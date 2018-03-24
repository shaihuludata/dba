import queue
from collections import OrderedDict
from signal import Signal

c_alloc = {'Alloc-ID': 1, 'Flags': 2, 'StartTime': 3, 'StopTime': 4, 'CRC': 5}
alloc_structure = OrderedDict(sorted(c_alloc.items(), key=lambda t: t[1]))

class PonDevice:

    def __init__(self, name, config):
        self.state = 'Standby'
        self.name = name
        self.config = config
        self.requests = list()
        self.cycle_duration = 125
        self.data_to_send = str()
        print('New PonDevice {}'.format(name))

    def plan_next_act(self, time):
        pass
        #data = 'nothing to send'
        #return {0: [data]}

    def send_signal(self, port=0):
        pass

    def recv_signal(self, port:int, sig:Signal):
        pass

class Olt(PonDevice):

    def plan_next_act(self, time):
        #if self.state == 'Transmitting':
        planned_time_step = round(time/self.cycle_duration + 0.51)
        planned_time = planned_time_step * self.cycle_duration
        bwmap = self.make_bwmap(self.requests)
        self.data_to_send = bwmap
        return {planned_time: [self.send_signal]}

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

    def send_signal(self, port=0):
        local_port = port
        print('sending GTC and bwmap', self.data_to_send, 'to {}'.format(local_port))
        sig = Signal(self.data_to_send)
        sig.physics['power'] = float(self.config['transmitter_power'])
        sig.physics['wavelength'] = float(self.config['transmitter_wavelength'])
        return (self.name, local_port, sig)

    def recv_signal(self, port:int, sig:Signal):
        return

class Ont(PonDevice):

    def plan_next_act(self, time):
        return {}

    def send(self, data):
        header = 'current header'
        rdata = header + data
        return rdata

    def request_bw(self):
        print('Sending req')

    def send_signal(self):
        return

    def recv_signal(self, port:int, sig:Signal):
        return