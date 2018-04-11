import matplotlib
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mp
# mp.use('agg')
import time


class FlowObserver:

    def __init__(self, time_ranges_to_show):
        self.name = 'some kind of observer'
        self.observer_result = dict()
        # {dev.name + '::' + port: [(time, sig.__dict__)]}
        if not time_ranges_to_show:
            self.time_ranges_to_show = [[1000, 2000]]
        else:
            self.time_ranges_to_show = time_ranges_to_show

        self.time_horisont = 0
        for time_range in self.time_ranges_to_show:
            new_horizont = max(time_range)
            if self.time_horisont < new_horizont:
                self.time_horisont = new_horizont

    def notice(self, schedule, cur_time):
        passed_schedule = dict()
        for time_range in self.time_ranges_to_show:
            passed_schedule.update({time: schedule[time] for time in schedule
                                    if (time in range(time_range[0], time_range[1])) and (time <= cur_time)})

        for ev_time in passed_schedule:
            for event in passed_schedule[ev_time]:
                dev, state, sig, port = event['dev'], event['state'], event['sig'], event['port']
                if event['state'] in ['s_start', 's_end', 'r_start', 'r_end']:
                    point = dev.name + '::' + str(port)
                    if point in self.observer_result:
                        time_sig = self.observer_result[point]
                    else:
                        time_sig = list()
                    time_sig.append({'time': ev_time, 'state': state, 'sig': sig.__dict__})
                    self.observer_result[point] = time_sig
        return

    def cook_result_for_dev(self, dev):
        data = list()
        for point in self.observer_result:
            if dev in point:
                for ev_start in self.observer_result[point]:
                    if ev_start['state'] is 's_start':
                        sig_id = ev_start['sig']['id']
                        t_start = ev_start['time']
                        for ev_end in self.observer_result[point]:
                            if ev_end['state'] is 's_end':
                                if ev_end['sig']['id'] == sig_id:
                                    t_end = ev_end['time']
                                    break
                        if type(t_start) is int and type(t_end) is int:
                            data.append([t_start, t_end])
                        else:
                            print('Сигнал {} не имеет завершающего события'.format(sig_id))
                    #data = self.observer_result[point]
        return data

    def cook_result(self, dev_list):
        points_data = dict()
        event_sequence = {'s_start': 's_end', 'r_start': 'r_end'}
        for dev in dev_list:
            for point in self.observer_result:
                s_data, r_data = list(), list()
                if dev in point:
                    for ev_start in self.observer_result[point]:
                        for ev_start_name in event_sequence:
                            ev_end_name = event_sequence[ev_start_name]
                            if ev_start['state'] is ev_start_name:
                                sig_id = ev_start['sig']['id']
                                t_start = ev_start['time']
                                for ev_end in self.observer_result[point]:
                                    if ev_end['state'] is ev_end_name:
                                        if ev_end['sig']['id'] == sig_id:
                                            t_end = ev_end['time']
                                            break
                                if type(t_start) in [int, float]:
                                    if type(t_end) in [int, float]:
                                        if ev_start_name == 's_start':
                                            s_data.append([t_start, t_end])
                                        elif ev_start_name == 'r_start':
                                            r_data.append([t_start, t_end])
                                    else:
                                        print('Сигнал {} не имеет завершающего события'.format(sig_id))
                        #data = self.observer_result[point]
                    # upd_dict = dict()
                    # for data in [s_data, r_data]
                    points_data.update({point+'_snd': s_data, point+'_rec': r_data})
                    break
        actual_dict = dict()
        for point in points_data:
            if len(points_data[point]) > 0:
                actual_dict[point] = points_data[point]
        points_data = actual_dict
        return points_data

    def make_results(self):
        fig = plt.figure(1, figsize=(15, 15))
        fig.show()
        ax = fig.add_subplot(111)
        devs_to_watch = ['OLT', 'ONT1', 'ONT2', 'ONT3', 'ONT4']
        #data_to_plot = self.cook_result_for_dev('OLT')  # [[1, 3], [4, 6], [5, 10]]
        data_to_plot = self.cook_result(devs_to_watch)  # [[1, 3], [4, 6], [5, 10]]
        number_of_events_per_point = list()
        #эта переменная нужна чтобы как-то размещать пустые боксы с сохранением масштаба графика
        #среди всех событий находится минимальная временная точка, она будет низом графика
        min_time_moment = self.time_horisont
        for i in data_to_plot.values():
            number_of_events_per_point.append(len(i))
            for j in i:
                if min_time_moment > min(j):
                    min_time_moment = min(j)
        horisont_event_data = max(number_of_events_per_point)

        for point in data_to_plot:
            for i in range(horisont_event_data - len(data_to_plot[point])):
                data_to_plot[point].append([min_time_moment, min_time_moment])

        points_to_watch = list(data_to_plot.keys())
        data_sorted_by_time = map(list, zip(*data_to_plot.values()))
        for dtp in data_sorted_by_time:
            ax.boxplot(dtp)
            ax.set_xticklabels(points_to_watch)
            fig.canvas.draw()
            #time.sleep(1)
        fig.canvas.draw()
        # time.sleep(3)
        fig.savefig('fig1.png', bbox_inches='tight')
