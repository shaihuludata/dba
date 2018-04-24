import matplotlib
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mp
# mp.use('agg')
import time
import json

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
            passed_schedule.update({time: schedule[time] for time in schedule
                                    if (time in range(time_range[0], time_range[1])) and (time <= cur_time)})

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
            passed_schedule.update({t: schedule[t] for t in schedule
                                    if (t in range(time_range[0], time_range[1])) and (t <= cur_time)})

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
            passed_schedule.update({t: schedule[t] for t in schedule
                                    if (t in range(time_range[0], time_range[1])) and (t <= cur_time)})

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
        passed_schedule = dict()
        for time_range in self.time_ranges_to_show:
            passed_schedule.update({t: schedule[t] for t in schedule
                                    if (t in range(time_range[0], time_range[1])) and (t <= cur_time)})

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
        return

    def cook_result(self):
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
                    flow_packet_result[alloc][packet_num] = packet
        return flow_packet_result

    def cook_result2(self):
        time_throughput_result = dict()
        # for alloc in self.observer_result:
        #     time_data_result = self.observer_result[alloc]
        #     for time_r in time_data_result:
        #         alloc_time_data = time_data_result[time_r]
        #         for packet in alloc_time_data:
        #             if alloc not in flow_packet_result:
        #                 flow_packet_result[alloc] = dict()
        #             packet_num = packet['packet_num']
        #             # if packet_num not in flow_packet_result[alloc]:
        #             packet['dead_time'] = time_r
        #             flow_packet_result[alloc][packet_num] = packet
        # return time_throughput_result
        return self.observer_result

    def make_results(self):
        fig = plt.figure(1, figsize=(15, 15))
        fig.show()
        flow_packet_result = self.cook_result()
        flow_time_throughput_result = self.cook_result2()
        number_of_flows = len(self.observer_result)
        subplot_index = 1
        for flow_name in flow_packet_result:
            packet_result, latency_result = list(), list()
            for pack_num in flow_packet_result[flow_name]:
                packet = flow_packet_result[flow_name][pack_num]
                if 'born_time' in packet:
                    packet_result.append(pack_num)
                    latency_result.append(packet['dead_time'] - packet['born_time'])
            ax = fig.add_subplot(number_of_flows, 2, subplot_index)
            subplot_index += 1
            plt.ylabel(flow_name)
            ax.plot(packet_result, latency_result, 'ro')
            fig.canvas.draw()
            time.sleep(1)

            time_result, throughput_result = list(), list()
            time_throughput_result = dict()
            for time_d in self.observer_result[flow_name]:
                packets = flow_time_throughput_result[flow_name][time_d]
                throughput = list()
                for packet in packets:
                    throughput.append(packet['size'])
                time_throughput_result[time_d] = (sum(throughput))

            # теперь надо пронормировать пришедшее количество байт на временной интервал
            time_result = list(time_throughput_result.keys())
            time_result.sort()
            last_time_d = int()
            for time_d in time_result:
                throughput_result.append(time_throughput_result[time_d] / (time_d - last_time_d))
                last_time_d = time_d

            ax = fig.add_subplot(number_of_flows, 2, subplot_index)
            subplot_index += 1
            # plt.ylabel(flow_name)
            ax.plot(time_result, throughput_result)
            fig.canvas.draw()
            time.sleep(1)

        # ax.set_xticklabels(points_to_watch)
        fig.canvas.draw()
        # time.sleep(1)
        # plt.show()
        fig.savefig(result_dir + 'packets.png', bbox_inches='tight')
        plt.close(fig)


class IPTrafficObserver:

    def __init__(self, time_ranges_to_show):
        self.name = 'Traffic visualizer'
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
        # append_to_json(schedule.__dict__, result_dir + 'IPtraffic.json')
        passed_schedule = dict()
        for time_range in self.time_ranges_to_show:
            passed_schedule.update({t: schedule[t] for t in schedule
                                    if (t in range(time_range[0], time_range[1])) and (t <= cur_time)})

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
        return

    def cook_result(self):
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
                    flow_packet_result[alloc][packet_num] = packet
        return flow_packet_result

    def cook_result2(self):
        time_throughput_result = dict()
        # for alloc in self.observer_result:
        #     time_data_result = self.observer_result[alloc]
        #     for time_r in time_data_result:
        #         alloc_time_data = time_data_result[time_r]
        #         for packet in alloc_time_data:
        #             if alloc not in flow_packet_result:
        #                 flow_packet_result[alloc] = dict()
        #             packet_num = packet['packet_num']
        #             # if packet_num not in flow_packet_result[alloc]:
        #             packet['dead_time'] = time_r
        #             flow_packet_result[alloc][packet_num] = packet
        # return time_throughput_result
        return self.observer_result

    def make_results(self):
        fig = plt.figure(1, figsize=(15, 15))
        fig.show()
        flow_packet_result = self.cook_result()
        flow_time_throughput_result = self.cook_result2()
        number_of_flows = len(self.observer_result)
        subplot_index = 1
        for flow_name in flow_packet_result:
            packet_result, latency_result = list(), list()
            for pack_num in flow_packet_result[flow_name]:
                packet = flow_packet_result[flow_name][pack_num]
                if 'born_time' in packet:
                    packet_result.append(pack_num)
                    latency_result.append(packet['dead_time'] - packet['born_time'])
            ax = fig.add_subplot(number_of_flows, 2, subplot_index)
            subplot_index += 1
            plt.ylabel(flow_name)
            ax.plot(packet_result, latency_result, 'ro')
            fig.canvas.draw()
            time.sleep(1)

            time_result, throughput_result = list(), list()
            time_throughput_result = dict()
            for time_d in self.observer_result[flow_name]:
                packets = flow_time_throughput_result[flow_name][time_d]
                throughput = list()
                for packet in packets:
                    throughput.append(packet['size'])
                time_throughput_result[time_d] = (sum(throughput))

            # теперь надо пронормировать пришедшее количество байт на временной интервал
            time_result = list(time_throughput_result.keys())
            time_result.sort()
            last_time_d = int()
            for time_d in time_result:
                throughput_result.append(time_throughput_result[time_d] / (time_d - last_time_d))
                last_time_d = time_d

            ax = fig.add_subplot(number_of_flows, 2, subplot_index)
            subplot_index += 1
            # plt.ylabel(flow_name)
            ax.plot(time_result, throughput_result)
            fig.canvas.draw()
            time.sleep(1)

        # ax.set_xticklabels(points_to_watch)
        fig.canvas.draw()
        # time.sleep(1)
        # plt.show()
        fig.savefig(result_dir + 'packets.png', bbox_inches='tight')
        plt.close(fig)
