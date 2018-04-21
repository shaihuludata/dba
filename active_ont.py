from active_optics import ActiveDevice
import random
from signal import Signal
from uni_traffic.traffic import Traffic

class Ont(ActiveDevice):
    TO1 = 0 #Serial number acquisition and ranging timer
    TO2 = 0 #POPUP timer

    def __init__(self, name, config):
        ActiveDevice.__init__(self, name, config)
        self.planned_events = dict()
        if "activation_time" in self.config:
            self.time_activation = self.config['activation_time'] * 1000
            # time_start = self.config["activation_time"]
            # time_end = time_start + 10
        self.state = 'Offline'
        self.range_time_delta = list()
        self.traffic_generators = list()
        self.current_allocations = dict() #key alloc_id : value grant_size

        if 'Alloc' in config:
            for alloc_id in config['Alloc']:
                alloc_type = config['Alloc'][alloc_id]
                tg = Traffic(self.name, alloc_id, alloc_type)
                self.traffic_generators.append(tg)
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
        if self.state is 'Offline' and time >= self.time_activation:
            self.state = 'Initial'
        if self.state is 'Initial':
            pass
        elif self.state is 'Standby':
            pass
        elif self.state is 'SerialNumber':
            pass
        elif self.state is 'Ranging':
            pass
        elif self.state is 'Operation':
            for tg in self.traffic_generators:
                tg.new_message(time)
                if len(tg.queue) > 0:
                    message_parameters = tg.queue.pop(0)
                    send_time = time + message_parameters.pop('interval')
                    gem_name = message_parameters['alloc_id']
                    traf_class = message_parameters['traf_class']
                    send_size = message_parameters['size']
                    if send_time not in self.data_to_send:
                        self.data_to_send[send_time] = dict()
                    if gem_name not in self.data_to_send[send_time]:
                        self.data_to_send[send_time][gem_name] = list()
                    self.data_to_send[send_time][gem_name].append(message_parameters)

            # дальше надо удалить пустые позиции в буфере
            # TODO: обработка устаревших сообщений
            # тут надо удалить всё устаревшее из self.data_...
            # !!! перенесено в процесс работы с data...
            # for i in self.data_to_send:
            #     for j in self.data_to_send[i]:
            #         if len(self.data_to_send[i][j]) == 0:
            #             self.data_to_send[i].pop(j)
            #     if len(self.data_to_send[i]) == 0:
            #         self.data_to_send.pop(i)

        elif self.state is 'POPUP':
            pass
        elif self.state is 'EmergencyStop':
            pass
        return planned_signals

    def request_bw(self):
        print('Sending req')

    def s_start(self, sig, port: int):
        sig = self.eo_transform(sig)
        #self.next_cycle_start = self.time + self.cycle_duration
        return self.name, port, sig

    def r_end(self, sig, port: int):
        #обработка на случай коллизии
        for rec_sig in self.receiving_sig:
            if rec_sig.id == sig.id:
                self.receiving_sig.pop(rec_sig)
                if rec_sig.physics['collision']:
                    self.counters.ingress_collision += 1
                    return {}
                break

        self.next_cycle_start = self.time + self.cycle_duration
        time = self.time
        if self.state == 'Offline':
            pass
        elif self.state == 'Initial':
            self.state = 'Standby'
        elif self.state == 'Standby':
        # delimiter value, power level mode and pre-assigned delay)
            #тут нужно из сигнала вытащить запрос SN
            if 'sn_request' in sig.data:
                #delay = random.randrange(34, 36, 1) + random.randrange(0, 50, 1)
                delay = random.randrange(0, 80, 1) + self.cycle_duration
                sig = self.oe_transform(sig)
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
                sig = self.oe_transform(sig)
                # Формально тут должно быть 'SerialNumber'
                # но без потери смысла для симуляции должно быть Ranging
                self.state = 'Ranging'
                # print(sig)
                # output = {"sig": sig, "delay": delay}
                return {}
        elif self.state == 'Ranging':
            if 's_timestamp' in sig.data:
                s_timestamp = sig.data['s_timestamp']
                if len(self.range_time_delta) > 10:
                    self.range_time_delta.pop(0)
                self.range_time_delta.append(self.time - s_timestamp - self.cycle_duration)
            self.state = 'Operation'
        elif self.state == 'Operation':
            #'Alloc-ID'
            avg_half_rtt = sum(self.range_time_delta)/len(self.range_time_delta)
            data_to_send = dict()
            for allocation in sig.data['bwmap']:
                alloc_id = allocation['Alloc-ID']
                if self.name in alloc_id:
                    allocation_start = allocation['StartTime']
                    allocation_stop = allocation['StopTime']
                    grant_size = allocation_stop - allocation_start
                    intra_cycle_s_start = round(8*1000000 * allocation_start / self.transmitter_speed)
                    intra_cycle_e_start = round(8 * 1000000 * allocation_stop / self.transmitter_speed)
                    planned_s_time = self.next_cycle_start + intra_cycle_s_start - 2*avg_half_rtt + self.cycle_duration
                    planned_e_time = self.next_cycle_start + intra_cycle_e_start - 2*avg_half_rtt + self.cycle_duration
                    planned_delta = planned_e_time - planned_s_time #полезно для отладки
                    if planned_s_time < self.time:
                        raise Exception('Текущее время {}, запланированное время {}'.format(self.time, planned_s_time))

                    #self.current_allocations[alloc_id] = grant_size
                    #TODO: data_to_send надо будет наполнить из очередирования со стороны UNI ONT
                    # actual_data_to_send = {actual_time: self.data_to_send[actual_time]
                    #                        for actual_time in self.data_to_send
                    #                        if actual_time <= time}
                    while grant_size >= 0:
                        mes_time = min(self.data_to_send.keys())
                        if time >= mes_time:
                            if alloc_id in self.data_to_send[mes_time]:
                                message_list = self.data_to_send[mes_time][alloc_id]
                                if len(message_list) == 0:
                                    break
                                #фрагментация
                                if grant_size >= message_list[0]['size']:
                                    packet = message_list.pop(0)
                                    if len(self.data_to_send[mes_time][alloc_id]) == 0:
                                        self.data_to_send[mes_time].pop(alloc_id)
                                else:
                                    packet = dict()
                                    packet.update(message_list[0])
                                    packet['size'] = grant_size
                                    message_list[0]['size'] -= grant_size
                                    message_list[0]['fragment_offset'] += grant_size
                                grant_size -= packet['size']
                                print(packet)
                                data_to_send.update({packet['alloc_id']: packet})
                            else:
                                break
                            if len(self.data_to_send[mes_time]) == 0:
                                self.data_to_send.pop(time)
                        else:
                            break
                    data_to_send.update({'cycle_num': sig.data['cycle_num']})

                    sig_id = '{}:{}:{}'.format(planned_s_time, self.name, planned_e_time)
                    if sig_id not in self.sending_sig.values():
                        self.sending_sig[planned_s_time] = sig_id
                        req_sig = Signal(sig_id, data_to_send, source=self.name)
                        self.planned_events.update({
                            planned_s_time: [{"dev": self, "state": "s_start", "sig": req_sig, "port": 0}],
                            planned_e_time: [{"dev": self, "state": "s_end", "sig": req_sig, "port": 0}]})
        else:
            raise Exception('State {} not implemented'.format(self.state))
        if self.state != 'Offline':
            self.counters.ingress_unicast += 1
        return {}

