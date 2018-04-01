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
                point = dev.name + '::' + port
                if point in self.observer_result:
                    time_sig = self.observer_result[point]
                else:
                    time_sig = list()
                time_sig.append((time, state, sig.__dict__))
                self.observer_result[point] = time_sig
        return

    def make_results(self):
        import numpy as np
        import matplotlib.pyplot as plt
        import matplotlib as mp
        #mp.use('agg')

        fig = plt.figure(1, figsize=(9, 6))
        ax = fig.add_subplot(111)
        data_to_plot = [np.array([1, 2, 3]), np.array([4, 6]), np.array([5, 10])]
        bp = ax.boxplot(data_to_plot)#, capprops=dict(color="red"))

        fig.show()
        #fig.savefig('fig1.png', bbox_inches='tight')
        import time
        time.sleep(10)
