import queue


class PonDevice:

    def __init__(self, name):#, id):
        self.state = 'Standby'
        self.name = name
        self.cycle_duration = 125
        self.data_to_send = str()
        print('New PonDevice {}'.format(name))

    def plan_next_act(self, time, new_requests):
        pass
        #data = 'nothing to send'
        #return {0: [data]}


class Olt(PonDevice):

    def plan_next_act(self, time, new_requests):
        #if self.state == 'Transmitting':
        planned_time_step = round(time/self.cycle_duration + 0.51)
        planned_time = planned_time_step * self.cycle_duration
        bwmap = self.make_bwmap(new_requests)
        self.data_to_send = self.name + ' ' + bwmap
        return {planned_time: [self.send_signal]}

    def make_bwmap(self, requests):
        bwmap = 'bwmap_structure'
        return bwmap

    def send_signal(self):
        print('bugaga' + self.data_to_send)
        return

class Ont(PonDevice):

    def plan_next_act(self, time, new_requests):
        return {}

    def send(self, data):
        header = 'current header'
        rdata = header + data
        return rdata

    def request_bw(self):
        print('Sending req')

