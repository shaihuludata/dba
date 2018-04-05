from pon_device import PonDevice
from collections import OrderedDict
from signal import Signal
import random

c_alloc = {'Alloc-ID': 1, 'Flags': 2, 'StartTime': 3, 'StopTime': 4, 'CRC': 5}
alloc_structure = OrderedDict(sorted(c_alloc.items(), key=lambda t: t[1]))


class ActiveDevice(PonDevice):
    receiving_sig = list() #на самом деле, должна быть привязка к порту, наверное...

    def __init__(self, name, config):
        PonDevice.__init__(self, name, config)
        self.state = 'Offline'
        self.power_matrix = 0
        self.cycle_duration = 125
        self.requests = list()
        self.data_to_send = dict()
        self.device_scheduler = dict()

    def plan_next_act(self, time):
        pass
        #data = 'nothing to send'
        #return {0: [data]}

    def s_start(self, sig, port: int):
        sig = self.eo_transform(sig)
        return self.name, port, sig

    def s_end(self, sig, port: int):
        return self.name, port, sig

    def r_start(self, sig, port: int):
        if len(self.receiving_sig) == 0:
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

    serial_number_request_interval = 250
    def __init__(self, name, config):
        ActiveDevice.__init__(self, name, config)
        self.last_time_sn_request = -250

    def plan_next_act(self, time):
        if self.state == 'Offline':
            self.state = 'Initial'
            return {}
        else:
            planned_time = round(time/self.cycle_duration + 0.51) * self.cycle_duration
            bwmap = self.make_bwmap(self.requests) #bwmap пока что пустая
            self.data_to_send = {'bwmap': bwmap}
            self.data_to_send['sn_request'] =\
                (time - self.last_time_sn_request) >= self.serial_number_request_interval

            sig = Signal('{}:{}:{}'
                         .format(time, self.name, planned_time), self.data_to_send)
            if planned_time in self.device_scheduler:
                return {}
            else:
                self.device_scheduler[planned_time] = sig.id
            return {planned_time:
                        [{"dev": self, "state": "s_start", "sig": sig, "port": 0}],
                    planned_time + self.cycle_duration:
                        [{"dev": self, "state": "s_end", "sig": sig, "port": 0}]
                    }

    def make_bwmap(self, requests):
        bwmap = list()
        if self.config['dba_type'] == 'static':
            alloc_id_counter = 0
            maximum_ont_amount = self.config['maximum_ont_amount']
            for req in requests:
                allocation = OrderedDict()
                alloc_structure['Alloc-ID'] = alloc_id_counter
                alloc_structure['Flags'] = 0
                alloc_structure['StartTime'] = alloc_id_counter * 100
                alloc_structure['StopTime'] = alloc_id_counter * 100 + 100
                alloc_structure['CRC'] = 0
                allocation = alloc_structure
                bwmap.append(allocation)
                alloc_id_counter += 1
        else:
            print('Unknown dba_type {}'.format(self.config['dba_type']))
        if len(bwmap) == 0:
            bwmap.append('empty_bwmap_structure')
        return bwmap


class Ont(ActiveDevice):
    TO1 = 0 #Serial number acquisition and ranging timer
    TO2 = 0 #POPUP timer
    # def __init__(self, name, config):
    #     ActiveDevice.__init__(self, name, config)

    def plan_next_act(self, time):
        if self.state is 'Initial':
            pass
        elif self.state is 'Standby':
            if "activation_time" in self.config:
                time_start = self.config["activation_time"]
                time_end = time_start + 10
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
        return {}

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
        if self.state == 'Initial':
            self.state = 'Standby'
        elif self.state == 'Standby':
        # delimiter value, power level mode and pre-assigned delay)
            #тут нужно из сигнала вытащить запрос SN
            print(sig)
        sig = self.oe_transform(sig)
        output = {"sig": sig, "delay": self.cycle_duration}
        return {port: output}

