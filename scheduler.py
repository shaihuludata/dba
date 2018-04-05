from passive_optics import Splitter, Fiber
from active_optics import Olt, Ont
from observers import Observer
#schedule = {time : [event]}


class Schedule:
    events = dict()

    def upd_schedule(self, new_events:dict):
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
    def __init__(self, net):
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
            elif 'Fiber' in dev:
                self.devices[dev] = Fiber(name=dev, config=net[dev])

        self.observers = list()
        self.observers.append(Observer())

        # self.dba_algorithm = algorithm
        self.current_requests = list()
        self.time = -125
        self.schedule = Schedule()
        self.schedule.upd_schedule(self.interrogate_devices())
        return

    def notify_observers(self):
        for observer in self.observers:
            observer.notice(self.schedule.events, self.time)

    def make_results(self):
        for observer in self.observers:
            observer.make_results()

    def proceed_schedule(self, cur_time):
        self.time = cur_time
        self.notify_observers()
        self.schedule.upd_schedule(self.interrogate_devices())
        current_events = self.schedule.events.pop(cur_time)
        new_sched = Schedule()
        for event in current_events:
            state, sig = event['state'], event['sig']
            l_dev, l_port = event['dev'], event['port']
            print('{} sig, Time {} device {} {}'.format(sig.id, cur_time, l_dev.name, state))
            # if 'Fiber' in l_dev.name:
            #     print('')
            if state == 's_start':
                if 'OLT' in l_dev.name:
                    print('')
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
                    continue
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
            elif state == 'r_end':
                port_sig_dict = l_dev.r_end(sig, l_port)
                if ('ONT' in l_dev.name or 'OLT' in l_dev.name) and len(port_sig_dict) == 1:
                    for port in port_sig_dict:
                        sig = port_sig_dict[port]['sig']
                        if sig.physics['type'] == 'electric':
                            print('Сигнал {} доставлен и принят {}'.format(sig.id, l_dev.name))
                        new_event = {'dev': l_dev, 'state': 's_start',
                                     'sig': port_sig_dict[port]['sig'], 'port': port}
                        delay = port_sig_dict[port]['delay']
                        new_sched.upd_schedule({cur_time + delay: [new_event]})
                else:
                    for port in port_sig_dict:
                        # r_device, r_port = self.net[l_dev.name]['ports'][str(port)].split("::")
                        # r_dev = self.devices[r_device]
                        new_event = {'dev': l_dev, 'state': 's_end',
                                     'sig': port_sig_dict[port]['sig'], 'port': port}
                        delay = port_sig_dict[port]['delay']
                        new_sched.upd_schedule({cur_time + delay: [new_event]})
            else:
                raise Exception('{} Non implemented'.format(state))
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
        return new_sched.events
