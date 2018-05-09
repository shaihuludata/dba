import json
from sympy import Interval, FiniteSet
import numpy as np

distributions = {'poisson': np.random.poisson,
                 'normal': np.random.normal,
                 'even': np.random.rand}


class Traffic:
    size_of_array = 100

    def __init__(self, dev_name, id, type):
        configs = json.load(open('./uni_traffic/traffic_types.json'))
        config = configs[type]
        self.id = dev_name + '_' + id
        self.queue = list()
        self.traf_class = config["class"]
        self.service = config["service"]
        self.packet_counter = 0
        self.max_queue_size = config["max_queue_size"]  # in number_of_packets

        size = self.size_of_array
        if "send_interval" in config and "size_of_packet" in config:
            sid = config["send_interval_distribution"]
            par = config["send_interval"]
            if sid == "deterministic":
                self.send_interval = par * np.ones(size)
            elif sid == "poisson":
                self.send_interval = np.random.poisson(par, size)
            elif sid == "normal":
                sigma = config["sigma_si"]
                self.send_interval = np.random.normal(par, sigma, size)
            else:
                raise NotImplemented
                # dist_law = distributions[sid]
                # args = dict()
                # args['size'] = self.size_of_array
                # for par in ['lam']:  # , 'size']:
                #     if par in config:
                #         args[par] = config[par]
                # self.send_interval = dist_law(**args)
            par = config["size_of_packet"]
            sopd = config["size_of_packet_distribution"]
            if sopd == "deterministic":
                self.size_of_packet = par * np.ones(size)
            elif sopd == "poisson":
                self.size_of_packet = np.random.poisson(par, size)
            elif sopd == "normal":
                sigma = config["sigma_sop"]
                self.size_of_packet = np.random.normal(par, sigma, size)
            else:
                raise NotImplemented
            self.new_message = self.new_message_static_trafic
        self.last_packet_born = 0

        if "activity_interval" in config and "silence_interval" in config:
            aid = config["activity_interval_distribution"]
            par = config["activity_interval"]
            if aid == "deterministic":
                self.activity_interval = par * np.ones(size)
            elif aid == "poisson":
                self.activity_interval = np.random.poisson(par, size)
            elif aid == "normal":
                sigma = config["sigma_ai"]
                self.activity_interval = np.random.normal(par, sigma, size)
            else:
                raise NotImplemented
            par = config["silence_interval"]
            silenceid = config["silence_interval_distribution"]
            if silenceid == "deterministic":
                self.silence_interval = par * np.ones(size)
            elif silenceid == "poisson":
                self.silence_interval = np.random.poisson(par, size)
            elif silenceid == "normal":
                sigma = config["sigma_silence"]
                self.silence_interval = np.random.normal(par, sigma, size)
            else:
                raise NotImplemented
            self.new_message = self.new_message_periodical_activity
        else:
            self.activity_interval = np.zeros(size)

        self.last_activity = - self.activity_interval[0]
        self.last_end_of_silence = 0

    def new_message(self, time: float):
        raise NotImplemented

    def new_message_static_trafic(self, time: float):
        index = self.packet_counter%len(self.send_interval)
        if time - self.last_packet_born >= self.send_interval[index]:
            self.last_packet_born = time
            self.packet_counter += 1
            if len(self.queue) > self.max_queue_size:
                return False
            message = self.make_new_message(time)
            self.queue.append(message)
        return True

    def new_message_periodical_activity(self, time: float):
        index = self.packet_counter % len(self.send_interval)
        full_period = self.activity_interval[index] + self.silence_interval[index]
        current_part = time - self.last_activity
        if current_part >= full_period:
            self.last_activity = time
            return False
        elif current_part >= self.activity_interval[index]:
            return False
        else:
            index = self.packet_counter % len(self.send_interval)
            current_send_interval = self.send_interval[index]
            if time - self.last_packet_born >= current_send_interval:
                self.last_packet_born = time
                self.packet_counter += 1
                if len(self.queue) > self.max_queue_size:
                    return False
                message = self.make_new_message(time)
                self.queue.append(message)
                return True
            return False

    def make_new_message(self, time):
        index = self.packet_counter % len(self.send_interval)
        return {'born_time': time,
                'alloc_id': self.id,
                'traf_class': self.traf_class,
                'interval': self.send_interval,
                'size': self.size_of_packet[index],
                'total_size': self.size_of_packet[index],
                'fragment_offset': 0,
                'packet_id': self.id + '_{}'.format(time),
                'packet_num': self.packet_counter,
                }

