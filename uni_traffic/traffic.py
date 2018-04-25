import json


class Traffic:
    def __init__(self, dev_name, id, type):
        configs = json.load(open('./uni_traffic/traffic_types.json'))
        config = configs[type]
        self.id = dev_name + '_' + id
        self.queue = list()
        self.traf_class = config["class"]
        self.service = config["service"]
        self.packet_counter = 0
        self.last_packet_born = 0
        self.max_queue_size = config["max_queue_size"]  # in number_of_packets
        if config["distribution"] == "deterministic":
            self.send_interval = config["send_interval"]
            self.size_of_packet = config["size_of_packet"]
        else:
            raise NotImplemented

    def new_message(self, time):
        if len(self.queue) > self.max_queue_size:
            self.packet_counter += 1
            return False
        if time - self.last_packet_born >= self.send_interval:
            self.last_packet_born = time
            self.packet_counter += 1
            message = {'born_time': time,
                       'alloc_id': self.id,
                       'traf_class': self.traf_class,
                       'interval': self.send_interval,
                       'size': self.size_of_packet,
                       'total_size': self.size_of_packet,
                       'fragment_offset': 0,
                       'packet_id': self.id + '_{}'.format(time),
                       'packet_num': self.packet_counter,
                       }
            self.queue.append(message)
        return True