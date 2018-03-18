import json
from pon_device import Olt, Ont


class ModelScheduler:
    def __init__(self, net_filename, algorithm):
        net = json.load(net_filename)
        print(net)
        desc = net['OLT']
        id = 0
        self.olt = Olt(desc, id=id)
        self.onts = list()
        for dev in net:
            if 'ONT' in dev:
                id = id + 1
                self.onts.append(Ont(net[dev], id))
        self.dba_algorithm = algorithm
        self.schedule = dict()
        self.renew_schedule(0)

    def renew_schedule(self, cur_time):
        self.time = cur_time
        new_events = self.interrogate_devices()
        for ev in new_events:
            if ev not in self.schedule:
                self.schedule.update(new_events)
            elif ev in self.schedule and self.schedule[ev] != new_events[ev]:
                self.schedule[ev].extend(new_events[ev])
            else:
                print('Планируемое событие уже есть в базе')
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
        next_cycle = self.olt.calculate_next_transmission(self.time)
        event = self.time, [next_cycle]
        events.append(event)
        return events

    def proceed_events(self, events):
        print(events)


def main():
    sched = ModelScheduler('./network.json', 'basic_NSC')
    time_horisont = 1250
    timestep = 125
    timesteps = time_horisont // timestep
    for step in range(timesteps):
        sched.proceed_schedule(step*timestep)
        sched.renew_schedule(step*timestep)


if __name__ == 'main':
    main()
