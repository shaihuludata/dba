from passive_optics import Splitter, Fiber
from active_olt import Olt
from active_ont import Ont
from observers import *
# schedule = {time : [event]}


class Schedule:
    events = dict()

    def upd_schedule(self, new_events: dict):
        start_schedule = dict()
        start_schedule.update(self.events)
        new_time_schedule = dict()
        for time in new_events:
            if time not in self.events:
                new_time_schedule.update({time: new_events[time]})
            elif self.events[time] is None:
                new_time_schedule.update({time: new_events[time]})
            else:
                old_events = self.events[time]
                events = new_events[time]
                for event in events:
                    if event not in old_events:
                        old_events.append(event)
                        self.events[time] = old_events
                    # else:
                    #     print('Планируемое событие уже есть в базе')
        self.events.update(new_time_schedule)
        if None in self.events.values():
            print('Ошибка в расписании!')

    def del_event_from_schedule(schedule, new_events):
        # if ev not in schedule:
        #     schedule.update(new_events)
        # elif ev in self.schedule and self.schedule[ev] != new_events[ev]:
        #     self.schedule[ev].extend(new_events[ev])
        # else:
        #     print('Планируемое событие уже есть в базе')
        # new_schedule = dict()
        # return new_schedule
        pass


class ModelScheduler:
    def __init__(self, net, config):
        self.net = net
        self.onts = list()
        self.devices = dict()
        self.temp_dict = dict()
        self.track = dict()
        time_horisont = config['horisont']

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
            elif 'Fiber' in dev:
                self.devices[dev] = Fiber(name=dev, config=net[dev])

        self.observers = list()
        self.traf_observers = list()
        if config["observers"]["flow"]["report"]:
            time_ranges = config["observers"]["flow"]["time_ranges"]
            self.observers.append(FlowObserver(time_ranges_to_show=time_ranges))
        if config["observers"]["power"]["report"]:
            time_ranges = config["observers"]["power"]["time_ranges"]
            self.observers.append(PhysicsObserver(time_ranges_to_show=time_ranges))
        if config["observers"]["traffic"]["report"]:
            time_ranges = config["observers"]["traffic"]["time_ranges"]
            self.observers.append(ReceivedTrafficObserver(time_ranges_to_show=time_ranges))
        if config["observers"]["IPtraffic"]["report"]:
            time_ranges = config["observers"]["IPtraffic"]["time_ranges"]
            self.observers.append(IPTrafficObserver(time_ranges_to_show=time_ranges))
        if config["observers"]["mass_traffic"]["report"]:
            time_ranges = config["observers"]["mass_traffic"]["time_ranges"]
            self.observers.append(MassTrafficObserver(time_ranges_to_show=time_ranges))
        if config["observers"]["BufferObserver"]["report"]:
            time_ranges = config["observers"]["BufferObserver"]["time_ranges"]
            self.observers.append(BufferObserver(time_ranges_to_show=time_ranges))

        # self.dba_algorithm = algorithm
        self.current_requests = list()
        self.time = -125
        self.schedule = Schedule()
        self.schedule.upd_schedule(self.interrogate_devices())
        return

    def notify_observers(self):
        for observer in self.observers:
            if observer.name in ['Traffic visualizer', 'Mass packet visualizer']:
                observer.notice(self.schedule.events[self.time], self.time)
            elif observer.name in ['BufferObserver']:
                observer.notice(self.onts, self.time)
            else:
                observer.notice(self.schedule.events, self.time)

    def make_results(self):
        for observer in self.observers:
            observer.make_results()

        for dev in self.onts:
            print('{} {}'.format(dev.name, dev.STATE))
            print(dev.counters.export_to_console())
        print('{} {}'.format(self.olt.name, self.olt.STATE))
        print(self.olt.counters.export_to_console())

    def track_the_packet(self, sched):
        for t in sched.events:
            events = sched.events[t]
            for ev in events:
                state = ev['state']
                for ont_alloc_name in ev['sig'].data:
                    if 'ONT' in ont_alloc_name:
                        ont_alloc = ev['sig'].data[ont_alloc_name]
                        for packet in ont_alloc:
                            pack_id = packet['packet_id']
                            if pack_id not in self.track:
                                self.track[pack_id] = list()
                            if (t, state) not in self.track[pack_id]:
                                self.track[pack_id].append((t, state))
        return self.track

    def proceed_schedule(self, cur_time):
        self.time = cur_time
        self.notify_observers()
        self.schedule.upd_schedule(self.interrogate_devices())
        current_events = self.schedule.events.pop(cur_time)
        # track = self.track_the_packet()
        sorted_events = list()
        # надо отсортировать, первые события должны быть 'r_end'
        for ev_state in ['defrag', 'r_end', 's_end', 'r_start', 's_start']:
            for event in current_events:
                if event['state'] == ev_state:
                    sorted_events.append(event)
        new_sched = Schedule()
        sending_sig = self.olt.sending_sig
        self.temp_dict = sorted_events
        for event in sorted_events:
            state, sig = event['state'], event['sig']
            l_dev, l_port = event['dev'], event['port']
            # if 'OLT' in l_dev.name:
            #     if state == 'r_end':
            #         print('Time {}, device {} {}, sig {}, '.format(cur_time, l_dev.name, state, sig.id))
            if state == 'r_end':
                if 'ONT' in l_dev.name or 'OLT' in l_dev.name:
                    time_sig_dict = l_dev.r_end(sig, l_port)
                    if len(time_sig_dict) > 0:
                        new_sched.upd_schedule(time_sig_dict)
                else:
                    port_sig_dict = l_dev.r_end(sig, l_port)
                    for port in port_sig_dict:
                        cur_sig = port_sig_dict[port]['sig']
                        new_event = {'dev': l_dev, 'state': 's_end',
                                     'sig': cur_sig, 'port': port}
                        delay = port_sig_dict[port]['delay']
                        new_sched.upd_schedule({cur_time + delay: [new_event]})
            elif state == 's_start':
                l_device, l_port, sig = l_dev.s_start(sig, l_port)
                r_device, r_port = self.net[l_device]['ports'][str(l_port)].split("::")
                r_dev = self.devices[r_device]
                new_event = {'dev': r_dev, 'state': 'r_start', 'sig': sig, 'port': int(r_port)}
                new_sched.upd_schedule({cur_time: [new_event]})
            elif state == 'r_start':
                port_sig_dict = l_dev.r_start(sig, l_port)
                if ('ONT' in l_dev.name or 'OLT' in l_dev.name) and len(port_sig_dict) == 1:
                    # print('Сигнал {} принимается'.format(sig.id))
                    # for port in port_sig_dict:
                    #     sig = port_sig_dict[port]['sig']
                    # continue
                    pass
                else:
                    for port in port_sig_dict:
                        new_event = {'dev': l_dev, 'state': 's_start',
                                     'sig': port_sig_dict[port]['sig'], 'port': port}
                        delay = port_sig_dict[port]['delay']
                        new_sched.upd_schedule({cur_time + delay: [new_event]})
            elif state == 's_end':
                l_device, l_port, sig = l_dev.s_end(sig, l_port)
                try:
                    r_device, r_port = self.net[l_device]['ports'][str(l_port)].split("::")
                except:
                    raise
                r_dev = self.devices[r_device]
                new_event = {'dev': r_dev, 'state': 'r_end', 'sig': sig, 'port': int(r_port)}
                new_sched.upd_schedule({cur_time: [new_event]})
            elif state == 'defrag':
                pass
            else:
                raise Exception('{} Not implemented'.format(state))
        self.schedule.upd_schedule(new_sched.events)
        return True

    def interrogate_devices(self):
        new_sched = Schedule()
        for dev_name in self.devices:
            dev = self.devices[dev_name]
            event = None
            if 'OLT' in dev.name or 'ONT' in dev.name:
                event = dev.plan_next_act(self.time)
            if event is not None:
                new_sched.upd_schedule(event)
        # track = self.track_the_packet(new_sched)
        return new_sched.events
