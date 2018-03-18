import queue


class PonDevice:
    def __init__(self, desc, id):
        self.state = 'Standby'
        self.id = id
        self.cycle_duration = 125
        print('New PonDevice {}'.format(id))

    def calculate_next_transmission(self, time, new_requests):
        data = 'some data to send on next cycle'
        return data


class Olt(PonDevice):

    def make_bwmap(self):
        bwmap = 'bwmap_structure'
        return bwmap


class Ont(PonDevice):

    def send(self, data):
        header = 'current header'
        rdata = header + data
        return rdata

    def request_bw(self):
        print('Sending req')

