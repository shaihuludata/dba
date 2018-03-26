from pon_device import PonDevice
from collections import OrderedDict
from signal import Signal

c_alloc = {'Alloc-ID': 1, 'Flags': 2, 'StartTime': 3, 'StopTime': 4, 'CRC': 5}
alloc_structure = OrderedDict(sorted(c_alloc.items(), key=lambda t: t[1]))


class ActiveDevice(PonDevice):
    def __init__(self, name, config):
        self.name = name
        self.config = config
        self.state = 'Standby'
        self.power_matrix = 0
        self.cycle_duration = 125
        self.requests = list()
        self.data_to_send = str()

    def plan_next_act(self, time):
        pass
        #data = 'nothing to send'
        #return {0: [data]}

    def s_start(self, sig, l_port=0):
        sig = self.eo_transform(sig)
        return (self.name, l_port, sig)

    def s_end(self, sig, port: int):
        return (self.name, port, sig)

    def r_start(self, sig, port: int):
        output = {"sig": sig, "delay": self.cycle_duration}
        return {port: output}

    def r_end(self, sig, port: int):
        sig = self.oe_transform(sig)
        output = {"sig": sig, "delay": self.cycle_duration}
        return {}

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

    # def __init__(self, name, config):
    #     super(ActiveDevice, self).__init__()

    def plan_next_act(self, time):
        #if self.state == 'Transmitting':
        planned_time = round(time/self.cycle_duration + 0.51) * self.cycle_duration
        bwmap = self.make_bwmap(self.requests) #bwmap пока что пустая
        self.data_to_send = bwmap
        sig = Signal('{}:{}:{}'.format(time, self.name, planned_time), self.data_to_send)
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

    # def r_start(self, sig, port:int):
    #     return


class Ont(ActiveDevice):

    def plan_next_act(self, time):
        return {}

    def send(self, data):
        header = 'current header'
        rdata = header + data
        return rdata

    def request_bw(self):
        print('Sending req')

    # def s_start(self, sig, port:int):
    #     return

