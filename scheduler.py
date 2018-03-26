from passive_optics import Splitter
from active_optics import Olt, Ont
#schedule = {time : [event]}


def upd_schedule(schedule:dict, ev:dict):
    start_schedule = dict()
    start_schedule.update(schedule)
    new_time_schedule = dict()
    if None in schedule.values():
        print('вот оно')
    for time in ev:
        if time not in schedule:
            new_time_schedule.update({time: ev[time]})
        elif schedule[time] is None:
            new_time_schedule.update({time: ev[time]})
        else:
            old_events = schedule[time]
            new_events = ev[time]
            for event in new_events:
                if event not in old_events:
                    #result_events = old_events.append(event)
                    old_events.append(event)
                    schedule[time] = old_events
                else:
                    print('Планируемое событие уже есть в базе')
    schedule.update(new_time_schedule)
    if None in schedule.values():
        print('вот оно')
    return schedule

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
        self.renew_schedule(-20)
        self.current_requests = list()
        self.time = 0

    def renew_schedule(self, cur_time):
        self.time = cur_time
        new_events = self.interrogate_devices()
        #for ev in new_events:
        self.schedule = upd_schedule(self.schedule, new_events)
        return True

    def proceed_schedule(self, cur_time):
        current_events = self.schedule.pop(cur_time)
        for event in current_events:
            state, sig = event['state'], event['sig']
            l_dev, l_port = event['dev'], event['port']
            if state == 's_start':
                l_device, l_port, sig = l_dev.s_start(sig, l_port)
                print('Time {} device {} {} sig {}'.format(cur_time, l_dev.name, state, sig.id))
                r_device, r_port = self.net[l_device]['ports'][str(l_port)].split("::")
                r_dev = self.devices[r_device]
                #r_port_sig_dict = r_dev.r_start(sig, r_port)
                new_event = {'dev': r_dev,
                             'state': 'r_start',
                             'sig': sig,
                             'port': int(r_port)}
                self.schedule = upd_schedule(self.schedule,
                                         {cur_time: [new_event]})
            elif state == 'r_start':
                port_sig_dict = l_dev.r_start(sig, l_port)
                print('Time {} device {} {} sig {}'.format(cur_time, l_dev.name, state, sig.id))
                if len(port_sig_dict) == 1:
                    for port in port_sig_dict:
                        sig = port_sig_dict[port]['sig']
                        if 'ONT' in l_dev.name or 'OLT' in l_dev.name:
                            #print('Сигнал {} принимается'.format(sig.id))
                            continue
                        else:
                            new_event = {'dev': l_dev,
                                         'state': 's_start',
                                         'sig': port_sig_dict[port]['sig'],
                                         'port': port}
                            delay = port_sig_dict[port]['delay']
                            self.schedule = upd_schedule(self.schedule,
                                                         {cur_time + delay: [new_event]})
                else:
                    for port in port_sig_dict:
                        new_event = {'dev': l_dev,
                                     'state': 's_start',
                                     'sig': port_sig_dict[port]['sig'],
                                     'port': port}
                        delay = port_sig_dict[port]['delay']
                        self.schedule = upd_schedule(self.schedule,
                                                     {cur_time + delay: [new_event]})
            elif state == 's_end':
                l_device, l_port, sig = l_dev.s_end(sig, l_port)
                print('Time {} device {} {} sig {}'.format(cur_time, l_dev.name, state, sig.id))
                try:
                    r_device, r_port = self.net[l_device]['ports'][str(l_port)].split("::")
                except:
                    raise
                r_dev = self.devices[r_device]
                # r_port_sig_dict = r_dev.r_start(sig, r_port)
                new_event = {'dev': r_dev,
                             'state': 'r_end',
                             'sig': sig,
                             'port': int(r_port)}
                self.schedule = upd_schedule(self.schedule,
                                             {cur_time: [new_event]})
            elif state == 'r_end':
                port_sig_dict = l_dev.r_start(sig, l_port)
                if len(port_sig_dict) == 1:
                    for port in port_sig_dict:
                        sig = port_sig_dict[port]['sig']
                        if sig.physics['type'] == 'electric':
                            print('Сигнал {} доставлен и принят {}'.format(sig.id, l_dev.name))
            else:
                raise Exception('{} Non implemented'.format(state))
        return True

    def interrogate_devices(self):
        new_events = dict()
        for dev_name in self.devices:
            dev = self.devices[dev_name]
            event = None
            if 'OLT' in dev.name: #'ONT' in dev.name or
                event = dev.plan_next_act(self.time)#, self.current_requests)

            #event = {evtime: [str(dev.id) + ' ' + next_cycle]}
            if event is not None:
                new_events = upd_schedule(new_events, event)
        return new_events

