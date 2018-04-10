from active_optics import ActiveDevice
from collections import OrderedDict
from signal import Signal

dumb_event = {'dev': None, 'state': 'dumb_event', 'sig': None, 'port': None}

# class C_Alloc:
#     def __init__(self):
#         c_alloc = {'Alloc-ID': 1, 'Flags': 2, 'StartTime': 3, 'StopTime': 4, 'CRC': 5}
#         self.alloc_structure = OrderedDict(sorted(c_alloc.items(), key=lambda t: t[1]))
#
#     def new_alloc(self):
#         return self.alloc_structure

class Olt(ActiveDevice):
    serial_number_quiet_interval = 200

    def __init__(self, name, config):
        ActiveDevice.__init__(self, name, config)
        self.serial_number_request_interval = self.config['sn_request_interval']
        self.upstream_interframe_interval = 10 #in bytes
        self.sn_request_last_time = -2250
        self.sn_request_quiet_interval_end = 0
        self.ont_discovered = dict()
        self.maximum_ont_amount = int(self.config['maximum_ont_amount'])

        if self.config["transmitter_type"] == "1G":
            self.maximum_allocation_start_time = 19438
        elif self.config["transmitter_type"] == "2G":
            self.maximum_allocation_start_time = 38878

    def plan_next_act(self, time):
        self.time = time
        if self.state == 'Offline':
            self.state = 'Initial'
            time = time + self.cycle_duration
        planned_s_time = round(time / self.cycle_duration + 0.51) * self.cycle_duration
        self.next_cycle_start = planned_s_time
        planned_e_time = planned_s_time + self.cycle_duration
        sig = None
        if self.state == 'Initial':
            if planned_s_time not in self.device_scheduler:
                self.data_to_send = self.make_bwmap(time, self.requests)
                sig = Signal('{}:{}:{}'.format(planned_s_time, self.name, planned_e_time), self.data_to_send)
                self.device_scheduler[planned_s_time] = sig.id
                return {planned_s_time: [{"dev": self, "state": "s_start", "sig": sig, "port": 0}],
                        planned_e_time: [{"dev": self, "state": "s_end", "sig": sig, "port": 0}]
                        }
            else:
                return {}

    def make_bwmap(self, time, requests):
        bwmap = list()
        sn_request = False
        if (time - self.sn_request_last_time) >= self.serial_number_request_interval:
            self.sn_request_last_time = self.next_cycle_start
            self.sn_request_quiet_interval_end =\
                self.next_cycle_start + self.serial_number_quiet_interval + 236
            sn_request = True
            # alloc_structure['Alloc-ID'] = 'to_all'
            # alloc_structure['Flags'] = 0
            # alloc_structure['StartTime'] = self.next_cycle_start + 236
            # alloc_structure['StopTime'] = self.sn_request_quiet_interval_end + 236
            # allocation = alloc_structure
            # bwmap.append(allocation)
        elif self.config['dba_type'] == 'static':
            alloc_timer = 0 #in bytes
            max_time = self.maximum_allocation_start_time
            for ont in self.ont_discovered:
                for alloc in self.ont_discovered[ont]:
                    # if self.ont_discovered[ont][alloc] is 'Ranging':
                    if alloc_timer <= max_time:
                        #self.ont_discovered[ont][alloc] = '{}'.format(alloc_timer)
                        alloc_structure = {'Alloc-ID': alloc,
                                           'Flags': 0,
                                           'StartTime': alloc_timer,
                                           'StopTime': None,
                                           'CRC': None}
                        #для статичного DBA выделяется интервал, обратно пропорциональный
                        #self.maximum_ont_amount - количеству ONT
                        alloc_timer += round(max_time / self.maximum_ont_amount)
                        alloc_structure['StopTime'] = alloc_timer
                        if len(bwmap) > 0:
                            pass
                        bwmap.append(alloc_structure)

                alloc_timer += self.upstream_interframe_interval
        else:
            print('Unknown dba_type {}'.format(self.config['dba_type']))
        return {'bwmap': bwmap, 'sn_request': sn_request, 's_timestamp': self.next_cycle_start}

    # def r_start(self, sig, port: int):
    #     self.receiving_sig.append(sig)
    #     if len(self.receiving_sig) > 1:
    #         print('{} ИНТЕРФЕРЕНЦИОННАЯ КОЛЛИЗИЯ на порту {}!!!'.format(self.name, port))
    #         sig.physics['collision'] = True
    #         for rec_sig in self.receiving_sig:
    #             rec_sig.physics['collision'] = True
    #     output = {"sig": sig, "delay": self.cycle_duration}
    #     return {port: output}

    def r_end(self, sig, port: int):
        for rec_sig in self.receiving_sig:
            if rec_sig.id == sig.id:
                self.receiving_sig.remove(rec_sig)
                if rec_sig.physics['collision']:
                    self.counters.ingress_collision += 1
                    return {}
                break
        if 'sn_response' in sig.data and self.time < self.sn_request_quiet_interval_end:
            #self.ont_discovered.append(sig.data['sn_response'])
            s_number = sig.data['sn_response']
            self.ont_discovered[s_number] = {s_number+'_0': None}
            sig = self.oe_transform(sig)
        #output = {"sig": sig, "delay": delay}
        else:
            self.counters.ingress_unicast += 1
            pass
        return {}#port: output}

