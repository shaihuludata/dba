
class Dba:
    traf_classes = {"voice": 0, "video": 1, "data": 2, "best_effort": 3}

    def __init__(self, env, config, snd_sig):
        self.env = env
        self.global_bwmap = dict()
        self.next_cycle_start = 0
        self.ont_discovered = dict()
        self.cycle_duration = config["cycle_duration"]
        self.snd_sig = snd_sig
        self.upstream_interframe_interval = config["upstream_interframe_interval"]
        if "maximum_allocation_start_time" in config and config["maximum_allocation_start_time"] is not None:
            self.maximum_allocation_start_time = config["maximum_allocation_start_time"]
        elif config["transmitter_type"] == "1G":
            self.maximum_allocation_start_time = 19438
        elif config["transmitter_type"] == "2G":
            self.maximum_allocation_start_time = 38878

        self.action = env.process(self.run())

    def run(self):
        while True:
            raise NotImplemented

    def empty(self):
        pass

    def sn_request(self):
        bwmap = list()
        alloc_structure = {"Alloc-ID": "to_all",
                           "StartTime": 0,
                           "StopTime": self.maximum_allocation_start_time}
        bwmap.append(alloc_structure)
        self.global_bwmap[self.next_cycle_start] = bwmap
        self.global_bwmap[self.next_cycle_start + self.cycle_duration] = bwmap
        return bwmap

    def register_new_ont(self, s_number, allocs):
        self.ont_discovered[s_number] = allocs

    def register_packet(self, alloc, size):
        pass
