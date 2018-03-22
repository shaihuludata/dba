
#schedule = {time : [event]}

def upd_schedule(schedule:dict, ev:dict):
    for time in ev.keys():
        if time not in schedule:
            schedule.update(ev)
        else:
            old_events = schedule[time]
            new_events = ev[time]
            for event in new_events:
                if event not in old_events:
                    result_events = old_events.append(event)
                    schedule[time] = result_events
                else:
                    print('Планируемое событие уже есть в базе')
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

