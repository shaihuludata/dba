from active_optics import ActiveDevice
from collections import OrderedDict
from signal import Signal
import copy


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
        self.upstream_interframe_interval = self.config['upstream_interframe_interval'] #10 #in bytes
        self.sn_request_last_time = -2750
        self.sn_request_quiet_interval_end = 0
        self.ont_discovered = dict()
        self.global_bwmap = dict() #{time: intra_cycle_bwmap}
        self.maximum_ont_amount = int(self.config['maximum_ont_amount'])
        self.counters.ont_discovered = int()


        if self.config["transmitter_type"] == "1G":
            self.maximum_allocation_start_time = 19438
        elif self.config["transmitter_type"] == "2G":
            self.maximum_allocation_start_time = 38878

    def plan_next_act(self, time):
        self.time = time
        if self.state == 'Offline':
            self.state = 'Initial'
            time = time + self.cycle_duration
        self.counters.cycle_number = round(time / self.cycle_duration + 0.51)
        planned_s_time = self.counters.cycle_number * self.cycle_duration
        self.next_cycle_start = planned_s_time
        planned_e_time = planned_s_time + self.cycle_duration
        sig = None
        data_to_send = dict()
        data_to_send.update(self.data_to_send)
        if self.state == 'Initial':
            if planned_s_time not in self.sending_sig:
                next_bwmap = self.make_bwmap(time)
                data_to_send.update(next_bwmap)
                sig_id = '{}:{}:{}'.format(planned_s_time, self.name, planned_e_time)
                sig = Signal(sig_id, data_to_send)
                self.sending_sig[planned_s_time] = sig.id
                self.data_to_send.clear()
                return {planned_s_time: [{"dev": self, "state": "s_start", "sig": sig, "port": 0}],
                        planned_e_time: [{"dev": self, "state": "s_end", "sig": sig, "port": 0}]}
            else:
                return {}

    def make_bwmap(self, time):
        bwmap = list()
        if (time - self.sn_request_last_time) >= self.serial_number_request_interval:
            self.sn_request_last_time = self.next_cycle_start
            self.sn_request_quiet_interval_end =\
                self.next_cycle_start + self.serial_number_quiet_interval + 236 + 2*self.cycle_duration
            sn_request = True
            alloc_structure = {'Alloc-ID': 'to_all', 'Flags': 0,
                               'StartTime': 0,
                               'StopTime': self.maximum_allocation_start_time,
                               'CRC': None}
            # alloc_structure['StartTime'] = self.next_cycle_start + 236
            # alloc_structure['StopTime'] = self.sn_request_quiet_interval_end + 236
            bwmap.append(alloc_structure)
            self.global_bwmap[self.next_cycle_start] = bwmap
            self.global_bwmap[self.next_cycle_start + self.cycle_duration] = bwmap
            return {'bwmap': bwmap, 'sn_request': sn_request, 's_timestamp': self.next_cycle_start}
        elif self.config['dba_type'] == 'static':
            alloc_timer = 0 #in bytes
            max_time = self.maximum_allocation_start_time
            if self.next_cycle_start not in self.global_bwmap:
                for ont in self.ont_discovered:
                    for alloc in self.ont_discovered[ont]:
                        # if self.ont_discovered[ont][alloc] is 'Ranging':
                        if alloc_timer <= max_time:
                            #self.ont_discovered[ont][alloc] = '{}'.format(alloc_timer)
                            alloc_structure = {'Alloc-ID': alloc, 'Flags': 0,
                                               'StartTime': alloc_timer,
                                               'StopTime': None,
                                               'CRC': None}
                            #для статичного DBA выделяется интервал, обратно пропорциональный
                            #self.maximum_ont_amount - количеству ONT
                            onts = len(self.ont_discovered)
                            alloc_timer += round(max_time / onts) - self.upstream_interframe_interval #self.maximum_ont_amount)
                            alloc_structure['StopTime'] = alloc_timer
                            bwmap.append(alloc_structure)
                    alloc_timer += self.upstream_interframe_interval
                self.global_bwmap[self.next_cycle_start] = bwmap
            else:
                bwmap = self.global_bwmap[self.next_cycle_start]
            return {'bwmap': bwmap, 's_timestamp': self.next_cycle_start, 'cycle_num': self.counters.cycle_number}
        else:
            print('Unknown dba_type {}'.format(self.config['dba_type']))
            return {}

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
                self.receiving_sig.pop(rec_sig)
                if rec_sig.physics['collision']:
                    self.counters.ingress_collision += 1
                    return {}
                break
        if 'sn_response' in sig.data and self.time < self.sn_request_quiet_interval_end:
            #self.ont_discovered.append(sig.data['sn_response'])
            s_number = sig.data['sn_response']
            self.ont_discovered[s_number] = {s_number+'_0': None}
            if 'sn_ack' not in self.data_to_send:
                self.data_to_send['sn_ack'] = list()
            self.data_to_send['sn_ack'].append(s_number)
            #self.data_to_send['sn_ack'] = s_number
            sig = self.oe_transform(sig)
        #output = {"sig": sig, "delay": delay}
        else:
            self.counters.ingress_unicast += 1
            pass
        return {}#port: output}

    def export_counters(self):
        self.counters.ont_discovered = len(self.ont_discovered)
        return self.counters.export_to_console()