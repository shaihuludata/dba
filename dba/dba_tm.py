from dba.dba import Dba


class DbaTM(Dba):
    def __init__(self, env, config, snd_sig):
        Dba.__init__(self, env, config, snd_sig)
        # минимальный размер гранта при утилизации 0
        self.min_grant = 10
        self.mem_size = 10
        # для хранения текущих значений утилизации
        self.alloc_utilisation = dict()
        # для хранения информации о выданных грантах
        self.alloc_grants = dict()
        # для хранения информации о размерах полученных пакетов
        self.alloc_bandwidth = dict()
        self.alloc_max_bandwidth = dict()
        # для хранения информации о классах alloc"ов
        self.alloc_class = dict()

    def run(self):
        while True:
            ont_alloc_dict = self.ont_discovered
            requests = dict()
            max_time = self.maximum_allocation_start_time - len(self.ont_discovered) * self.upstream_interframe_interval

            for ont in ont_alloc_dict:
                allocs = ont_alloc_dict[ont]
                for alloc in allocs:
                    if len(self.alloc_bandwidth[alloc]) > 0:
                        current_bw = self.alloc_bandwidth[alloc][-1]
                    else:
                        current_bw = self.min_grant
                    current_uti = self.alloc_utilisation[alloc][-1]
                    alloc_size = self.generate_alloc(current_bw, current_uti, alloc)
                    if alloc not in requests:
                        requests[alloc] = alloc_size
                    else:
                        raise Exception("Странная какая-то ошибка")
            requests = self.crop_allocations(requests, max_time)
            # после определения реальных значений аллоков, их можно записать в гранты
            for alloc in requests:
                alloc_size = requests[alloc]
                if len(self.alloc_grants[alloc]) >= self.mem_size:
                    self.alloc_grants[alloc].pop(0)
                self.alloc_grants[alloc].append(alloc_size)
            bwmap = self.compose_bwmap_message(requests, ont_alloc_dict, max_time)

            if "bwmap" not in self.snd_sig:
                self.snd_sig["bwmap"] = bwmap
            else:
                pass
            self.snd_sig["s_timestamp"] = self.env.now
            yield self.env.timeout(self.cycle_duration)

    def compose_bwmap_message(self, requests, ont_alloc_dict, max_time):
        bwmap = list()
        alloc_timer = 0  # in bytes
        for ont in ont_alloc_dict:
            if alloc_timer < max_time:
                allocs = ont_alloc_dict[ont]
                for alloc in allocs:
                    alloc_structure = {"Alloc-ID": alloc,  # "Flags": 0,
                                       "StartTime": alloc_timer, "StopTime": None}  # , "CRC": None}
                    alloc_size = round(requests[alloc])
                    alloc_timer += alloc_size
                    alloc_structure["StopTime"] = alloc_timer
                    if alloc_timer > self.maximum_allocation_start_time:
                        print("ошибка")
                    bwmap.append(alloc_structure)
                alloc_timer += self.upstream_interframe_interval
        return bwmap

    def generate_alloc(self, bw, uti, alloc):
        alloc_size = int()
        if uti < 0.9:
            alloc_size = round(bw * 0.5 + 0.5)
        else:  # if uti in Interval(0.9, 1):
            alloc_size = round(bw * 5 + 0.5)
        if alloc_size < self.min_grant:
            alloc_size = self.min_grant
        return alloc_size

    def crop_allocations(self, requests: dict, max_time):
        total_size = sum(requests.values())
        while total_size > max_time - 200:
            ratio = total_size / max_time + 0.08
            for alloc in requests:
                current_req = requests[alloc]
                new_req = round(requests[alloc] / ratio)
                requests[alloc] = new_req
            total_size = sum(requests.values())
        return requests

    def register_new_ont(self, s_number, allocs: list):
        self.ont_discovered[s_number] = list(allocs.keys())
        for alloc in allocs:
            self.alloc_utilisation[alloc] = [0]
            self.alloc_grants[alloc] = [self.min_grant]
            self.alloc_bandwidth[alloc] = [0]
            self.alloc_max_bandwidth[alloc] = 0
            self.alloc_class[alloc] = allocs[alloc]

    def register_packet(self, alloc, packets: list):
        size = int()
        for packet in packets:
            size += packet.size
        if len(self.alloc_bandwidth[alloc]) >= self.mem_size:
            self.alloc_bandwidth[alloc].pop(0)
        self.alloc_bandwidth[alloc].append(size)
        self.alloc_max_bandwidth[alloc] = max(self.alloc_bandwidth[alloc])
        # if self.alloc_max_bandwidth[alloc] < size:
        #     self.alloc_max_bandwidth[alloc] = size
        self.recalculate_utilisation(alloc)

    def recalculate_utilisation(self, alloc):
        total_bw = self.alloc_bandwidth[alloc]
        total_grant = self.alloc_grants[alloc][-len(total_bw):]
        mean_total_bw = sum(total_bw) / len(total_bw)
        mean_total_grant = sum(total_grant) / len(total_grant)
        current_uti = round(mean_total_bw / mean_total_grant, 2)
        # if current_uti > 1:
        #     print("uti {} > 1".format(current_uti))
        # current_uti = total_bw[-1] / total_grant[-1]
        if len(self.alloc_utilisation[alloc]) >= self.mem_size:
            self.alloc_utilisation[alloc].pop(0)
        self.alloc_utilisation[alloc].append(round(current_uti, 2))


