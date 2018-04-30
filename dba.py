

class Dba:
    def __init__(self, config):
        self.global_bwmap = dict()  # {time: intra_cycle_bwmap}
        self.next_cycle_start = 0

        self.cycle_duration = config['cycle_duration']

        self.upstream_interframe_interval = config['upstream_interframe_interval']

        if 'maximum_allocation_start_time' in config:
            self.maximum_allocation_start_time = config['maximum_allocation_start_time']
        elif config["transmitter_type"] == "1G":
            self.maximum_allocation_start_time = 19438
        elif config["transmitter_type"] == "2G":
            self.maximum_allocation_start_time = 38878

    def bwmap(self, requests, cur_time):
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


class DbaStatic(Dba):
    def __init__(self, config):
        Dba.__init__(self, config)

    def bwmap(self, requests, cur_time):
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

    def bwmap(self, requests, cur_time):
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

    def bwmap(self, requests, cur_time):
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

    def bwmap(self, requests, cur_time):
        alloc_timer = 0  # in bytes
        bwmap = list()
        onts = len(requests)
        max_time = self.maximum_allocation_start_time
        for ont in requests:
            print(requests[ont])

        return bwmap