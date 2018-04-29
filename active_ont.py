from active_optics import ActiveDevice
import random
from signal import Signal
from uni_traffic.traffic import Traffic

class Ont(ActiveDevice):
    # TO1 = 0 #Serial number acquisition and ranging timer
    # TO2 = 0 #POPUP timer

    def __init__(self, name, config):
        ActiveDevice.__init__(self, name, config)
        self.planned_events = dict()
        if "activation_time" in self.config:
            self.time_activation = self.config['activation_time'] * 1000
            # time_start = self.config["activation_time"]
            # time_end = time_start + 10
        self.STATE = 'Offline'
        self.range_time_delta = list()
        self.traffic_generators = dict()
        self.current_allocations = dict() #key alloc_id : value grant_size

        if 'Alloc' in config:
            for alloc_id in config['Alloc']:
                alloc_type = config['Alloc'][alloc_id]
                tg = Traffic(self.name, alloc_id, alloc_type)
                self.traffic_generators[self.name + '_' + alloc_id] = tg
                self.current_allocations[tg.id] = None
        if "0" not in config['Alloc']:
            alloc_type = 'type0'
            tg = Traffic(self.name, "0", alloc_type)
            self.current_allocations[tg.id] = None
        pass

    def plan_next_act(self, time):
        self.time = time
        planned_signals = dict()
        if len(self.planned_events) > 0:
            planned_signals.update(self.planned_events)
            self.planned_events = dict()
        if self.STATE is 'Offline' and time >= self.time_activation:
            self.STATE = 'Initial'
        if self.STATE is 'Initial':
            pass
        elif self.STATE is 'Standby':
            pass
        elif self.STATE is 'SerialNumber':
            pass
        elif self.STATE is 'Ranging':
            pass
        elif self.STATE is 'Operation':
            for tg_name in self.traffic_generators:
                tg = self.traffic_generators[tg_name]
                tg.new_message(time)
        elif self.STATE is 'POPUP':
            pass
        elif self.STATE is 'EmergencyStop':
            pass
        return planned_signals

    def request_bw(self):
        print('Sending req')

    def r_end(self, sig, port: int):
        # обработка на случай коллизии
        for rec_sig in self.receiving_sig:
            if rec_sig.id == sig.id:
                self.receiving_sig.pop(rec_sig)
                if rec_sig.physics['collision']:
                    self.counters.ingress_collision += 1
                    return {}
                break

        self.next_cycle_start = self.time + self.cycle_duration
        time = self.time
        if self.STATE == 'Offline':
            pass
        elif self.STATE == 'Initial':
            self.STATE = 'Standby'
        elif self.STATE == 'Standby':
        # delimiter value, power level mode and pre-assigned delay)
            sig = self.oe_transform(sig)
            # тут нужно из сигнала вытащить запрос SN
            if 'sn_request' in sig.data:
                # delay = random.randrange(34, 36, 1) + random.randrange(0, 50, 1)
                delay = random.randrange(0, 80, 1) + self.cycle_duration
                planned_s_time = self.next_cycle_start + delay
                planned_e_time = planned_s_time + 2
                sig_id = '{}:{}:{}'.format(planned_s_time, self.name, planned_e_time)
                resp_sig = Signal(sig_id, {}, source=self.name)
                alloc_ids = list(self.current_allocations.keys())
                resp_sig.data['sn_response'] = (self.name, alloc_ids)
                self.planned_events.update({
                    planned_s_time: [{"dev": self, "state": "s_start", "sig": resp_sig, "port": 0}],
                    planned_e_time: [{"dev": self, "state": "s_end", "sig": resp_sig, "port": 0}]
                })
            elif 'sn_ack' in sig.data:
                for alloc in sig.data['sn_ack']:
                    if alloc in self.current_allocations:
                        self.current_allocations[alloc] = 'sn_ack'
                allocs_acked = list(i for i in self.current_allocations.keys()
                                    if self.current_allocations[i] == 'sn_ack')
                if len(allocs_acked) > 0:
                    print('{} Авторизация на OLT подтверждена, allocs: {}'.format(self.name, allocs_acked))
                # Формально тут должно быть 'SerialNumber'
                # но без потери смысла для симуляции должно быть Ranging
                    self.STATE = 'Ranging'
                # print(sig)
                # output = {"sig": sig, "delay": delay}
                return {}
        elif self.STATE == 'Ranging':
            if 's_timestamp' in sig.data:
                s_timestamp = sig.data['s_timestamp']
                if len(self.range_time_delta) > 10:
                    self.range_time_delta.pop(0)
                self.range_time_delta.append(self.time - s_timestamp - self.cycle_duration)
            self.STATE = 'Operation'
        elif self.STATE == 'Operation':
            # 'Alloc-ID'
            avg_half_rtt = sum(self.range_time_delta)/len(self.range_time_delta)
            for allocation in sig.data['bwmap']:
                name = self.name
                alloc_id = allocation['Alloc-ID']
                for dev_alloc in self.current_allocations:
                    if dev_alloc == alloc_id:
                        data_to_send = dict()
                        allocation_start = allocation['StartTime']
                        allocation_stop = allocation['StopTime']
                        grant_size = allocation_stop - allocation_start
                        intra_cycle_s_start = round(8*1000000*allocation_start / self.transmitter_speed, 1)
                        intra_cycle_e_start = round(8*1000000*allocation_stop / self.transmitter_speed, 1)
                        planned_s_time = self.next_cycle_start + intra_cycle_s_start - 2*avg_half_rtt + self.cycle_duration
                        planned_e_time = self.next_cycle_start + intra_cycle_e_start - 2*avg_half_rtt + self.cycle_duration
                        planned_delta = planned_e_time - planned_s_time  # полезно для отладки
                        if planned_s_time < self.time:
                            raise Exception('Текущее время {} меньше запланированного {}'.format(self.time, planned_s_time))

                        for tg_name in self.traffic_generators:
                            tg = self.traffic_generators[tg_name]
                            if tg.id == alloc_id:
                                if len(tg.queue) == 0:
                                    break
                                else:  # len(tg.queue) > 0:
                                    packets_to_send = list()
                                    for message in tg.queue:
                                        if grant_size == 0:
                                            break
                                        send_time = time + message['interval']
                                        traf_class = message['traf_class']
                                        # if 'ONT2' in message['alloc_id'] and message['packet_num'] == 30:
                                        #     print('543')
                                        # if 'ONT2' in message['alloc_id']:
                                        #     print('765')
                                        send_size = message['size']
                                        packet = dict()
                                        packet.update(message)
                                        if grant_size >= send_size:
                                            # packets_to_send.append(packet)
                                            message['size'] = 0
                                        else:
                                            packet['size'] = grant_size
                                            message['size'] -= grant_size
                                            message['fragment_offset'] += grant_size
                                        packets_to_send.append(packet)
                                        grant_size -= packet['size']
                                        # print("planned_s_time {}, packet_id {}, size {}"
                                        #       .format(planned_s_time, packet['packet_id'], packet['size']))
                                        packet_alloc = packet['alloc_id']
                                    for packet in packets_to_send:
                                        for packet_q in tg.queue:
                                            packet_id = packet['packet_id']
                                            if packet_id == packet_q['packet_id']:
                                                if packet_q['size'] == 0:
                                                    self.traffic_generators[alloc_id].queue.remove(packet_q)
                                                    break
                                        if alloc_id not in data_to_send:
                                            data_to_send[alloc_id] = list()
                                        data_to_send[alloc_id].append(packet)
                                break
                        data_to_send.update({'cycle_num': sig.data['cycle_num']})

                        sig_id = '{}:{}:{}'.format(planned_s_time, self.name, planned_e_time)
                        if sig_id not in self.sending_sig.values():
                            self.sending_sig[planned_s_time] = sig_id
                            req_sig = Signal(sig_id, data_to_send, source=self.name)
                            if planned_s_time not in self.planned_events:
                                self.planned_events[planned_s_time] = list()
                            if planned_e_time not in self.planned_events:
                                self.planned_events[planned_e_time] = list()
                            self.planned_events[planned_s_time].append({"dev": self, "state": "s_start", "sig": req_sig, "port": 0})
                            self.planned_events[planned_e_time].append({"dev": self, "state": "s_end", "sig": req_sig, "port": 0})
                        break
        else:
            raise Exception('State {} not implemented'.format(self.STATE))
        if self.STATE != 'Offline':
            self.counters.ingress_unicast += 1
        return {}