class DbaTrafficMonLinear(DbaTM):
    TM_linear_multi_dict = {0: {0.9: 1.1, 0: 0.7},
                            1: {0.9: 1.5, 0: 0.7},
                            2: {0.9: 3.0, 0: 0.7},
                            3: {0.9: 3.0, 0: 0.7}}

    def empty(self):
        pass

    def generate_alloc(self, bw, uti, alloc):
        utis = self.TM_linear_multi_dict[self.alloc_class[alloc]]
        multi = float()
        utis_list = list(utis.keys())
        utis_list.sort()
        for i in utis_list:
            if uti > i:
                multi = utis[i]

        alloc_size = round(bw * uti * multi + 0.5)
        max_bw = self.alloc_max_bandwidth[alloc]
        for traf_type in ["voice", "video"]:
            if self.alloc_class[alloc] == self.traf_classes[traf_type]:
                alloc_size = 1.1 * max_bw if alloc_size > 1.1 * max_bw else alloc_size

        if alloc_size < self.min_grant:
            alloc_size = self.min_grant
        if bw > self.min_grant and alloc_size > bw:
            self.empty()
        return alloc_size

    def crop_allocations(self, requests: dict, max_time):
        for traf in ["best_effort", "data", "video", "voice"]:
            total_size = sum(requests.values())
            while total_size > max_time:
                traf_dict = {i: requests[i] for i in self.alloc_class if self.alloc_class[i] == self.traf_classes[traf]}
                delta_size = total_size - (max_time)
                total_traf_size = sum(list(traf_dict.values()))
                if total_traf_size > delta_size:
                    ratio = total_traf_size / delta_size
                    for alloc in traf_dict:
                        new_req = int(round(requests[alloc] / ratio))
                        requests[alloc] = new_req
                else:
                    for alloc in traf_dict:
                        requests[alloc] = 0
                    break
                total_size = sum(requests.values())
        total_size = sum(requests.values())
        return requests

    def register_packet(self, alloc, packets: list):
        def calc_mean_three_max(alloc_bw: list):
            big_list = list(alloc_bw)
            if len(big_list) > 5:
                lit_list = list()
                for i in range(0, 2):
                    max_val = max(big_list)
                    big_list.remove(max_val)
                    lit_list.append(max_val)
                mean_max = sum(lit_list) / len(lit_list)
            else:
                mean_max = max(big_list)
            return mean_max

        size = int()
        for packet in packets:
            size += packet.size
        if len(self.alloc_bandwidth[alloc]) >= self.mem_size:
            self.alloc_bandwidth[alloc].pop(0)
        self.alloc_bandwidth[alloc].append(size)
        self.alloc_max_bandwidth[alloc] = calc_mean_three_max(self.alloc_bandwidth[alloc])
        self.recalculate_utilisation(alloc)
