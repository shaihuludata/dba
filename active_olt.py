from active_optics import ActiveDevice
from collections import OrderedDict
from signal import Signal
import copy
from dba import DbaStatic, DbaStaticAllocs, DbaSR, DbaTM, DbaTM_extra, DbaTM_linear
from sympy import Interval, Union, EmptySet


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
        self.sn_request_last_time = 0 - self.serial_number_request_interval + 250
        self.sn_request_quiet_interval_end = 0
        self.maximum_ont_amount = int(self.config['maximum_ont_amount'])
        self.counters.number_of_ont = int()
        self.defragmentation_buffer = dict()

        dba_config = dict()
        # self.upstream_interframe_interval = self.config['upstream_interframe_interval']  # 10 # in bytes
        for dba_par in ["cycle_duration", "transmitter_type",
                        'maximum_allocation_start_time', 'upstream_interframe_interval']:
            if dba_par in config:
                dba_config[dba_par] = config[dba_par]

        if config['dba_type'] == 'static':
            self.dba = DbaStatic(dba_config)
        elif config['dba_type'] == 'static_allocs':
            self.dba = DbaStaticAllocs(dba_config)
        elif config['dba_type'] == 'traffic_monitoring':
            self.dba = DbaTM(dba_config)
        elif config['dba_type'] == 'traffic_monitoring_extra':
            self.dba = DbaTM_extra(dba_config)
        elif config['dba_type'] == 'DbaTM_linear':
            self.dba = DbaTM_linear(dba_config)
        elif config['dba_type'] == 'status_report':
            self.dba = DbaSR(dba_config)

    def plan_next_act(self, time):
        self.time = time
        if self.STATE == 'Offline':
            self.STATE = 'Initial'
            time = time + self.cycle_duration
        self.counters.cycle_number = round(time / self.cycle_duration + 0.51)
        planned_s_time = self.counters.cycle_number * self.cycle_duration
        self.dba.next_cycle_start = planned_s_time
        planned_e_time = planned_s_time + self.cycle_duration
        sig = None
        data_to_send = dict()
        data_to_send.update(self.data_to_send)
        # if self.STATE == 'Initial':
        if planned_s_time not in self.sending_sig:
            next_bwmap = self.make_bwmap(time)
            data_to_send.update(next_bwmap)
            sig_id = '{}:{}:{}'.format(planned_s_time, self.name, planned_e_time)
            sig = Signal(sig_id, data_to_send, source=self.name)
            self.sending_sig[planned_s_time] = sig.id
            self.data_to_send.clear()
            return {planned_s_time: [{"dev": self, "state": "s_start", "sig": sig, "port": 0}],
                    planned_e_time: [{"dev": self, "state": "s_end", "sig": sig, "port": 0}]}
        else:
            return {}

    def make_bwmap(self, time):
        if (time - self.sn_request_last_time) >= self.serial_number_request_interval:
            sn_request = True
            self.sn_request_last_time = self.dba.next_cycle_start
            self.sn_request_quiet_interval_end = \
                self.dba.next_cycle_start + self.serial_number_quiet_interval + 236 + 2 * self.cycle_duration
            bwmap = self.dba.sn_request()
            return {'bwmap': bwmap, 'sn_request': sn_request, 's_timestamp': self.dba.next_cycle_start}
        else:
            bwmap = self.dba.bwmap(cur_time=time)
            return {'bwmap': bwmap, 's_timestamp': self.dba.next_cycle_start, 'cycle_num': self.counters.cycle_number}

    def r_end(self, sig, port: int):
        ret = dict()
        # обработка интерференционной коллизии
        # каждый принимаемый сигнал должен быть помечен как коллизирующий
        for rec_sig in self.receiving_sig:
            if rec_sig.id == sig.id:
                self.receiving_sig.pop(rec_sig)
                if rec_sig.physics['collision']:
                    self.counters.ingress_collision += 1
                    return {}
                break

        sig = self.oe_transform(sig)
        # проверка на содержание ответов на запросы регистрации в сообщении
        if 'sn_response' in sig.data and self.time < self.sn_request_quiet_interval_end:
            s_number = sig.data['sn_response'][0]
            allocs = sig.data['sn_response'][1]
            self.dba.register_new_ont(s_number, allocs)
            self.counters.number_of_ont = len(self.dba.ont_discovered)
            if 'sn_ack' not in self.data_to_send:
                self.data_to_send['sn_ack'] = list()
            self.data_to_send['sn_ack'].extend(allocs)
            # output = {"sig": sig, "delay": delay}
            return {}
        # нормальный приём сообщения
        else:
            for alloc in sig.data:
                if 'ONT' in alloc:
                    for packet in sig.data[alloc]:
                        packet_id = packet['packet_id']
                        if packet_id not in self.defragmentation_buffer:
                            self.defragmentation_buffer[packet_id] = list()
                        self.defragmentation_buffer[packet_id].append(packet)
                    self.dba.register_packet(alloc, sig.data[alloc])
            ret = self.defragmentation()
            # набор пакетов после дефрагментации регистрируется в планировщике как событие типа "defrag"
            return ret

    def defragmentation(self):
        # дефрагментация накопленных в буффере пакетов
        ret = dict()
        ids_to_delete_from_buffer = list()
        for pack in self.defragmentation_buffer:
            fragments = self.defragmentation_buffer[pack]
            defragmented = EmptySet()
            for fragment in fragments:
                cur_start = int(fragment['fragment_offset'])
                cur_end = int(cur_start + fragment['size'])
                total_size = int(fragment['total_size'])
                if cur_start == 0:
                    cur_fragment = Interval(cur_start, cur_end)
                else:
                    cur_fragment = Interval.Lopen(cur_start, cur_end)
                if defragmented.intersect(cur_fragment) is EmptySet():
                    defragmented = defragmented.union(cur_fragment)
                else:
                    raise Exception('Ошибка дефрагментации')
                if defragmented.measure == total_size:
                    # if self.time not in self.received_packets:
                    #     self.received_packets[self.time] = list()
                    # self.received_packets[self.time].append(defragmented)
                    self.counters.ingress_unicast += 1
                    if self.time not in ret:
                        ret[self.time] = list()
                    fragment['fragment_offset'] = 0
                    fragment['size'] = total_size
                    defrag_packet = dict()
                    defrag_packet.update(fragment)
                    ret[self.time].append({"dev": self, "state": "defrag", "sig": defrag_packet, "port": 0})
                    ids_to_delete_from_buffer.append(fragment['packet_id'])
        # теперь надо удалить из self.defragmentation_buffer всё, что похоже на 'packet_id'
        for id in ids_to_delete_from_buffer:
            self.defragmentation_buffer.pop(id)
        return ret

    def export_counters(self):
        # self.counters.number_of_ont = len(self.dba.ont_discovered)
        return self.counters.export_to_console()

