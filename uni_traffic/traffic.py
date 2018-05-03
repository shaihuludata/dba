import json
from sympy import Interval, FiniteSet


class Traffic:
    def __init__(self, dev_name, id, type):
        configs = json.load(open('./uni_traffic/traffic_types.json'))
        config = configs[type]
        self.id = dev_name + '_' + id
        self.queue = list()
        self.traf_class = config["class"]
        self.service = config["service"]
        self.packet_counter = 0
        self.max_queue_size = config["max_queue_size"]  # in number_of_packets

        if "send_interval" in config and "size_of_packet" in config:
            if config["send_interval_distribution"] == "deterministic":
                self.send_interval = config["send_interval"]
            if config["size_of_packet_distribution"] == "deterministic":
                self.size_of_packet = config["size_of_packet"]
            self.new_message = self.new_message_static_trafic
        self.last_packet_born = 0

        if "activity_interval" in config and "silence_interval" in config:
            if config["activity_interval_distribution"] == "deterministic":
                self.activity_interval = config["activity_interval"]
            if config["silence_interval_distribution"] == "deterministic":
                self.silence_interval = config["silence_interval"]
            self.new_message = self.new_message_periodical_activity
        else:
            self.activity_interval = 0
            self.silence_interval = 0
        self.last_activity = - self.activity_interval
        self.last_end_of_silence = 0

    def new_message(self, time: float):
        raise NotImplemented

    def new_message_static_trafic(self, time: float):
        if time - self.last_packet_born >= self.send_interval:
            self.last_packet_born = time
            self.packet_counter += 1
            if len(self.queue) > self.max_queue_size:
                return False
            message = self.make_new_message(time)
            self.queue.append(message)
        return True

    def new_message_periodical_activity(self, time: float):
        full_period = self.activity_interval + self.silence_interval
        current_part = time - self.last_activity
        if current_part >= full_period:
            self.last_activity = time
            # тут надо будет вставить пересчёт параметров для недетерминированных переменных
            return False
        elif current_part >= self.activity_interval:
            # self.last_end_of_silence = time
            return False
        else:
            if time - self.last_packet_born >= self.send_interval:
                self.last_packet_born = time
                self.packet_counter += 1
                if len(self.queue) > self.max_queue_size:
                    return False
                message = self.make_new_message(time)
                self.queue.append(message)
                return True
            return False

    def make_new_message(self, time):
        return {'born_time': time,
                'alloc_id': self.id,
                'traf_class': self.traf_class,
                'interval': self.send_interval,
                'size': self.size_of_packet,
                'total_size': self.size_of_packet,
                'fragment_offset': 0,
                'packet_id': self.id + '_{}'.format(time),
                'packet_num': self.packet_counter,
                }
