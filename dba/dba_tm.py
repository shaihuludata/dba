from dba.dba import Dba
import math


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

    def register_new_ont(self, s_number, allocs: dict):
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
        self.recalculate_utilisation(alloc)
        if "ONT4" in alloc:
            al_bw = self.alloc_bandwidth[alloc]
            al_max_bw = self.alloc_max_bandwidth[alloc]
            al_uti = self.alloc_utilisation[alloc]
            pass

    def recalculate_utilisation(self, alloc):
        total_bw = self.alloc_bandwidth[alloc]
        total_grant = self.alloc_grants[alloc][-len(total_bw):]
        mean_total_bw = sum(total_bw) / len(total_bw)
        mean_total_grant = sum(total_grant) / len(total_grant)
        current_uti = round(mean_total_bw / mean_total_grant, 2)
        if len(self.alloc_utilisation[alloc]) >= self.mem_size:
            self.alloc_utilisation[alloc].pop(0)
        self.alloc_utilisation[alloc].append(round(current_uti, 2))


class DbaTrafficMonLinear(DbaTM):
    TM_linear_multi_dict = {0: {0.9: 1.1, 0: 0.7},
                            1: {0.9: 1.5, 0: 0.7},
                            2: {0.9: 3.0, 0: 0.7},
                            3: {0.9: 3.0, 0: 0.7}}

    def generate_alloc(self, bw, uti, alloc):
        al_class = self.alloc_class[alloc]
        utis = self.TM_linear_multi_dict[al_class]
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
        alloc_size = self.min_grant if alloc_size < self.min_grant else alloc_size

        if "ONT4" in alloc:
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
            # несколько максимальных значений в списке
            # вычисляем среднее
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

        if "ONT4" in alloc:
            al_bw = self.alloc_bandwidth[alloc]
            al_uti = self.alloc_utilisation[alloc]
            al_max_bw = self.alloc_max_bandwidth[alloc]


class DbaTMLinearFair(DbaTrafficMonLinear):
    def run(self):
        while True:
            ont_alloc_dict = self.ont_discovered
            requests = dict()
            max_time = self.maximum_allocation_start_time - len(self.ont_discovered) * self.upstream_interframe_interval

            # расчитать веса аллоков
            weigths = dict()
            for ont in ont_alloc_dict:
                allocs = ont_alloc_dict[ont]
                for alloc in allocs:
                    if len(self.alloc_bandwidth[alloc]) > 0:
                        current_bw = self.alloc_bandwidth[alloc][-1]
                    else:
                        current_bw = self.min_grant
                    current_uti = self.alloc_utilisation[alloc][-1]
                    weight = self.generate_alloc_weight(current_bw, current_uti, alloc)
                    weigths[alloc] = weight
                    if alloc not in requests:
                        requests[alloc] = 0

            # определить доли от max_time
            total_weight = sum(weigths.values())
            portions = dict()
            if total_weight == 0:
                total_weight += 1
            portions = {alloc: weigths[alloc]/total_weight for alloc in weigths}

            for alloc in portions:
                portion = portions[alloc]
                if portion * max_time < self.min_grant:
                    requests[alloc] = self.min_grant
            max_time -= sum(requests[i] for i in requests)
            assert max_time > 0
            for alloc in portions:
                if requests[alloc] == 0:
                    portion = portions[alloc]
                    alloc_size = int(round(portion * max_time))
                    requests[alloc] = alloc_size

            # после определения реальных значений аллоков, их можно записать в гранты
            for alloc in requests:
                alloc_size = requests[alloc]
                if len(self.alloc_grants[alloc]) >= self.mem_size:
                    self.alloc_grants[alloc].pop(0)
                self.alloc_grants[alloc].append(alloc_size)
            bwmap = self.compose_bwmap_message(requests, ont_alloc_dict, self.maximum_allocation_start_time)

            if "bwmap" not in self.snd_sig:
                self.snd_sig["bwmap"] = bwmap
            else:
                pass
            self.snd_sig["s_timestamp"] = self.env.now
            if self is None:
                raise Exception("WTF????")
            yield self.env.timeout(self.cycle_duration)

    fair_multipliers = {0: {"bw": 1.0, "uti": 2},
                        1: {"bw": 0.9, "uti": 3},
                        2: {"bw": 0.8, "uti": 4},
                        3: {"bw": 0.5, "uti": 5}}

    def generate_alloc_weight(self, bw, uti, alloc):
        al_class = self.alloc_class[alloc]
        if bw == 0 or uti == 0:
            return 0
        # bw_weight = bw * self.fair_multipliers[al_class]["bw"]
        bw_weight = math.log10(bw)  # * self.fair_multipliers[al_class]["bw"]
        uti_weight = uti * self.fair_multipliers[al_class]["uti"]
        weight = bw_weight + uti_weight
        return weight
        # alloc_size = round(bw * uti * multi + 0.5)
        # max_bw = self.alloc_max_bandwidth[alloc]
        # for traf_type in ["voice", "video"]:
        #     if self.alloc_class[alloc] == self.traf_classes[traf_type]:
        #         alloc_size = 1.1 * max_bw if alloc_size > 1.1 * max_bw else alloc_size
        # alloc_size = self.min_grant if alloc_size < self.min_grant else alloc_size
        #
        # if "ONT4" in alloc:
        #     if bw > self.min_grant and alloc_size > bw:
        #         self.empty()
        # return alloc_size
