import matplotlib
import numpy as np
from mpl_toolkits.mplot3d import axes3d
import matplotlib.pyplot as plt
import matplotlib as mp
# mp.use('agg')
import time
import json
from sympy import Interval, FiniteSet
from matplotlib import cm
from matplotlib.ticker import LinearLocator, FormatStrFormatter
import statistics

result_dir = './result/'

def append_to_json(_dict, path):
    with open(path, 'a+') as f:
        f.seek(0, 2)  # Go to the end of file
        if f.tell() == 0:  # Check if file is empty
            json.dump([_dict], f)  # If empty, write an array
        else:
            f.seek(-1, 2)
            f.truncate()  # Remove the last character, open the array
            f.write(' , ')  # Write the separator
            json.dump(_dict, f)  # Dump the dictionary
            f.write(']')  # Close the array


class FlowObserver:

    def __init__(self, time_ranges_to_show):
        self.name = 'GTC_signals_visualizer'
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
            time_interval = Interval(time_range[0], time_range[1])
            passed_schedule.update({time: schedule[time] for time in schedule
                                    if (time in time_interval) and (time <= cur_time)})

        for ev_time in passed_schedule:
            for event in passed_schedule[ev_time]:
                dev, state, sig, port = event['dev'], event['state'], event['sig'], event['port']
                if state in ['s_start', 's_end', 'r_start', 'r_end']:
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
            #boxprops = dict(linestyle='--', linewidth=3, color='darkgoldenrod')
            boxprops = dict()
            #meanlineprops = dict(linestyle='--', linewidth=2.5, color='purple')
            # _linestyles = [('-', 'solid'), ('--', 'dashed'), ('-.', 'dashdot'), (':', 'dotted')
            whiskerprops = dict(linestyle='-', linewidth=1, color='black')
            ax.boxplot(dtp, 0, 'rs',
                       meanline=False, vert=True,
                       patch_artist=True, boxprops=boxprops,
                       whiskerprops=whiskerprops)

            ax.set_xticklabels(points_to_watch)
            fig.canvas.draw()
            #time.sleep(1)

        fig.canvas.draw()
        # time.sleep(3)
        fig.savefig(result_dir + 'flow_diagram.png', bbox_inches='tight')
        plt.close(fig)


class PhysicsObserver:

    def __init__(self, time_ranges_to_show):
        self.name = 'Physics visualizer'
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
        # обозреваем только события, заключённые в time_ranges_to_show
        passed_schedule = dict()
        for time_range in self.time_ranges_to_show:
            time_interval = Interval(time_range[0], time_range[1])
            passed_schedule.update({t: schedule[t] for t in schedule
                                    if (t in time_interval) and (t <= cur_time)})

        for ev_time in passed_schedule:
            for event in passed_schedule[ev_time]:
                dev, state, sig, port = event['dev'], event['state'], event['sig'], event['port']
                if state in ['s_start', 's_end', 'r_start', 'r_end']:
                    if sig.name not in self.observer_result:
                        self.observer_result[sig.name] = dict()
                    physics = dict()
                    physics.update(sig.physics)
                    self.observer_result[sig.name][sig.external.distance_passed] = physics
                    #в результате накапливается 3 уровня вложений словарей
                    #{имя сигнала : {время: физика сигнала}}
        return

    def cook_result(self):

        return

    def make_results_by_time(self):
        # for sig_name in self.observer_result:
        #     time_phys_result = self.observer_result[sig_name]
        #     time_result, pow_result = list(), list()
        #     number_of_sigs = len(time_phys_result)
        #     times = list(time_phys_result.keys())
        #     times.sort()
        #     for time_r in times:
        #         time_result.append(time_r)
        #         pow_result.append(time_phys_result[time_r]['power'])
        #     ax = fig.add_subplot(number_of_sigs, 1, sig_name_index)
        #     sig_name_index += 1
        #     ax.plot(time_result, pow_result)
        #     #fig.canvas.draw()
        #     time.sleep(1)
        return

    def make_results(self):
        fig = plt.figure(1, figsize=(15, 15))
        fig.show()
        sig_name_index = 1
        length_limit = int()

        #чтобы уравнять длины графиков
        for sig_name in self.observer_result:
            cur_length_limit = max(self.observer_result[sig_name].keys())
            if length_limit < cur_length_limit:
                length_limit = cur_length_limit

        number_of_sigs = len(self.observer_result)
        for sig_name in self.observer_result:
            dist_phys_result = self.observer_result[sig_name]
            dist_result, pow_result = list(), list()
            dists = list(dist_phys_result.keys())
            dists.sort()
            for time_r in dists:
                dist_result.append(time_r)
                pow_result.append(dist_phys_result[time_r]['power'])
            ax = fig.add_subplot(number_of_sigs, 1, sig_name_index)
            sig_name_index += 1
            plt.ylabel(sig_name)
            ax.plot(dist_result, pow_result)
            ax.set_xlim(0, length_limit)
            fig.canvas.draw()
            time.sleep(1)

        #ax.set_xticklabels(points_to_watch)
        fig.canvas.draw()
        #time.sleep(1)
        #plt.show()
        fig.savefig(result_dir + 'levels.png', bbox_inches='tight')
        plt.close(fig)


