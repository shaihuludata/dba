import json
import numpy as np
from uni_traffic.traffic_components import UniPort, PacketGenerator


class TrafficGeneratorBuilder:
    traf_classes = {"voice": 0, "video": 1, "data": 2, "best_effort": 3}
    # elif sid == "poisson":
    #     (par, size)
    # elif sid == "normal":
    #     sigma = config["sigma_si"]
    #     self.send_interval = (par, sigma, size)

    def __init__(self):
        self.traf_configs = json.load(open("./uni_traffic/traffic_types.json"))

    def generate_distribution(self, distribution, parameters: list):
        def configured_distr():
            return distribution(*parameters)
        return configured_distr

    def packet_source(self, env, flow_id, traf_type, activation_time=0):
        def deterministic(parameter, dumb=None):
            return parameter  # time interval
        distribution_types = {"poisson": np.random.poisson,
                        "normal": np.random.normal,
                        "deterministic": deterministic}
        if traf_type in self.traf_configs["traffic"]:
            config = self.traf_configs["traffic"][traf_type]
            adist_type = config["send_interval_distribution"]
            adistrib = distribution_types[adist_type]
            a_dist_params = list()
            for par in ["send_interval", "sigma_si"]:
                if par in config:
                    a_dist_params.append(config[par])
            adist = self.generate_distribution(adistrib, a_dist_params)
            sdist_type = config["size_of_packet_distribution"]
            sdistrib = distribution_types[sdist_type]
            s_dist_params = list()
            for par in ["size_of_packet", "sigma_sop"]:
                if par in config:
                    s_dist_params.append(config[par])
            sdist = self.generate_distribution(sdistrib, s_dist_params)
        else:
            raise NotImplemented
        # (env, id, adist, sdist, initial_delay = 0, finish = float("inf"), flow_id = 0
        pg = PacketGenerator(env, flow_id, adist, sdist, initial_delay=activation_time, flow_id=flow_id)
        pg.service = config["service"]
        return pg

    def uni_input_for_ont(self, env, pg, port_type=None):
        if port_type in self.traf_configs["ports"]:
            config = self.traf_configs["ports"][port_type]
            rate, qlimit = config["rate"], config["qlimit"]
        else:
            rate = 1000000
            qlimit = 2000000
        # env, rate, qlimit = None, limit_bytes = True, debug = False
        uniport = UniPort(env, rate, qlimit)
        uniport.traf_class = self.traf_classes[pg.service]
        pg.out = uniport
        return uniport
