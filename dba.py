

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
        if len(bwmap) > 0:
            pass
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
        if len(bwmap) > 0:
            pass
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

    def bwmap(self, cur_time):
        requests = self.ont_discovered
        alloc_timer = 0  # in bytes
        bwmap = list()
        onts = len(requests)
        max_time = self.maximum_allocation_start_time
        for ont in requests:
            print(requests[ont])

        return bwmap

    def register_new_ont(self, s_number, allocs: list()):
        self.ont_discovered[s_number] = allocs
        for alloc in allocs:
            self.alloc_utilisation[alloc] = 1
            self.alloc_grants[alloc] = list()
            self.alloc_bandwidth[alloc] = list()

    def register_packet(self, alloc, size):
        if len(self.alloc_bandwidth[alloc]) > self.mem_size:
            self.alloc_bandwidth[alloc].pop(0)
        self.alloc_bandwidth[alloc].append(size)
        self.recalculate_utilisation(alloc)

    def recalculate_utilisation(self, alloc):
        total_bw = self.alloc_bandwidth[alloc]
        total_grant = self.alloc_grants[alloc]
        self.alloc_utilisation[alloc] = sum(total_bw) / sum(total_grant)


