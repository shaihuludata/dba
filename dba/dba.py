from addict import Dict


class Dba:
    traf_classes = Dict({"voice": 0, "video": 1, "data": 2, "best_effort": 3})

    def __init__(self, env, config, snd_sig):
        self.env = env
        self.global_bwmap = dict()  # {time: intra_cycle_bwmap}
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

    def sn_request(self):
        bwmap = list()
        alloc_structure = {"Alloc-ID": "to_all",  # "Flags": 0,
                           "StartTime": 0,
                           "StopTime": self.maximum_allocation_start_time}  # , "CRC": None}
        bwmap.append(alloc_structure)
        self.global_bwmap[self.next_cycle_start] = bwmap
        self.global_bwmap[self.next_cycle_start + self.cycle_duration] = bwmap
        return bwmap

    def register_new_ont(self, s_number, allocs):
        self.ont_discovered[s_number] = allocs

    def register_packet(self, alloc, size):
        pass
