from active_optics import ActiveDevice
import random
from signal import Signal

class Ont(ActiveDevice):
    TO1 = 0 #Serial number acquisition and ranging timer
    TO2 = 0 #POPUP timer
    # def __init__(self, name, config):
    #     ActiveDevice.__init__(self, name, config)
    # min_onu_resp_time = 236

    def __init__(self, name, config):
        ActiveDevice.__init__(self, name, config)
        self.planned_events = dict()
        if "activation_time" in self.config:
            self.time_activation = self.config['activation_time'] * 1000
            # time_start = self.config["activation_time"]
            # time_end = time_start + 10
        if "UNI_requests" in self.config:
            self.requests = self.config['UNI_requests']
            pass
        self.state = 'Offline'
        self.range_time_delta = list()

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
            pass
            # if len(self.requests) > 0:
            #     cur_req_parameters = self.requests.pop(0)
            #     cur_req_delay_before_send = cur_req_parameters[0]
            #     cur_req_bytes_to_send = cur_req_parameters[1]
            #     planned_s_time = self.time
            #     sending_duration = 8*cur_req_bytes_to_send/self.transmitter_speed
            #     planned_e_time = planned_s_time + sending_duration
            #     self.data_to_send = {}
            #     req_sig = Signal('{}:{}:{}'.format(planned_s_time, self.name, planned_e_time), self.data_to_send)
            #     self.planned_events.update({
            #         planned_s_time: [{"dev": self, "state": "s_start", "sig": req_sig, "port": 0}],
            #         planned_e_time: [{"dev": self, "state": "s_end", "sig": req_sig, "port": 0}]})
        elif self.state is 'POPUP':
            pass
        elif self.state is 'EmergencyStop':
            pass
        return planned_signals

    def request_bw(self):
        print('Sending req')

    def s_start(self, sig, port: int):
        sig = self.eo_transform(sig)
        self.next_cycle_start = self.time + self.cycle_duration
        return self.name, port, sig

    def r_end(self, sig, port: int):
        for rec_sig in self.receiving_sig:
            if rec_sig.id == sig.id:
                self.receiving_sig.remove(rec_sig)
                break

        if self.state == 'Offline':
            pass
        elif self.state == 'Initial':
            self.state = 'Standby'
        elif self.state == 'Standby':
        # delimiter value, power level mode and pre-assigned delay)
            #тут нужно из сигнала вытащить запрос SN
            if sig.data['sn_request']:
                delay = random.randrange(34, 36, 1) + random.randrange(0, 48, 1)
                sig = self.oe_transform(sig)
                planned_s_time = self.time + delay
                planned_e_time = planned_s_time + 10
                resp_sig = Signal('{}:{}:{}'.format(planned_s_time, self.name, planned_e_time), self.data_to_send)
                resp_sig.data['sn_response'] = self.name
                self.planned_events.update({
                    planned_s_time:
                        [{"dev": self, "state": "s_start", "sig": resp_sig, "port": 0}],
                    planned_e_time:
                        [{"dev": self, "state": "s_end", "sig": resp_sig, "port": 0}]
                })
                # Формально тут должно быть 'SerialNumber'
                # но без потери смысла для симуляции должно быть Ranging
                self.state = 'Ranging'
                # print(sig)
                # output = {"sig": sig, "delay": delay}
                return {}# port: output}
        elif self.state == 'Ranging':
            if 's_timestamp' in sig.data:
                s_timestamp = sig.data['s_timestamp']
                if len(self.range_time_delta) > 10:
                    self.range_time_delta.pop(0)
                self.range_time_delta.append(self.time - s_timestamp)
            self.state = 'Operation'
        elif self.state == 'Operation':
            #'Alloc-ID'
            for allocation in sig.data['bwmap']:
                alloc_id = allocation['Alloc-ID']
                if self.name in alloc_id:
                    #TODO вот тут надо будет воткнуть поправку на RTT
                    intra_cycle_s_start = round(8*1000000 * allocation['StartTime'] / self.transmitter_speed)
                    planned_s_time = self.next_cycle_start + intra_cycle_s_start
                    intra_cycle_e_start = round(8*1000000 * allocation['StopTime'] / self.transmitter_speed)
                    planned_e_time = self.next_cycle_start + intra_cycle_e_start
                    self.data_to_send = {}
                    req_sig = Signal('{}:{}:{}'.
                                     format(planned_s_time, self.name, planned_e_time), self.data_to_send)
                    self.planned_events.update({
                        planned_s_time: [{"dev": self, "state": "s_start", "sig": req_sig, "port": 0}],
                        planned_e_time: [{"dev": self, "state": "s_end", "sig": req_sig, "port": 0}]})
            # if len(self.requests) > 0:
            #     cur_req_parameters = self.requests.pop(0)
            #     cur_req_delay_before_send = cur_req_parameters[0]
            #     cur_req_bytes_to_send = cur_req_parameters[1]
            #     sending_duration = 8*cur_req_bytes_to_send/self.transmitter_speed
        else:
            raise Exception('State {} not implemented'.format(self.state))
        return {}