import json
from pon_device import Olt, Ont
from passive_optics import Splitter
from schedule_functions import upd_schedule, del_event_from_schedule
from time import sleep


class ModelScheduler:
    def __init__(self, net, algorithm):
        self.net = net
        self.onts = list()
        self.devices = dict()
        for dev in net:
            if 'OLT' in dev:
                self.olt = Olt(name=dev, config=net[dev])
                self.devices[dev] = self.olt
            elif 'ONT' in dev:
                ont = Ont(name=dev, config=net[dev])
                self.onts.append(ont)
                self.devices[dev] = ont
            elif 'Splitter' in dev:
                splitter = Splitter(name=dev, config=net[dev])
                self.devices[dev] = splitter

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
            for event in self.schedule[time]:
                local_device, local_port, sig = event()
                remote_point = self.net[local_device]['ports'][str(local_port)]
                remote_device, remote_port = remote_point.split("::")
                dev = self.devices[remote_device]
                new_port_sigs = dev.recv_signal(int(remote_port), sig)
                print(new_port_sigs)
                new_events = dict()
                for port_sig in new_port_sigs:
                    dev.plan_next_act()
                    upd_schedule(self.schedule, new_events)

            self.schedule.pop(time)
            times.remove(time)
        return True

    def interrogate_devices(self):
        new_events = dict()
        for dev_name in self.devices:
            dev = self.devices[dev_name]
            event = dev.plan_next_act(self.time)#, self.current_requests)
            #event = {evtime: [str(dev.id) + ' ' + next_cycle]}
            if event is not None:
                new_events = upd_schedule(new_events, event)
        return new_events


def main():
    net = json.load(open('./network.json'))
    print('Net description: ', net)
    sched = ModelScheduler(net, 'basic_NSC')
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
