import json
import numpy as np
from scipy.stats import weibull_min
from uni_traffic.traffic_components import PacketGenerator, PacketGeneratorGen2


class TrafficGeneratorBuilder:
    traf_classes = {"voice": 0, "video": 1, "data": 2, "best_effort": 3}

    def __init__(self, traf_types="./uni_traffic/traffic_types.json"):
        self.traf_configs = json.load(open(traf_types))

    def generate_distribution(self, distribution, parameters: list, multiplier=1):
        def configured_distr():
            return multiplier * distribution(*parameters)
        return configured_distr

    def packet_source(self, env, flow_id, traf_type, activation_time=0):
        def deterministic(parameter, dumb=None):
            return parameter  # time interval
        distribution_types = {"poisson": np.random.poisson,
                              "normal": np.random.normal,
                              "deterministic": deterministic,
                              "exponential": np.random.exponential,
                              "weibull": np.random.weibull,
                              "weibull_min": weibull_min}
        # if traf_type in self.traf_configs["traffic"]:
        config = self.traf_configs["traffic"][traf_type]
        if "model_gen" in config:
            # в состоянии активности: распределения
            # интервала отправки и размера сообщений
            adist_type = config['act_interval_distribution']
            adistrib = distribution_types[adist_type]
            adist_params = list()
            if 'act_interval_mean' in config:
                par = config['act_interval_mean']
                adist_params.append(1/par)
            adist = self.generate_distribution(adistrib, adist_params)

            asdist_type = config['act_size_of_packet_distribution']
            asdistrib = distribution_types[asdist_type]
            asdist_params = list()
            for par in ["act_size_of_packet", "sigma_sop", "lam_sop"]:
                if par in config:
                    asdist_params.append(config[par])
            asdist = self.generate_distribution(asdistrib, asdist_params)



            # в состоянии не-активности:
            # интервал отправки и размер сообщений
            pdist_type = config['pas_interval_distribution']
            pdistrib = distribution_types[pdist_type]
            pdist_params = list()
            if 'pas_interval_mean' in config:
                par = config['pas_interval_mean']
                pdist_params.append(config[1/par])
            pdist = self.generate_distribution(pdistrib, pdist_params)

            psdist_type = config['pas_size_of_packet_distribution']
            psdistrib = distribution_types[psdist_type]
            psdist_params = list()
            if 'pas_size_of_packet' in config:
                psdist_params.append(config['pas_size_of_packet'])

            pg = PacketGeneratorGen2(env, flow_id,
                                     active_dist=adist,
                                     active_sdist=asdist,
                                     active_idist=aidist,
                                     passive_dist=pdist,
                                     passive_sdist=pdist,
                                     passive_idist=pidist,
                                     initial_delay=activation_time, flow_id=flow_id,
                                     cos=config["class"], service=config["service"])
        else:
            # распределение и интервал отправки сообщений
            adist_type = config["send_interval_distribution"]
            adistrib = distribution_types[adist_type]
            a_dist_params = list()
            for par in ["send_interval", "sigma_si"]:
                if par in config:
                    a_dist_params.append(config[par])
            adist = self.generate_distribution(adistrib, a_dist_params)
            # распределение и размер сообщений
            sdist_type = config["size_of_packet_distribution"]
            sdistrib = distribution_types[sdist_type]
            s_dist_params = list()
            for par in ["size_of_packet", "sigma_sop", "lam_sop"]:
                if par in config:
                    s_dist_params.append(config[par])
            multi = config["sop_multiplier"] if "sop_multiplier" in config else 1
            sdist = self.generate_distribution(sdistrib, s_dist_params, multiplier=multi)
            if "activity_interval_distribution" in config and "silence_interval_distribution" in config:
                # распределение и длительность интервала активности
                act_dist_type = config["activity_interval_distribution"]
                act_distrib = distribution_types[act_dist_type]
                act_dist_params = list()
                for par in ["activity_interval", "sigma_ai"]:
                    if par in config:
                        act_dist_params.append(config[par])
                act_dist = self.generate_distribution(act_distrib, act_dist_params)

                # распределение и длительность интервала не активности
                pas_dist_type = config["silence_interval_distribution"]
                pas_distrib = distribution_types[pas_dist_type]
                pas_dist_params = list()
                for par in ["silence_interval", "sigma_silence"]:
                    if par in config:
                        pas_dist_params.append(config[par])
                pas_dist = self.generate_distribution(pas_distrib, pas_dist_params)
            else:
                act_dist = None
                pas_dist = None
            # (env, id, adist, sdist, initial_delay = 0, finish = float("inf"), flow_id = 0
            pg = PacketGenerator(env, flow_id, adist, sdist, active_dist=act_dist, passive_dist=pas_dist,
                                 initial_delay=activation_time, flow_id=flow_id,
                                 cos=config["class"], service=config["service"])
        return pg

    def uni_input_for_ont(self, env, service, constructor, port_type=None):
        if port_type in self.traf_configs["ports"]:
            config = self.traf_configs["ports"][port_type]
            rate, qlimit = config["rate"], config["qlimit"]
        else:
            rate = 1000000
            qlimit = 2000000
        # env, rate, qlimit = None, limit_bytes = True, debug = False
        uniport = constructor(env, rate, qlimit)
        uniport.traf_class = self.traf_classes[service]
        return uniport
