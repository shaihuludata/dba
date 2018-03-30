import matplotlib


class Observer:
    def __init__(self):
        self.name = 'some kind of observer'
        self.observer_result = dict()
        #{dev.name + '::' + port: [(time, sig.__dict__)]}

    def notice(self, schedule, cur_time):
        passed_schedule = {time: schedule[time] for time in schedule if time <= cur_time}

        for time in passed_schedule:
            for event in passed_schedule[time]:
                dev, state, sig, port = event['dev'], event['state'], event['sig'], str(event['port'])
                if 'OLT' in dev.name:
                    print('ку')
                point = dev.name + '::' + port
                if point in self.observer_result:
                    time_sig = self.observer_result[point]
                else:
                    time_sig = list()
                time_sig.append((time, state, sig.__dict__))
                self.observer_result[point] = time_sig
        return