class TrafficObserver:

    def __init__(self, time_ranges_to_show):
        self.name = 'Traffic visualizer'
        self.observer_result = dict()
        # # {dev.name + '::' + port: [(time, sig.__dict__)]}
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
        # обозреваем только события, заключённые в time_ranges_to_show
        passed_schedule = dict()
        for time_range in self.time_ranges_to_show:
            time_interval = Interval(time_range[0], time_range[1])
            passed_schedule.update({t: schedule[t] for t in schedule
                                    if (t in time_interval) and (t <= cur_time)})

        for ev_time in passed_schedule:
            for event in passed_schedule[ev_time]:
                dev, state, sig, port = event['dev'], event['state'], event['sig'], event['port']
                # if sig.physics['type'] == 'electric':
                if 'OLT' in dev.name and state == 'r_end':
                    if sig.name not in self.observer_result:
                        self.observer_result[sig.name] = dict()
                    data = dict()
                    data.update(sig.data)
                    # for dev_name in ['OLT']:  # , 'OLT']
                    # if dev_name in dev.name:
                    self.observer_result[sig.name][ev_time] = data
                # {имя сигнала : {время: данные сигнала}}
        return

    def cook_result(self):
        flow_time_result = dict()
        for dev_name in self.observer_result:
            time_data_result = self.observer_result[dev_name]
            for time_r in time_data_result:
                tcont_data = time_data_result[time_r]
                for alloc in tcont_data:
                    if dev_name in alloc:
                        if alloc not in flow_time_result:
                            flow_time_result[alloc] = dict()
                        if time_r not in flow_time_result[alloc]:
                            flow_time_result[alloc][time_r] = tcont_data[alloc]
        return flow_time_result

    def make_results(self):
        fig = plt.figure(1, figsize=(15, 15))
        fig.show()

        # number_of_sigs = len(self.observer_result)
        flow_time_result = self.cook_result()
        number_of_flows = len(flow_time_result)
        flow_index = 1
        for flow_name in flow_time_result:
            time_result, latency_result = list(), list()
            for time_r in flow_time_result[flow_name]:
                packet_data = flow_time_result[flow_name][time_r]
                if 'born_time' in packet_data:
                    time_result.append(time_r)
                    latency_result.append(time_r - packet_data['born_time'])
            ax = fig.add_subplot(number_of_flows, 1, flow_index)
            flow_index += 1
            plt.ylabel(flow_name)
            ax.plot(time_result, latency_result)
            fig.canvas.draw()
            time.sleep(1)

        # ax.set_xticklabels(points_to_watch)
        fig.canvas.draw()
        # time.sleep(1)
        # plt.show()
        fig.savefig(result_dir + 'packets.png', bbox_inches='tight')


