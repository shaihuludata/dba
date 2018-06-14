from threading import Thread
from threading import Event as ThEvent
from sympy import EmptySet, Interval
import matplotlib.pyplot as plt
from uni_traffic.packet import Packet
import numpy as np
import collections
import re
import json


class Observer(Thread):
    result_dir = "./result/"
    # flow FlowObserver, power PhysicsObserver, traffic ReceivedTrafficObserver
    # mass_traffic MassTrafficObserver, BufferObserver BufferObserver

    def __init__(self, env, config):
        Thread.__init__(self)
        self.env = env
        self.name = "CommonObserver"
        obs_conf = config["observers"]
        self.time_ranges_to_show = dict()
        self.observers_active = list()
        observer_dict = {"flow": 0, "power": 0,
                         "packets": (self.packets_matcher,
                                     self.packets_res_make),
                         "traffic_utilization": ((self.traffic_utilization_matcher, self.buffer_utilization_matcher),
                                                 self.traffic_utilization_res_make),
                         "buffers": 0,
                         "mass": 0,
                         "total_per_flow_performance_result": ()}
        self.match_conditions = list()
        self.result_makers = list()
        for obs_name in obs_conf:
            cur_obs_conf = obs_conf[obs_name]
            if cur_obs_conf["report"]:
                self.observers_active.append(obs_name)
                time_ranges = cur_obs_conf["time_ranges"]
                self.time_ranges_to_show[obs_name] = EmptySet().union(Interval(i[0], i[1])
                                                                      for i in time_ranges)
                matcher = observer_dict[obs_name][0]
                if isinstance(matcher, collections.Iterable):
                    self.match_conditions.extend(matcher)
                else:
                    self.match_conditions.append(matcher)
                res_maker = observer_dict[obs_name][1]
                self.result_makers.append(res_maker)

        if len(self.time_ranges_to_show) > 0:
            self.time_horizon = max(list(max(self.time_ranges_to_show[i].boundary)
                                         for i in self.time_ranges_to_show))
            self.time_horizon = max(config["horizon"], self.time_horizon)

        self.new_data = list()
        self.traf_mon_result = dict()
        self.packets_result = dict()
        self.global_flow_result = dict()
        self.ev_wait = ThEvent()
        self.end_flag = False
        self.cur_time = 0

    def run(self):
        while not self.end_flag:
            cur_time_in_msec = round(self.env.now // 1000)
            if cur_time_in_msec > self.cur_time:
                print("время {} мс".format(cur_time_in_msec))
                self.cur_time = cur_time_in_msec
            self.ev_wait.wait(timeout=5)  # wait for event
            for i in self.new_data:
                # r_end, cur_time, dev, sig, port = i
                # defragmentation, cur_time, psink, pkt
                for matcher in self.match_conditions:
                    try:
                        matcher(*i)
                    except TypeError:
                        pass
                self.new_data.remove(i)
                self.ev_wait.clear()  # clean event for future

    def notice(self, func):
        def wrapped(*args):
            data = list(args)
            data.insert(0, round(self.env.now, 3))
            data.insert(0, func.__name__)
            self.new_data.append(tuple(data))
            self.ev_wait.set()
            return func(*args)
        return wrapped

    @staticmethod
    def export_counters(devices):
        for dev_name in devices:
            if re.search("[ON|LT]", dev_name) is not None:
                dev = devices[dev_name]
                print("{} : {}".format(dev_name, dev.counters.export_to_console()))
            if re.search("OLT", dev_name) is not None:
                print("{} : {}".format("OLT0_recv", dev.p_sink.p_counters.export_to_console()))
            if re.search("ONT", dev_name) is not None:
                for tg_name in dev.traffic_generators:
                    tg = dev.traffic_generators[tg_name]
                    print("{} : {}".format(tg_name, tg.p_counters.export_to_console()))

    def make_results(self):
        for res_make in self.result_makers:
            fig = plt.figure(1, figsize=(15, 15))
            fig.show()
            res_make(fig)
            plt.close(fig)
        if "total_per_flow_performance_result" in self.observers_active:
            tpfp_res = self.make_total_per_flow_performance_result()

    def make_total_per_flow_performance_result(self):
        objective = json.load(open("../observer/net_performance.json"))
        normative = dict()
        normative.update(objective["ITU-T Y1540"])
        normative.update(objective["PON"])

        normalized_per_flow_result = dict()
        for flow_id in self.global_flow_result:
            normalized_per_flow_result[flow_id] = dict()
            normalized_result = dict()
            par_result = dict()
            normalized_result[tr_class] = par_result
            for par in ["IPTD", "IPDV", "IPLR"]:
                par_value = normative[par][tr_class]
                if par == "IPTD":
                    par_result = float(par_value.split("+")[0])
                elif par == "IPDV":
                    par_result = float(par_value) if par_value != "U" else float("Inf")
                elif par == "IPLR":
                    par_result = float(par_value) if par_value != "U" else float("Inf")
                else:
                    raise NotImplemented
            # normalized_result[tr_class][par] = par_result

    def packets_matcher(self, operation, cur_time, psink, pkt: Packet):
        if operation is not "check_dfg_pkt":
            return False
        if pkt is None:
            return False
        if cur_time not in self.time_ranges_to_show["packets"]:
            return False
        # ***
        # if "ONT1_1" in pkt.flow_id:
        #     print(pkt.num)
        # ***
        flow_id = pkt.flow_id
        if flow_id not in self.packets_result:
            self.packets_result[flow_id] = dict()
        if pkt.num not in self.packets_result[flow_id]:
            self.packets_result[flow_id][pkt.num] = pkt

    def packets_res_make(self, fig):
        number_of_flows = len(self.packets_result)
        flow_pack_result = self.packets_result
        subplot_index = 1
        flows = list(flow_pack_result.keys())
        flows.sort()
        for flow_name in flows:
            # time_result = list(flow_time_result[flow_name].keys())
            pack_res = flow_pack_result[flow_name]
            pkt_nums = list(pack_res.keys())
            pkt_nums.sort()
            # график задержек
            latency_result = list()
            for pkt_num in pkt_nums:
                pkt = pack_res[pkt_num]
                latency_result.append(pkt.dfg_time - pkt.s_time)
            ax = fig.add_subplot(number_of_flows, 3, subplot_index)
            subplot_index += 1
            plt.ylabel(flow_name)
            ax.plot(pkt_nums, latency_result, "ro")
            fig.canvas.draw()

            # график вариации задержек
            dv_result = list()
            basis_latency = min(latency_result)
            basis_latency = sum(latency_result) / len(latency_result)
            for pkt_num in pkt_nums:
                pkt = pack_res[pkt_num]
                dv = (pkt.dfg_time - pkt.s_time) / basis_latency
                dv_result.append(dv)
            ax = fig.add_subplot(number_of_flows, 3, subplot_index)
            subplot_index += 1
            # plt.ylabel(flow_name)
            ax.plot(pkt_nums, dv_result, "ro")
            min_dv = min(dv_result)
            max_dv = max(dv_result)
            ax.set_ylim(bottom=min_dv - 1, top=max_dv + 1)
            fig.canvas.draw()

            # график коэффициента потерь
            # каждое последующее значение зависит от предыдущего
            # поэтому массив по времени должен быть отсортирован
            packet_nums = list()
            lr_result = list()
            max_pack_num_got = int()
            for pkt_num in pkt_nums:
                pkt = pack_res[pkt_num]
                packet_nums.append(pkt_num)
                max_pack_num_got = pkt_num if pkt_num > max_pack_num_got else pkt_num
                current_lr = (max_pack_num_got - len(packet_nums)) / max_pack_num_got
                lr_result.append(current_lr)
            ax = fig.add_subplot(number_of_flows, 3, subplot_index)
            subplot_index += 1
            # plt.ylabel(flow_name)
            ax.plot(pkt_nums, lr_result, "ro")
            min_lr = min(lr_result)
            max_lr = max(lr_result)
            ax.set_ylim(bottom=min_lr, top=max_lr)
            fig.canvas.draw()

        # ax.set_xticklabels(points_to_watch)
        fig.canvas.draw()
        fig.savefig(self.result_dir + "packets1sec.png", bbox_inches="tight")

    def traffic_utilization_matcher(self, operation, cur_time, dev, sig, port):
        if operation is not "r_end":
            return False
        if cur_time not in self.time_ranges_to_show["traffic_utilization"]:
            return False
        if "OLT" not in dev.name:
            return False
        for flow_id in sig.data:
            if "ONT" not in flow_id:
                continue
            if flow_id not in self.traf_mon_result:
                self.traf_mon_result[flow_id] = dict()
            assert cur_time not in self.traf_mon_result[flow_id]
            pkts = sig.data[flow_id]
            pkts_size = sum(list(pkt.size for pkt in pkts))
            grant_size = sig.data["grant_size"]
            if grant_size < pkts_size:
                print("Однако")
            self.traf_mon_result[flow_id][cur_time] = (pkts_size, grant_size)
            # {имя сигнала : {время: данные сигнала}}
            return True

    def buffer_utilization_matcher(self, fig):
        pass

    def traffic_utilization_res_make(self, fig):

        def cook_summary_graph(flow_time_result, time_step):
            total_bits_sent = int()
            time_bw_result = dict()
            time_alloc_result = dict()
            for flow in flow_time_result:
                time_result = flow_time_result[flow]
                for t in time_result:
                    if t not in time_bw_result:
                        time_bw_result[t] = 0
                    if t not in time_alloc_result:
                        time_alloc_result[t] = 0
                    bw = time_result[t][0]
                    alloc = time_result[t][1]
                    time_bw_result[t] += bw
                    time_alloc_result[t] += alloc

            time_list = list(time_bw_result.keys())
            time_list.sort()
            last_time, end_time = min(time_list), max(time_list)
            bw_list = list()
            al_list = list()
            uti_list = list()
            time_stride = list()

            while end_time - last_time > 0:
                cur_min_t = last_time
                cur_max_t = last_time + time_step
                time_stride.append(cur_max_t)
                bw_t = sum(list(time_bw_result[tim]
                                for tim in time_list
                                if cur_min_t < tim <= cur_max_t))
                al_t = sum(list(time_alloc_result[tim]
                                for tim in time_list
                                if cur_min_t < tim <= cur_max_t))
                total_bits_sent += 8*bw_t
                bw_list.append(8 * bw_t / time_step)
                al_list.append(8 * al_t / time_step)
                last_time += time_step
                uti_list = np.array(bw_list) / np.array(al_list)
            return time_stride, bw_list, al_list, uti_list, total_bits_sent

        total_utilization_dict = dict()
        if len(self.traf_mon_result) == 0:
            return False
        flow_time_result = self.traf_mon_result
        number_of_flows = len(self.traf_mon_result) + 1
        time_step = 125
        time_result, bw_result, al_result, total_uti_result, _ =\
            cook_summary_graph(flow_time_result, time_step)
        subplot_index = 1
        ax = fig.add_subplot(number_of_flows, 2, subplot_index)
        plt.ylabel('total_bw')
        ax.plot(time_result, bw_result)
        ax.plot(time_result, al_result)
        subplot_index += 1
        total_bits_sent = sum(bw_result) * 125
        total_utilization = total_bits_sent / (2488.320*self.time_horizon)
        print("Полная утилизация", total_utilization)

        # график полной утилизации
        ax = fig.add_subplot(number_of_flows, 2, subplot_index)
        ax.plot(time_result, total_uti_result)
        subplot_index += 1

        # графики по потокам
        flows = list(flow_time_result.keys())
        flows.sort()
        for flow_name in flows:
            sig_res = flow_time_result[flow_name]
            time_result = list(sig_res.keys())
            time_result.sort()
            # график bw и alloc
            bw_result = list()
            alloc_result = list()
            last_time = int()
            # для пропускной способности
            # теперь надо пронормировать количество байт на временной интервал
            for sig_time in time_result:
                data_size, alloc_size = sig_res[sig_time]
                bw_result.append((8*data_size)/(sig_time - last_time))
                alloc_result.append((8*alloc_size)/(sig_time - last_time))
                last_time = sig_time

            ax = fig.add_subplot(number_of_flows, 2, subplot_index)
            subplot_index += 1
            plt.ylabel(flow_name)
            ax.plot(time_result, bw_result)
            ax.plot(time_result, alloc_result)
            fig.canvas.draw()

            # график утилизации. есть 2 функции
            # надо их поделить, получится утилизация
            time_start, time_end = min(time_result), max(time_result)
            # time_stride = np.arange(time_start, time_end, 125)
            bw_result = np.array(bw_result)
            alloc_result = np.array(alloc_result)
            utilization_result = bw_result / alloc_result
            ax = fig.add_subplot(number_of_flows, 2, subplot_index)
            ax.plot(time_result, utilization_result)
            ax.set_ylim(bottom=0)
            fig.canvas.draw()
            subplot_index += 1

            # plt.xlabel("Утилизация")
            total_bw = abs(np.trapz(bw_result, time_result))
            total_al = abs(np.trapz(alloc_result, time_result))
            total_utilization = round(total_bw / total_al, 1)
            if total_utilization < 0:
                print('странно')
            total_utilization_dict[flow_name] = total_utilization
        print("Утилизация по потокам:")
        for flow_name in flows:
            print(flow_name, round(total_utilization_dict[flow_name], 1))
        # ax.set_xticklabels(points_to_watch)
        fig.canvas.draw()
        fig.savefig(self.result_dir + "bw_utilization.png", bbox_inches="tight")
