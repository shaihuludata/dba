import queue


class PonDevice:
    def __init__(self, desc, id):
        self.state = 'Standby'
        self.id = id
        self.cycle_duration = 125
        print('New PonDevice {}'.format(id))


class Olt(PonDevice):

    def make_bwmap(self):
        bwmap = 'bwmap_structure'
        return bwmap

    def calculate_next_transmission(self, time):
        data = 'some data to send on next cycle'
        return data


class Ont(PonDevice):

    def send(self, data):
        header = 'current header'
        rdata = header + data
        return rdata

    def request_bw(self):
        print('Sending req')

