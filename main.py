import json
from pon_device import Olt, Ont
from schedule_functions import upd_schedule, del_event_from_schedule
from time import sleep

class ModelScheduler:
    def __init__(self, net_filename, algorithm):
        net = json.load(open(net_filename))
        print(net)
        self.onts = list()

        for dev in net:
            if 'OLT' in dev:
                self.olt = Olt(name=dev)#, id=devid)
            elif 'ONT' in dev:
                self.onts.append(Ont(name=dev))#, devid))
        self.devices = [self.olt]
        self.devices.extend(self.onts)

        self.dba_algorithm = algorithm
        self.schedule = dict()
        self.current_requests = list()
        self.time = 0

    def renew_schedule(self, cur_time):
        self.time = cur_time
        new_events = self.interrogate_devices()
        #for ev in new_events:
        self.schedule = upd_schedule(self.schedule, new_events)
        return True

    def proceed_schedule(self, cur_time):
        self.time = cur_time
        times = list()
        for time in self.schedule:
            if time <= cur_time:
                times.append(time)

        for t in range(len(times)):
            time = min(times)
            self.proceed_events(self.schedule[time])
            self.schedule.pop(time)
            times.remove(time)
        return True

    def interrogate_devices(self):
        new_events = dict()
        for dev in self.devices:
            event = dev.plan_next_act(self.time, self.current_requests)
            #event = {evtime: [str(dev.id) + ' ' + next_cycle]}
            new_events = upd_schedule(new_events, event)
        return new_events

    def proceed_events(self, events):
        for ev in events:
            ev()


def main():
    sched = ModelScheduler('./network.json', 'basic_NSC')
    time_horisont = 500
    timestep = 125
    timesteps = time_horisont // timestep
    for step in range(timesteps):
        cur_time = step*timestep
        print('time: {}'.format(cur_time))
        print(sched.schedule)
        sched.proceed_schedule(cur_time)
        sched.renew_schedule(cur_time)
        sleep(1)


if __name__ == '__main__':
    main()