class ReceivedTrafficObserver:

    def __init__(self, time_ranges_to_show):
        self.name = 'Traffic visualizer'
        self.observer_result = dict()
        self.utilization_result = dict()
        if not time_ranges_to_show:
            self.time_ranges_to_show = [[1000, 2000]]
        else:
            self.time_ranges_to_show = time_ranges_to_show

        self.time_horisont = 0
        for time_range in self.time_ranges_to_show:
            new_horisont = max(time_range)
            if self.time_horisont < new_horisont:
                self.time_horisont = new_horisont

    def notice(self, events, cur_time):
        passed_schedule = dict()
        time_range = self.time_ranges_to_show[0]
        time_interval = Interval(time_range[0], time_range[1])
        if cur_time not in time_interval:
            return
        passed_schedule.update({cur_time: events})

        for event in passed_schedule[cur_time]:
            state = event['state']
            dev = event['dev']
            if state == 'defrag':
                packet, port = event['sig'], event['port']
                alloc = packet['alloc_id']
                # {alloc : {время: [пакеты]}}
                if alloc not in self.observer_result:
                    self.observer_result[alloc] = dict()
                if cur_time not in self.observer_result[alloc]:
                    self.observer_result[alloc][cur_time] = list()
                self.observer_result[alloc][cur_time].append(packet)
            elif 'OLT' in dev.name:
                sig, port = event['sig'], event['port']
                if 'bwmap' in sig.data:
                    bwmap = sig.data['bwmap']
                    for alloc in bwmap:
                        alloc_name = alloc['Alloc-ID']
                        alloc_size = alloc['StopTime'] - alloc['StartTime']
                        if alloc_name not in self.utilization_result:
                            self.utilization_result[alloc_name] = dict()
                        if cur_time not in self.utilization_result[alloc_name]:
                            self.utilization_result[alloc_name][cur_time] = list()
                        self.utilization_result[alloc_name][cur_time].append(alloc_size)
        return

    def cook_result(self):
        flow_time_result = dict()
        for alloc in self.observer_result:
            time_data_result = self.observer_result[alloc]
            for time_r in time_data_result:
                packet = time_data_result[time_r]
                #for packet in alloc_time_data:
                if alloc not in flow_time_result:
                    flow_time_result[alloc] = dict()
                # packet_num = packet['packet_num']
                # if packet_num not in flow_packet_result[alloc]:
                # packet['dead_time'] = time_r
                flow_time_result[alloc][time_r] = packet
        return flow_time_result

    def make_results(self):
        fig = plt.figure(1, figsize=(15, 15))
        fig.show()
        flow_time_result = self.cook_result()
        number_of_flows = len(self.observer_result)
        subplot_index = 1
        flow_utilization_dict = dict()
        for flow_name in flow_time_result:
            throughput_result, alloc_result = list(), list()
            time_throughput_result = dict()
            time_alloc_result = self.utilization_result[flow_name]
            for time_d in self.observer_result[flow_name]:
                packets = flow_time_result[flow_name][time_d]
                throughput = list()
                for packet in packets:
                    throughput.append(packet['size'])
                time_throughput_result[time_d] = (sum(throughput))

            # теперь надо пронормировать количество байт на временной интервал
            # для пропускной способности
            time_result_bw = list(time_throughput_result.keys())
            time_result_bw.sort()
            last_time_d = int()
            for time_d in time_result_bw:
                throughput_result.append(8 * time_throughput_result[time_d] / (time_d - last_time_d))
                last_time_d = time_d
            # для текущих значений alloc
            time_result_al = list(time_alloc_result.keys())
            time_result_al.sort()
            last_time_d = int()
            for time_d in time_result_al:
                alloc_result.append(8 * sum(time_alloc_result[time_d]) / (time_d - last_time_d))
                last_time_d = time_d

            ax = fig.add_subplot(number_of_flows, 2, subplot_index)
            subplot_index += 1
            plt.ylabel(flow_name)
            ax.plot(time_result_bw, throughput_result)
            ax.plot(time_result_al, alloc_result)
            fig.canvas.draw()
            # time.sleep(1)

            # теперь есть 2 функции:
            # time_result_bw и throughput_result, time_result_al и alloc_result
            # надо их вычесть друг из друга, получится график утилизации
            bw_interval = Interval(min(time_result_bw), max(time_result_bw))
            al_interval = Interval(min(time_result_al), max(time_result_al))
            common_interval = bw_interval.intersect(al_interval)
            if type(common_interval) is not FiniteSet:
                time_stride = np.arange(float(common_interval.start), float(common_interval.end), 125)
                bw_interpolated = np.interp(time_stride, time_result_bw, throughput_result)
                al_interpolated = np.interp(time_stride, time_result_al, alloc_result)
                utilization_result = bw_interpolated / al_interpolated
                ax = fig.add_subplot(number_of_flows, 2, subplot_index)
                ax.plot(time_stride, utilization_result)
                fig.canvas.draw()
            subplot_index += 1
            # plt.xlabel("Утилизация")
            time.sleep(1)

            total_bw = np.trapz(time_result_bw, throughput_result)
            total_al = np.trapz(time_result_al, alloc_result)
            total_utilization = total_bw / total_al
            if total_utilization < 0:
                print('странно')
            flow_utilization_dict[flow_name] = total_utilization
        print(flow_utilization_dict)
        mean_utilization = statistics.mean(flow_utilization_dict.values())
        disp_utilization = statistics.variance(flow_utilization_dict.values())
        print('mean_utilization {}, dispersion {}'.format(mean_utilization, disp_utilization))

        fig.canvas.draw()
        fig.savefig(result_dir + 'bandwidth.png', bbox_inches='tight')
        plt.close(fig)


