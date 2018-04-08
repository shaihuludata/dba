from pon_device import PonDevice
from collections import OrderedDict
from signal import Signal
import random

c_alloc = {'Alloc-ID': 1, 'Flags': 2, 'StartTime': 3, 'StopTime': 4, 'CRC': 5}
alloc_structure = OrderedDict(sorted(c_alloc.items(), key=lambda t: t[1]))
dumb_event = {'dev': None, 'state': 'dumb_event', 'sig': None, 'port': None}

class ActiveDevice(PonDevice):
    def __init__(self, name, config):
        PonDevice.__init__(self, name, config)
        self.state = 'Offline'
        self.power_matrix = 0
        self.cycle_duration = 125
        self.requests = list()
        self.data_to_send = dict()
        self.device_scheduler = dict()
        # TODO: в следующей версии, предусмотреть вместо списка словарь порт: список сигналов
        # либо в дальнейшем перенести мониторинг коллизий на наблюдателя контрольных точек
        self.receiving_sig = list()
        self.time = 0

    def plan_next_act(self, time):
        self.time = time
        pass
        #data = 'nothing to send'
        #return {0: [data]}

    def s_start(self, sig, port: int):
        sig = self.eo_transform(sig)
        return self.name, port, sig

    def s_end(self, sig, port: int):
        return self.name, port, sig

    def r_start(self, sig, port: int):
        if len(self.receiving_sig) > 0:
            print('{} ИНТЕРФЕРЕНЦИОННАЯ КОЛЛИЗИЯ на порту {}!!!'
                  .format(self.name, port))
        self.receiving_sig.append(sig)
        output = {"sig": sig, "delay": self.cycle_duration}
        return {port: output}

    def r_end(self, sig, port: int):
        self.receiving_sig.remove(sig)
        sig = self.oe_transform(sig)
        output = {"sig": sig, "delay": self.cycle_duration}
        return {port: output}

    def eo_transform(self, sig):
        optic_parameters = {'power': float(self.config['transmitter_power']),
                            'wavelength': float(self.config['transmitter_wavelength'])}
        if sig.physics['type'] == 'electric':
            sig.physics['type'] = 'optic'
        else:
            raise Exception
        sig.physics.update(optic_parameters)
        return sig

    def oe_transform(self, sig):
        optic_parameters = {}
        if sig.physics['type'] == 'optic':
            sig.physics['type'] = 'electric'
        else:
            raise Exception
        sig.physics.update(optic_parameters)
        return sig


class Olt(ActiveDevice):

    serial_number_quiet_interval = 200

    def __init__(self, name, config):
        ActiveDevice.__init__(self, name, config)
        self.serial_number_request_interval = self.config['sn_request_interval']
        self.sn_request_last_time = -2250
        self.sn_request_quiet_interval_end = 0
        self.ont_discovered = dict()
        self.next_cycle_start = 0

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
            self.sn_request_quiet_interval_end = self.next_cycle_start + self.serial_number_quiet_interval + 236
            sn_request = True
            alloc_structure['Alloc-ID'] = 'to_all'
            alloc_structure['Flags'] = 0
            alloc_structure['StartTime'] = self.next_cycle_start + 236
            alloc_structure['StopTime'] = self.sn_request_quiet_interval_end + 236
            allocation = alloc_structure
            bwmap.append(allocation)
        elif self.config['dba_type'] == 'static':
            alloc_id_counter = 0
            maximum_ont_amount = self.config['maximum_ont_amount']
            for req in requests:
                allocation = OrderedDict()
                alloc_structure['Alloc-ID'] = alloc_id_counter
                alloc_structure['Flags'] = 0
                alloc_structure['StartTime'] = alloc_id_counter * 100
                alloc_structure['StopTime'] = alloc_id_counter * 100 + 1001
                alloc_structure['CRC'] = 0
                allocation = alloc_structure
                bwmap.append(allocation)
                alloc_id_counter += 1
        else:
            print('Unknown dba_type {}'.format(self.config['dba_type']))
        return {'bwmap': bwmap, 'sn_request': sn_request}

    def r_start(self, sig, port: int):
        self.receiving_sig.append(sig)
        if len(self.receiving_sig) > 1:
            print('{} ИНТЕРФЕРЕНЦИОННАЯ КОЛЛИЗИЯ на порту {}!!!'.format(self.name, port))
            sig.physics['collision'] = True
            for rec_sig in self.receiving_sig:
                rec_sig.physics['collision'] = True
            print('')
        output = {"sig": sig, "delay": self.cycle_duration}
        return {port: output}

    def r_end(self, sig, port: int):
        for rec_sig in self.receiving_sig:
            if rec_sig.id == sig.id:
                self.receiving_sig.remove(rec_sig)
                if rec_sig.physics['collision']:
                    return {}
                break
        if 'sn_response' in sig.data and self.time < self.sn_request_quiet_interval_end:
            #self.ont_discovered.append(sig.data['sn_response'])
            self.ont_discovered[sig.data['sn_response']] = None
            sig = self.oe_transform(sig)
        #output = {"sig": sig, "delay": delay}
        return {}#port: output}


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
        self.state = 'Offline'

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
        elif self.state is 'POPUP':
            pass
        elif self.state is 'EmergencyStop':
            pass
        return planned_signals

    def request_bw(self):
        print('Sending req')

    # def s_start(self, sig, port:int):
    #
        # elif self.state is 'SerialNumber':
        #     pass
        # elif self.state is 'Ranging':
        #     pass
        # elif self.state is 'Operation':
        #     pass
        # elif self.state is 'POPUP':
        #     pass
        # elif self.state is 'EmergencyStop':
        #     pass

    # output = {"sig": sig, "delay": self.cycle_duration}
    # return {port: output}

    def r_end(self, sig, port: int):
        for rec_sig in self.receiving_sig:
            if rec_sig.id == sig.id:
                self.receiving_sig.remove(rec_sig)
                break
        if self.state == 'Initial':
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
            print('')
        return {}
