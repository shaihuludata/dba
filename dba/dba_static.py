from dba.dba import Dba


class DbaStatic(Dba):
    """Пробная версия, работает только для первого потока на каждой ONT"""
    def __init__(self, env, config, snd_sig):
        Dba.__init__(self, env, config, snd_sig)

    def run(self):
        while True:
            requests = self.ont_discovered
            alloc_timer = 0  # in bytes
            bwmap = list()
            onts = len(requests)
            max_alloc_time = self.maximum_allocation_start_time  # in bytes!
            # if (self.next_cycle_start not in self.global_bwmap)\
            #         or len(self.global_bwmap[self.next_cycle_start]) == 0:
            for ont in requests:
                # Выбрать первый поток от ont
                alloc = str()
                for allocation in requests[ont]:
                    if allocation.endswith("_1"):
                        alloc = allocation
                        break
                # Выделить пропускную способность ont, обратно пропорционально количеству ont
                if alloc_timer <= max_alloc_time:
                    alloc_structure = {"Alloc-ID": alloc,  # "Flags": 0,
                                       "StartTime": alloc_timer, "StopTime": None}  # , "CRC": None}
                    # для статичного DBA выделяется интервал, обратно пропорциональный
                    # self.maximum_ont_amount - количеству ONT
                    alloc_timer += round(max_alloc_time / onts) - self.upstream_interframe_interval
                    alloc_structure["StopTime"] = alloc_timer
                    bwmap.append(alloc_structure)
                alloc_timer += self.upstream_interframe_interval
            self.global_bwmap[self.next_cycle_start] = bwmap
            # olt подтянет bwmap из snd_port_sig
            if "bwmap" not in self.snd_sig:
                self.snd_sig["bwmap"] = bwmap
            else:
                pass
            self.snd_sig["s_timestamp"] = self.env.now
            yield self.env.timeout(self.cycle_duration)


class DbaStaticAllocs(Dba):
    def __init__(self, env, config, snd_sig):
        Dba.__init__(self, env, config, snd_sig)

    def run(self):
        while True:
            requests = self.ont_discovered
            alloc_timer = 0  # in bytes
            bwmap = list()
            onts = list()
            allocs = list()
            for ont in requests:
                onts.append(ont)
                allocs += requests[ont]
            max_time = self.maximum_allocation_start_time  # in bytes!
            for ont in requests:
                for alloc in requests[ont]:
                    if alloc_timer <= max_time:
                        alloc_structure = {"Alloc-ID": alloc,  # "Flags": 0,
                                           "StartTime": alloc_timer, "StopTime": None}  # , "CRC": None}
                        # для статичного DBA выделяется интервал, обратно пропорциональный
                        # self.maximum_ont_amount - количеству ONT
                        alloc_size = round(max_time / len(allocs))
                        alloc_timer += alloc_size
                        alloc_structure["StopTime"] = alloc_timer
                        bwmap.append(alloc_structure)
                alloc_timer += self.upstream_interframe_interval - self.upstream_interframe_interval
            self.global_bwmap[self.next_cycle_start] = bwmap
            # olt подтянет bwmap из snd_port_sig
            if "bwmap" not in self.snd_sig:
                self.snd_sig["bwmap"] = bwmap
            else:
                pass
            self.snd_sig["s_timestamp"] = self.env.now
            yield self.env.timeout(self.cycle_duration)