class IPTrafficObserver:

    def __init__(self, time_ranges_to_show):
        self.name = 'IP visualizer'
        self.observer_result_list = list()
        self.observer_result = dict()
        if not time_ranges_to_show:
            self.time_ranges_to_show = [[1000, 2000]]
        else:
            self.time_ranges_to_show = time_ranges_to_show

        self.time_horisont = 0
        for time_range in self.time_ranges_to_show:
            new_horisont = max(time_range)
            if self.time_horisont < new_horisont:
                self.time_horisont = new_horisont

    def notice(self, schedule, cur_time):
        sched = dict()
        for t in schedule:
            if t <= cur_time:
                for ev in schedule[t]:
                    if ev['state'] is 'defrag':
                        if t not in sched:
                            sched[t] = list()
                        sched[t].append(ev)
        # sched.update(schedule)
        if len(sched) > 0:
            self.observer_result_list.append((cur_time, sched))

    def cook_result(self):
        for time_sched_tup in self.observer_result_list:
            passed_schedule = dict()
            cur_time = time_sched_tup[0]
            schedule = time_sched_tup[1]
            for time_range in self.time_ranges_to_show:
                time_interval = Interval(time_range[0], time_range[1])
                passed_schedule.update({t: schedule[t] for t in schedule
                                        if (t in time_interval) and (t <= cur_time)})
                # for t in schedule:
                #     if t <= cur_time:
                #         time_interval = Interval(time_range[0], time_range[1])
                #         if t in time_interval:
                #             passed_schedule.update({t: schedule[t]})

            for ev_time in passed_schedule:
                for event in passed_schedule[ev_time]:
                    state = event['state']
                    if state == 'defrag':
                        dev, packet, port = event['dev'], event['sig'], event['port']
                        alloc = packet['alloc_id']
                        # {alloc : {время: [пакеты]}}
                        if alloc not in self.observer_result:
                            self.observer_result[alloc] = dict()
                        if ev_time not in self.observer_result[alloc]:
                            self.observer_result[alloc][ev_time] = list()
                        self.observer_result[alloc][ev_time].append(packet)

    def cook_packets(self):
        flow_packet_result = dict()
        for alloc in self.observer_result:
            time_data_result = self.observer_result[alloc]
            for time_r in time_data_result:
                alloc_time_data = time_data_result[time_r]
                for packet in alloc_time_data:
                    if alloc not in flow_packet_result:
                        flow_packet_result[alloc] = dict()

                    packet_num = packet['packet_num']
                    # if packet_num not in flow_packet_result[alloc]:
                    packet['dead_time'] = time_r
                    # flow_packet_result[alloc][packet_num] = packet
                    # if packet_num not in flow_packet_result[alloc]:
                    #     flow_packet_result[alloc][packet_num] = list()
                    flow_packet_result[alloc][packet_num] = packet
        return flow_packet_result

    def cook_loss_rate(self):
        result = dict()
        return result

    def make_results(self):
        self.cook_result()
        flow_packet_result = self.cook_packets()
        fig = plt.figure(1, figsize=(15, 20))
        fig.show()

        number_of_flows = len(self.observer_result)
        subplot_index = 1
        for flow_name in flow_packet_result:
            # список пакетов
            packet_num_result = list(flow_packet_result[flow_name].keys())
            packet_num_result.sort()
            # time_result_in_ms = list(i/1000 for i in packet_num_result)

            # график задержек
            latency_result = list()
            for pack_num in packet_num_result:
                packet = flow_packet_result[flow_name][pack_num]
                # for packet in flow_packet_result[flow_name][pack_num]:
                    # if 'born_time' in packet:
                latency_result.append(packet['dead_time'] - packet['born_time'])
            ax = fig.add_subplot(number_of_flows, 3, subplot_index)
            subplot_index += 1
            plt.ylabel(flow_name)
            ax.plot(packet_num_result, latency_result, 'ro')
            max_latency = max(latency_result)
            ax.set_ylim(bottom=0, top=max_latency+100)
            fig.canvas.draw()
            # time.sleep(1)

            # график вариации задержек
            dv_result = list()
            # basis_latency = min(latency_result)
            basis_latency = sum(latency_result) / len(latency_result)
            for pack_num in packet_num_result:
                packet = flow_packet_result[flow_name][pack_num]
                # if 'born_time' in packet:
                dv = (packet['dead_time'] - packet['born_time']) / basis_latency
                dv_result.append(dv)
            ax = fig.add_subplot(number_of_flows, 3, subplot_index)
            subplot_index += 1
            # plt.ylabel(flow_name)
            ax.plot(packet_num_result, dv_result, 'ro')
            min_dv = min(dv_result)
            max_dv = max(dv_result)
            ax.set_ylim(bottom=min_dv-1, top=max_dv+1)
            fig.canvas.draw()
            # time.sleep(1)

            # график коэффициента потерь
            # каждое последующее значение зависит от предыдущего
            # поэтому массив по времени должен быть отсортирован
            packet_nums = list()
            lr_result = list()
            max_pack_num_got = int()
            for pack_num in packet_num_result:
                packet = flow_packet_result[flow_name][pack_num]
                packet_num = packet['packet_num']
                max_pack_num_got = packet_num if packet_num > max_pack_num_got else packet_num
                packet_nums.append(packet_num)
                current_lr = (max_pack_num_got - len(packet_nums)) / max_pack_num_got
                # if current_lr > 0 and 'ONT4' in flow_name:
                #     print('4')
                # if current_lr > 0 and 'ONT3' in flow_name:
                #     print('3')
                # if current_lr > 0 and 'ONT2' in flow_name:
                #     print('2')
                # if current_lr > 0 and 'ONT1' in flow_name:
                #     print('1')
                lr_result.append(current_lr)
            ax = fig.add_subplot(number_of_flows, 3, subplot_index)
            subplot_index += 1
            # plt.ylabel(flow_name)
            ax.plot(packet_num_result, lr_result, 'ro')
            min_lr = min(lr_result)
            max_lr = max(lr_result)
            ax.set_ylim(bottom=min_lr, top=max_lr)
            fig.canvas.draw()
            # time.sleep(1)

        # ax.set_xticklabels(points_to_watch)
        fig.canvas.draw()
        # time.sleep(1)
        # plt.show()
        fig.savefig(result_dir + 'packets.png', bbox_inches='tight')
        plt.close(fig)


