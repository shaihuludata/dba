import json


class Traffic:
    def __init__(self, type):
        configs = json.load(open('./traffic_types.json'))
        config = configs[type]
        self.traf_class = config["class"]
        self.service = config["service"]
        if config["distribution"] is "deterministic":
            self.send_interval = config["send_interval"]
            self.size_of_packet = config["size_of_packet"]
        else:
            raise NotImplemented

    def new_message(self, time):
        return {}

