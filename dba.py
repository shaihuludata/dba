import numpy as np
from sympy import Interval
import collections
from addict import Dict

traf_classes = Dict({'voice': 0, 'video': 1, 'data': 2, 'best_effort': 3})


class Dba:
    def __init__(self, config):
        self.global_bwmap = dict()  # {time: intra_cycle_bwmap}
        self.next_cycle_start = 0
        self.ont_discovered = dict()
        self.cycle_duration = config['cycle_duration']

        self.upstream_interframe_interval = config['upstream_interframe_interval']

        if 'maximum_allocation_start_time' in config:
            self.maximum_allocation_start_time = config['maximum_allocation_start_time']
        elif config["transmitter_type"] == "1G":
            self.maximum_allocation_start_time = 19438
        elif config["transmitter_type"] == "2G":
            self.maximum_allocation_start_time = 38878

    def bwmap(self, cur_time):
        pass

    def sn_request(self):
        bwmap = list()
        alloc_structure = {'Alloc-ID': 'to_all',  # 'Flags': 0,
                           'StartTime': 0,
                           'StopTime': self.maximum_allocation_start_time}  # , 'CRC': None}
        # alloc_structure['StartTime'] = self.next_cycle_start + 236
        # alloc_structure['StopTime'] = self.sn_request_quiet_interval_end + 236
        bwmap.append(alloc_structure)
        self.global_bwmap[self.next_cycle_start] = bwmap
        self.global_bwmap[self.next_cycle_start + self.cycle_duration] = bwmap
        return bwmap

    def register_new_ont(self, s_number, allocs):
        self.ont_discovered[s_number] = allocs

    def register_packet(self, alloc, size):
        pass


class DbaStatic(Dba):
    def __init__(self, config):
        Dba.__init__(self, config)

    def bwmap(self, cur_time):
        requests = self.ont_discovered
        alloc_timer = 0  # in bytes
        bwmap = list()
        onts = len(requests)
        max_alloc_time = self.maximum_allocation_start_time  # in bytes!
        if (self.next_cycle_start not in self.global_bwmap)\
                or len(self.global_bwmap[self.next_cycle_start]) == 0:
            for ont in requests:
                alloc = str()
                for allocation in requests[ont]:
                    if allocation.endswith('_1'):
                        alloc = allocation
                        break
                if alloc_timer <= max_alloc_time:
                    alloc_structure = {'Alloc-ID': alloc,  # 'Flags': 0,
                                       'StartTime': alloc_timer, 'StopTime': None}  # , 'CRC': None}
                    # для статичного DBA выделяется интервал, обратно пропорциональный
                    # self.maximum_ont_amount - количеству ONT
                    alloc_timer += round(max_alloc_time / onts) - self.upstream_interframe_interval
                    alloc_structure['StopTime'] = alloc_timer
                    bwmap.append(alloc_structure)
                alloc_timer += self.upstream_interframe_interval
            self.global_bwmap[self.next_cycle_start] = bwmap
        else:
            bwmap = self.global_bwmap[self.next_cycle_start]
        return bwmap


class DbaStaticAllocs(Dba):
    def __init__(self, config):
        Dba.__init__(self, config)

    def bwmap(self, cur_time):
        requests = self.ont_discovered

        alloc_timer = 0  # in bytes
        bwmap = list()
        onts = list()
        allocs = list()

        for ont in requests:
            onts.append(ont)
            allocs += requests[ont]

        max_time = self.maximum_allocation_start_time
        if self.next_cycle_start not in self.global_bwmap:
            for ont in requests:
                for alloc in requests[ont]:
                    if alloc_timer <= max_time:
                        alloc_structure = {'Alloc-ID': alloc,  # 'Flags': 0,
                                           'StartTime': alloc_timer, 'StopTime': None}  # , 'CRC': None}
                        # для статичного DBA выделяется интервал, обратно пропорциональный
                        # self.maximum_ont_amount - количеству ONT
                        alloc_size = round(max_time / len(allocs))
                        alloc_timer += alloc_size
                        alloc_structure['StopTime'] = alloc_timer
                        bwmap.append(alloc_structure)
                alloc_timer += self.upstream_interframe_interval - self.upstream_interframe_interval
            self.global_bwmap[self.next_cycle_start] = bwmap
        else:
            bwmap = self.global_bwmap[self.next_cycle_start]
        return bwmap


class DbaSR(Dba):
    def __init__(self, config):
        Dba.__init__(self, config)

    def bwmap(self, cur_time):
        requests = self.ont_discovered
        alloc_timer = 0  # in bytes
        bwmap = list()
        onts = len(requests)
        max_time = self.maximum_allocation_start_time
        for ont in requests:
            print(requests[ont])

        return bwmap