class MassTrafficObserver:

    def __init__(self, time_ranges_to_show):
        self.name = 'Mass packet visualizer'
        self.observer_result_list = list()
        self.observer_result = dict()
        if not time_ranges_to_show:
            self.time_ranges_to_show = [[1000, 2000]]
        else:
            self.time_ranges_to_show = time_ranges_to_show

        self.time_horisont = 0
        for time_range in self.time_ranges_to_show:
            new_horisont = max(time_range)
            if self.time_horisont < new_horisont:
                self.time_horisont = new_horisont

    def notice(self, events, cur_time):
        time_range = self.time_ranges_to_show[0]
        time_interval = Interval(time_range[0], time_range[1])
        if cur_time not in time_interval:
            return
        # passed_schedule = {cur_time: events}

        for event in events:
            if event['state'] == 'defrag':
                self.observer_result_list.append((cur_time, event))
        return

    def cook_result(self):
        for time_ev_tup in self.observer_result_list:
            cur_time = time_ev_tup[0]
            event = time_ev_tup[1]

            if event['state'] == 'defrag':
                dev, packet, port = event['dev'], event['sig'], event['port']
                alloc = packet['alloc_id']
                # {alloc : {время: [пакеты]}}
                if alloc not in self.observer_result:
                    self.observer_result[alloc] = dict()
                if cur_time not in self.observer_result[alloc]:
                    self.observer_result[alloc][cur_time] = list()
                self.observer_result[alloc][cur_time].append(packet)

    def make_results(self):
        self.cook_result()
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        flow_time_result = self.observer_result
        # fig = plt.figure(1, figsize=(15, 20))
        fig.show()

        number_of_flows = len(self.observer_result)
        flow_time_intervals = dict()
        for flow_name in flow_time_result:
            time_event_dicts = flow_time_result[flow_name]
            if flow_name not in flow_time_intervals:
                min_time = min(time_event_dicts.keys())
                max_time = max(time_event_dicts.keys())
                flow_time_intervals[flow_name] = Interval(min_time, max_time)

        common_interval = Interval(0, self.time_horisont)
        for interval in flow_time_intervals.values():
            if type(interval) != FiniteSet:
                common_interval = common_interval.intersect(interval)

        interpolated_flow_time_result = dict()
        interpolated_flow_functions = dict()
        # stride_step = (common_interval.end - common_interval.start) / 20
        time_stride = np.arange(float(common_interval.start), float(common_interval.end), 125)
        for flow_name in flow_time_result:
            current_flow_res = flow_time_result[flow_name]
            if len(current_flow_res) > 1:
                arg_list = list(t for t in current_flow_res.keys() if t in common_interval)
                latency_args = np.array(arg_list)
                # func_list = list(current_flow_res[t][0]['born_time'] for t in current_flow_res.keys() if t in common_interval)
                for t in current_flow_res.keys():
                    if t in common_interval:
                        current_flow_res[t][0]['dead_time'] = t
                func_list = list(current_flow_res[t][0]['dead_time'] - current_flow_res[t][0]['born_time']
                                 for t in current_flow_res.keys() if t in common_interval)
                latency_func = np.array(func_list)
                interpolated_func = np.interp(time_stride, latency_args, latency_func)
                interpolated_flow_functions[flow_name] = interpolated_func
                t_stride = list()
                t_stride = time_stride.tolist()
                for t in t_stride:
                    t_index = t_stride.index(t)
                    if flow_name not in interpolated_flow_time_result:
                        interpolated_flow_time_result[flow_name] = dict()
                    interpolated_flow_time_result[flow_name][t] = interpolated_func[t_index]

        flow_index = 1
        flow_index_dict = dict()
        flow_index_list = list()
        for flow_name in interpolated_flow_time_result:
            flow_index_dict[flow_index] = flow_name
            flow_index_list.append(flow_index)
            flow_index += 1
        del(flow_index)

        time_stride, flow_index_list = np.meshgrid(time_stride, flow_index_list)
        func_list = list()
        for x in range(0, time_stride.shape[0]):
            f_string_list = list()
            for y in range(0, time_stride.shape[1]):
                t = time_stride[x][y]
                f = flow_index_list[x][y]
                flow_name = flow_index_dict[f]
                f_string_list.append(interpolated_flow_time_result[flow_name][t])
            func_list.append(f_string_list)
        func_map_list = np.array(func_list)

        surf = ax.plot_surface(flow_index_list, time_stride, func_map_list, cmap=cm.coolwarm, linewidth=0, antialiased=False)
        # график задержек
        # latency_result = list()
        # for pack_num in packet_num_result:
        #     packet = flow_time_result[flow_name][pack_num]
        #     # for packet in flow_packet_result[flow_name][pack_num]:
        #         # if 'born_time' in packet:
        #     latency_result.append(packet['dead_time'] - packet['born_time'])
        # ax = fig.add_subplot(number_of_flows, 3, subplot_index)
        # subplot_index += 1
        # plt.ylabel(flow_name)
        # ax.plot(packet_num_result, latency_result, 'ro')
        # max_latency = max(latency_result)
        # ax.set_ylim(bottom=0, top=max_latency+100)
        # fig.canvas.draw()

        # ax.plot_wireframe(X, Y, Z, rstride=10, cstride=10)
        # fig.canvas.draw()
        plt.show()
        fig.savefig(result_dir + '3d_packets.png', bbox_inches='tight')
        plt.close(fig)
