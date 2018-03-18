import json
from pon_device import Olt, Ont


class Schedule:
    def __init__(self):
        times = list()
        events = dict()

    def upd_event(self, ev):
        print('here some code will be')


class ModelScheduler:
    def __init__(self, net_filename, algorithm):
        net = json.load(open(net_filename))
        print(net)
        desc = net['OLT']
        devid = 0
        self.olt = Olt(desc, id=devid)
        self.onts = list()

        for dev in net:
            if 'ONT' in dev:
                devid = devid + 1
                self.onts.append(Ont(net[dev], devid))
        self.devices = [self.olt]
        self.devices.extend(self.onts)

        self.dba_algorithm = algorithm
        self.schedule = dict()
        self.current_requests = list()
        self.renew_schedule(0)
        self.time = 0

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
        times = list()
        for time in self.schedule:
            if time <= cur_time:
                times.append(time)

        for t in range(len(times)):
            print(self.schedule)
            self.proceed_events(self.schedule[min(times)])
            self.schedule.pop(min(times))
            times.remove(min(times))
        return True

    def interrogate_devices(self):
        events = dict()
        for dev in self.devices:
            next_cycle = dev.calculate_next_transmission(self.time, self.current_requests)
            evtime = self.time + 100
            event = {evtime: [str(dev.id) + ' ' + next_cycle]}
            if evtime not in self.schedule:
                self.schedule.update(event)
            elif evtime in self.schedule and self.schedule[evtime] != event[evtime]:
                self.schedule[evtime].extend(event[evtime])
        return events

    def proceed_events(self, events):
        print(' ')


def main():
    sched = ModelScheduler('./network.json', 'basic_NSC')
    time_horisont = 300
    timestep = 125
    timesteps = time_horisont // timestep
    for step in range(timesteps):
        cur_time = step*timestep
        sched.proceed_schedule(cur_time)
        sched.renew_schedule(cur_time)


if __name__ == '__main__':
    main()
