import json
from pon_device import Olt, Ont


class ModelScheduler:
    def __init__(self, net_filename, algorithm):
        net = json.load(net_filename)
        print(net)
        olt_desc = net['OLT']
        self.olt = Olt(olt_desc)
        self.onts = list()
        for dev in net:
            if 'ONT' in dev:
                self.onts.append(Ont(net[dev]))
        self.dba_algorithm = algorithm
        self.schedule = dict()

    def renew_schedule(self):
        new_events = self.interrogate_devices()
        for ev in new_events:
            if ev[0] not in self.schedule:
                self.schedule.update(new_events)
            else:
                self.schedule
        return True

    def proceed_schedule(self, cur_time):
        self.time = cur_time
        for time in self.schedule:
            if time <= cur_time:
                self.proceed_events(self.schedule[time])
                self.schedule.pop(time)
        return True

    def interrogate_devices(self):
        events = list()
        #event = self.olt.calculate_transmission()
        event = self.time + 40, '123'
        events.append(event)
        return events

    def proceed_events(self, events):
        print(events)

def main():
    sched = ModelScheduler('./network.json', 'basic_NSC')
    time_horisont = 100
    timestep = 5
    timesteps = time_horisont // timestep
    for step in range(timesteps):
        sched.proceed_schedule(step*timestep)
        sched.renew_schedule()


if __name__ == 'main':
    main()
