import json


class Traffic:
    def __init__(self, dev_name, id, type):
        configs = json.load(open('./uni_traffic/traffic_types.json'))
        config = configs[type]
        self.id = dev_name + '_' + id
        self.queue = list()
        self.traf_class = config["class"]
        self.service = config["service"]
        if config["distribution"] == "deterministic":
            self.send_interval = config["send_interval"]
            self.size_of_packet = config["size_of_packet"]
        else:
            raise NotImplemented

    def new_message(self, time):
        message = {'born_time': time,
                   'alloc_id': self.id,
                   'traf_class': self.traf_class,
                   'interval': self.send_interval,
                   'size': self.size_of_packet,
                   'fragment_offset': self.size_of_packet,
                   'packet_id': self.id + '_{}'.format(time),
                   'llid': self.id
                   }
        self.queue.append(message)