class DbaTM(Dba):
    def __init__(self, config):
        Dba.__init__(self, config)
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
        # для хранения информации о классах alloc'ов
        self.alloc_class = dict()

    def bwmap(self, cur_time):
        ont_alloc_dict = self.ont_discovered
        requests = dict()
        max_time = self.maximum_allocation_start_time - len(self.ont_discovered)*self.upstream_interframe_interval
        if (self.next_cycle_start not in self.global_bwmap)\
                or len(self.global_bwmap[self.next_cycle_start]) == 0:
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
                        raise Exception('Странная какая-то ошибка')
            requests = self.crop_allocations(requests, max_time)
            # после определения реальных значений аллоков, их можно записать в гранты
            for alloc in requests:
                alloc_size = requests[alloc]
                if len(self.alloc_grants[alloc]) >= self.mem_size:
                    self.alloc_grants[alloc].pop(0)
                self.alloc_grants[alloc].append(alloc_size)
            bwmap = self.compose_bwmap_message(requests, ont_alloc_dict, max_time)
            self.global_bwmap[self.next_cycle_start] = bwmap
        else:
            bwmap = self.global_bwmap[self.next_cycle_start]
        return bwmap

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

    def compose_bwmap_message(self, requests, ont_alloc_dict, max_time):
        bwmap = list()
        alloc_timer = 0  # in bytes
        for ont in ont_alloc_dict:
            if alloc_timer < max_time:
                allocs = ont_alloc_dict[ont]
                for alloc in allocs:
                    alloc_structure = {'Alloc-ID': alloc,  # 'Flags': 0,
                                       'StartTime': alloc_timer, 'StopTime': None}  # , 'CRC': None}
                    alloc_size = round(requests[alloc])
                    alloc_timer += alloc_size
                    alloc_structure['StopTime'] = alloc_timer
                    if alloc_timer > self.maximum_allocation_start_time:
                        print('ошибка')
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

    def register_new_ont(self, s_number, allocs: list()):
        self.ont_discovered[s_number] = list(allocs.keys())
        for alloc in allocs:
            self.alloc_utilisation[alloc] = [0]
            self.alloc_grants[alloc] = [self.min_grant]
            self.alloc_bandwidth[alloc] = [0]
            self.alloc_max_bandwidth[alloc] = 0
            self.alloc_class[alloc] = allocs[alloc]

    def register_packet(self, alloc, packets: list()):
        size = int()
        for packet in packets:
            size += packet['size']
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
        #     print('uti {} > 1'.format(current_uti))
        # current_uti = total_bw[-1] / total_grant[-1]
        if len(self.alloc_utilisation[alloc]) >= self.mem_size:
            self.alloc_utilisation[alloc].pop(0)
        self.alloc_utilisation[alloc].append(round(current_uti, 2))


class DbaTM_extra(DbaTM):

    def generate_alloc(self, bw, uti, alloc):
        q = 0.5*np.poly1d([4.34470329e+03, -9.89671083e+03, 8.30071007e+03,
                       -3.16340293e+03, 5.35889941e+02, -2.12260766e+01, 3.03372901e-02])
        multi = q(uti)
        alloc_size = round(bw * multi + 0.5)
        if alloc_size < self.min_grant:
            alloc_size = self.min_grant
        return alloc_size


TM_linear_multi_dict = {0: {0.9: 1.1, 0: 0.7},
                        1: {0.9: 1.5, 0: 0.7},
                        2: {0.9: 3.0, 0: 0.7},
                        3: {0.9: 3.0, 0: 0.7}}


class DbaTM_linear(DbaTM):

    def empty(self):
        pass

    def generate_alloc(self, bw, uti, alloc):
        utis = TM_linear_multi_dict[self.alloc_class[alloc]]
        multi = float()
        utis_list = list(utis.keys())
        utis_list.sort()
        for i in utis_list:
            if uti > i:
                multi = utis[i]

        alloc_size = round(bw * uti * multi + 0.5)
        max_bw = self.alloc_max_bandwidth[alloc]
        for traf_type in ['voice', 'video']:
            if self.alloc_class[alloc] == traf_classes[traf_type]:
                alloc_size = 1.1 * max_bw if alloc_size > 1.1 * max_bw else alloc_size

        if alloc_size < self.min_grant:
            alloc_size = self.min_grant
        if bw > self.min_grant and alloc_size > bw:
            self.empty()
        return alloc_size

    def crop_allocations(self, requests: dict, max_time):
        for traf in ['best_effort', 'data', 'video', 'voice']:
            total_size = sum(requests.values())
            while total_size > max_time:
                traf_dict = {i: requests[i] for i in self.alloc_class if self.alloc_class[i] == traf_classes[traf]}
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

    def register_packet(self, alloc, packets: list()):
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
            size += packet['size']
        if len(self.alloc_bandwidth[alloc]) >= self.mem_size:
            self.alloc_bandwidth[alloc].pop(0)
        self.alloc_bandwidth[alloc].append(size)
        self.alloc_max_bandwidth[alloc] = calc_mean_three_max(self.alloc_bandwidth[alloc])
        self.recalculate_utilisation(alloc)
