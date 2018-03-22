import queue


class PonDevice:

    def __init__(self, name):#, id):
        self.state = 'Standby'
        self.name = name
        self.cycle_duration = 125
        print('New PonDevice {}'.format(name))

    def plan_next_act(self, time, new_requests):
        pass
        #data = 'nothing to send'
        #return {0: [data]}


class Olt(PonDevice):

    def plan_next_act(self, time, new_requests):
        #if self.state == 'Transmitting':
        planned_time = round(time/self.cycle_duration + 0.5) * self.cycle_duration
        bwmap = self.make_bwmap(new_requests)
        data = self.name + ' ' + bwmap
        return {planned_time: [data]}

    def make_bwmap(self, requests):
        bwmap = 'bwmap_structure'
        return bwmap


class Ont(PonDevice):

    def plan_next_act(self, time, new_requests):
        return {-1: []}

    def send(self, data):
        header = 'current header'
        rdata = header + data
        return rdata

    def request_bw(self):
        print('Sending req')

