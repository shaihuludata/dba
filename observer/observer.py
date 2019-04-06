from threading import Thread
from threading import Event as ThEvent
from sympy import EmptySet, Interval
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from uni_traffic.packet import Packet
from pon.signal import Signal
import numpy as np
import collections
import re
import json
import logging
from memory_profiler import profile as mprofile


np.seterr(invalid="ignore", divide="ignore")


class Observer(Thread):
    result_dir = "./result/"
    # flow FlowObserver, power PhysicsObserver, traffic ReceivedTrafficObserver
    # mass_traffic MassTrafficObserver, BufferObserver BufferObserver

    def __init__(self, env, config):  # , daemon=True):
        Thread.__init__(self)
        self.env = env

        self.ev_read_data = ThEvent()
        self.ev_end_work = ThEvent()
        # current_time in msec
        self.cur_time = 0
        self.devices = None

        self.name = "CommonObserver"
        obs_conf = config["observers"]
        self.time_ranges_to_show = dict()
        # словарь содержит операции, ассоциированные с обозревателем
        # по ключам:
        #   flow - диаграммы потоков
        #   packets - мониторинг пакетов
        #   traffic_utilization - мониторинг утилизации ресурсов и буфферов
        #   total_per_flow_performance - интегральная оценка по потокам
        # по значениям - кортеж:
        # (проверка на соответствие условиям события, метод получения результата)
        observer_dict = {"flow": 0, "power": 0,
                         "packets": (self.packets_matcher,
                                     self.packets_res_make),
                         "traffic_utilization": ((self.traffic_utilization_matcher,
                                                  self.buffer_utilization_matcher),
                                                 self.traffic_utilization_res_make),
                         "buffers": 0,
                         "mass": 0,
                         "total_per_flow_performance": ()}
        # первые помещуются в match_conditions.
        # Наблюдатель прогоняет матчеры для сохранения результата
        self.match_conditions = list()
        # вторые используются для подготовки результата и его вывода
        # Наблюдатель прогоняет мэйкеры для обработки результата
        self.result_makers = list()
        # показывает, какие из наблюдений актуальны в симуляции
        self.observers_active = dict()

        for obs_name, cur_obs_conf in obs_conf.items():
            if cur_obs_conf["report"]:
                self.observers_active[obs_name] = cur_obs_conf["output"]
            if cur_obs_conf["report"] and "time_ranges" in cur_obs_conf:
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

        self.time_horizon = config["horizon"]

        # это буфер для новых данных,
        # потом обрабатываются в отдельном потоке и удаляются
        self.new_data = list()

        # _raw - сырые данные, полученные от матчеров
        # _result - обработанный и причёсанный результат
        # traffic_utilization
        self.traf_mon_raw = dict()
        self.traf_mon_result = dict()
        self.buffer_result = dict()
        # packets
        self.packets_raw = dict()
        self.packets_result = dict()
        # total_per_flow_performance
        self.global_flow_result = dict()
        self.flow_class = dict()
        self.flow_distance = dict()

    def show_progress(self):
        cur_time_in_msec = self.env.now // 1000
        if (cur_time_in_msec) > self.cur_time:
            progress = round(self.env.now / self.time_horizon, 1) * 100
            logging.info("Progress {}%, time {} ms".format(progress, cur_time_in_msec))
            self.cur_time = cur_time_in_msec

    def run(self):
        self.ev_end_work.clear()
        while True:
            self.show_progress()

            # wait for new data
            self.ev_read_data.wait(timeout=5)
            for i in self.new_data:
                # r_end, cur_time, dev, sig, port = i
                # defragmentation, cur_time, psink, pkt
                # put, cur_time, uni_port, pkt
                for matcher in self.match_conditions:
                    try:
                        matcher(*i)
                    except TypeError:
                        pass
                self.new_data.remove(i)
            # data processed ready for a new cycle
            self.ev_read_data.clear()
            if self.ev_end_work.is_set() and len(self.new_data) == 0:
                break
        logging.info("Observer finished")

    def notice(self, func):
        def wrapped(*args):
            data = list(args)
            data.insert(0, round(self.env.now, 3))
            data.insert(0, func.__name__)
            self.new_data.append(tuple(data))
            # new data should be processed in running thread
            self.ev_read_data.set()
            return func(*args)
        return wrapped

    # TODO: тут течёт
    def make_results(self):
        for res_make in self.result_makers:
            res_name, total_res, data_to_plot = res_make()

            if "figure" in self.observers_active[res_name]:
                self.export_data_to_figure(res_name, data_to_plot)
            if "json" in self.observers_active[res_name]:
                self.export_data_to_json(res_name, data_to_plot)

            if "total_per_flow_performance" in self.observers_active:
                if res_name not in self.global_flow_result:
                    self.global_flow_result[res_name] = dict()
                    self.global_flow_result[res_name].update(total_res)

        res_name = "device_counters"
        if res_name in self.observers_active:
            self.export_counters(self.devices)

        self.env = None
        res_name = "total_per_flow_performance"
        if res_name in self.observers_active:
            tpfp_res = self.make_total_per_flow_performance_result()
            if "json" in self.observers_active[res_name]:
                self.export_data_to_json(res_name, tpfp_res)
            # print(tpfp_res[0], tpfp_res[1])
            # for flow in tpfp_res[1]:
            #     print(flow, tpfp_res[2][flow])
            return tpfp_res[0]

    def make_total_per_flow_performance_result(self):
        """результате информационной свертки (редукции)
        некоторого подмножества
        индивидуальных показателей."""
        total_per_flow_performance_result = dict()

        # TODO: traffic performance auto-validation
        # TODO: нужно добавить fairness
        objective = json.load(open("./observer/net_performance.json"))
        normative = dict()
        normative.update(objective["ITU-T Y1540"])
        normative.update(objective["PON"])

        for flow_id in self.packets_raw:
            if "packets" in self.observers_active:
                self.flow_class[flow_id] = self.packets_raw[flow_id][1].cos
            if "traffic_utilization" in self.observers_active:
                a = min(list(self.traf_mon_raw[flow_id].keys()))
                self.flow_distance[flow_id] = self.traf_mon_raw[flow_id][a][2]

        glob_res = dict()
        for res_name in ["packets", "traffic_utilization"]:
            if res_name not in self.global_flow_result:
                print(res_name, "data absent")
                continue
            for flow_id in self.global_flow_result[res_name]:
                if flow_id not in glob_res:
                    glob_res[flow_id] = dict()
                glob_res[flow_id].update(self.global_flow_result[res_name][flow_id])
        self.global_flow_result = glob_res

        normalized_per_flow_result = dict()
        for flow_id in self.global_flow_result:
            flow_params = self.global_flow_result[flow_id]
            if flow_id not in self.flow_class:
                continue
            tr_class = self.flow_class[flow_id]
            # distance = self.flow_distance[flow_id]
            normalized_per_flow_result[flow_id] = par_result = dict()
            for par in ["IPTD", "IPDV", "IPLR", "uti", "bw", "buf"]:
                par_value = flow_params[par]
                n_par_value = normative[par][tr_class]
                if par == "IPTD":
                    n_par_value = float(n_par_value.split("+")[0]) * 1000 if n_par_value != "U" else float("Inf")
                    normalized_par_value = par_value / (n_par_value * 1.00)
                elif par == "IPDV":
                    n_par_value = float(n_par_value) * 1000 if n_par_value != "U" else float("Inf")
                    normalized_par_value = par_value / (n_par_value * 1.00)
                elif par == "IPLR":
                    n_par_value = float(n_par_value) if n_par_value != "U" else float("Inf")
                    normalized_par_value = par_value / (n_par_value * 1.00)
                elif par == "uti":
                    assert par_value <= 1
                    normalized_par_value = 1 - par_value
                elif par == "bw":
                    n_par_value = float(n_par_value)/1000000  # бит/с
                    normalized_par_value = 1 - par_value / n_par_value
                elif par == "buf":
                    n_par_value = int(n_par_value)
                    normalized_par_value = par_value / n_par_value
                else:
                    raise NotImplemented
                # if normalized_par_value > 1:
                #     normalized_par_value *= 10
                par_result[par] = round(normalized_par_value, 2)

        # normalized_result[tr_class][par] = par_result
        for flow_id in normalized_per_flow_result:
            total_per_flow_performance_result[flow_id] = round(sum(normalized_per_flow_result[flow_id].values())\
                                                         / len(normalized_per_flow_result[flow_id]), 2)
            # print(flow_id, normalized_per_flow_result[flow_id])
            # print(flow_id, total_per_flow_performance_result[flow_id])
        total_performance_index = sum(total_per_flow_performance_result.values())\
                                  / len(total_per_flow_performance_result)
        # print(total_performance_index)
        return round(total_performance_index, 2), total_per_flow_performance_result, normalized_per_flow_result

    def export_data_to_figure(self, res_name, data_to_plot):
        fig = plt.figure(1, figsize=(15, 15))
        number_of_flows = len(data_to_plot)
        flow_ids = list(flow_id for flow_id in data_to_plot)
        flow_ids.sort()
        subplot_index = 1
        for flow_name in flow_ids:
            columns = len(data_to_plot[flow_name])
            for tup in data_to_plot[flow_name]:
                ax = fig.add_subplot(number_of_flows, columns, subplot_index)
                plt.ylabel(flow_name)
                if res_name == "packets": style = "ro"
                elif res_name == "traffic_utilization": style = "--"
                else: style = "-"

                if isinstance(tup[1], tuple):
                    for graph in tup[1]:
                        ax.plot(tup[0], graph)
                else:
                    ax.plot(tup[0], tup[1], style)
                subplot_index += 1
        fig.show()
        out_filename = self.result_dir + res_name + ".png"
        fig.savefig(out_filename, bbox_inches="tight")
        plt.close(fig)
        logging.info("{} saved".format(out_filename))

    def export_data_to_json(self, res_name, data_to_plot):
        f = open(self.result_dir + res_name + ".json", "w")
        json.dump(data_to_plot, f)
        f.close()

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
        if flow_id not in self.packets_raw:
            self.packets_raw[flow_id] = dict()
        if pkt.num not in self.packets_raw[flow_id]:
            self.packets_raw[flow_id][pkt.num] = pkt

    def packets_res_make(self):
        data_total = dict()
        data_to_plot = dict()
        flows = list(self.packets_raw.keys())
        flows.sort()
        for flow_name in flows:
            # time_result = list(flow_time_result[flow_name].keys())
            pack_res = self.packets_raw[flow_name]
            pkt_nums = list(pack_res.keys())
            pkt_nums.sort()

            # график задержек
            latency_result = list()
            for pkt_num in pkt_nums:
                pkt = pack_res[pkt_num]
                latency_result.append(pkt.dfg_time - pkt.s_time)

            # график вариации задержек
            dv_result = list()
            basis_latency = min(latency_result)
            basis_latency = sum(latency_result) / len(latency_result)
            for pkt_num in pkt_nums:
                pkt = pack_res[pkt_num]
                dv = (pkt.dfg_time - pkt.s_time) - basis_latency
                dv_result.append(dv)

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

            if flow_name not in data_to_plot:
                data_to_plot[flow_name] = list()
            data_to_plot[flow_name].append((pkt_nums, latency_result))
            data_to_plot[flow_name].append((pkt_nums, dv_result))
            data_to_plot[flow_name].append((pkt_nums, lr_result))

            if flow_name not in data_total:
                data_total[flow_name] = dict()
            data_total[flow_name]["IPTD"] = max(latency_result)
            data_total[flow_name]["IPDV"] = abs(max(dv_result))
            data_total[flow_name]["IPLR"] = lr_result[-1]
        return "packets", data_total, data_to_plot

    def traffic_utilization_matcher(self, operation, cur_time, dev, sig: Signal, port):
        if operation is not "r_end":
            return False
        if cur_time not in self.time_ranges_to_show["traffic_utilization"]:
            return False
        if "OLT" not in dev.name:
            return False
        for flow_id in sig.data:
            if "ONT" not in flow_id:
                continue
            if flow_id not in self.traf_mon_raw:
                self.traf_mon_raw[flow_id] = dict()
            # TODO: разобраться почему тут ошибка
            # assert cur_time not in self.traf_mon_raw[flow_id]
            pkts = sig.data[flow_id]
            pkts_size = sum(list(pkt.size for pkt in pkts))
            grant_size = sig.data["grant_size"]
            if grant_size < pkts_size:
                print("Однако")
            distance = sig.physics["distance_passed"]
            self.traf_mon_raw[flow_id][cur_time] = (pkts_size, grant_size, distance)
            # {имя сигнала : {время: данные сигнала}}
            return True

    def buffer_utilization_matcher(self, operation, cur_time, dev, pkt):
        if operation is not "put":
            return False
        if cur_time not in self.time_ranges_to_show["traffic_utilization"]:
            return False
        if "Uni" not in dev.__class__.__name__:
            return False
        flow_id = pkt.flow_id
        if flow_id not in self.buffer_result:
            self.buffer_result[flow_id] = dict()
        self.buffer_result[flow_id][cur_time] = dev.byte_size  # len(dev.store.items)

    def traffic_utilization_res_make(self):
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
                try:
                    uti_list = np.array(bw_list) / np.array(al_list)
                except RuntimeWarning:
                    print(bw_list, al_list)
            return time_stride, bw_list, al_list, uti_list, total_bits_sent

        data_total = dict()
        data_to_plot = dict()
        total_utilization_dict = dict()
        if len(self.traf_mon_raw) == 0:
            return False
        flow_time_result = self.traf_mon_raw
        number_of_flows = len(self.traf_mon_raw) + 1
        time_step = 125
        # total_uti_result - график полной утилизации
        time_result, bw_result, al_result, total_uti_result, _ =\
            cook_summary_graph(flow_time_result, time_step)

        total_bits_sent = sum(bw_result) * 125
        total_utilization = total_bits_sent / (2488.320*self.time_horizon)
        # print("Полная утилизация", total_utilization)

        # графики по потокам
        flows = list(flow_time_result.keys())
        flows.sort()
        for flow_name in flows:
            sig_res = flow_time_result[flow_name]
            time_result = list(sig_res.keys())
            time_result.sort()
            # график bw и alloc
            bw_result = list()
            al_result = list()
            last_time = int()
            # для пропускной способности
            # теперь надо пронормировать количество байт на временной интервал
            for sig_time in time_result:
                data_size, alloc_size, distance = sig_res[sig_time]
                delta_time = sig_time - last_time
                # bw_result - в бит/мкс - в мегабитах/сек
                bw_result.append(round((8*data_size)/(delta_time), 3))
                al_result.append(round((8*alloc_size)/(delta_time), 3))
                last_time = sig_time

            # график утилизации. есть 2 функции
            # надо их поделить, получится утилизация
            time_start, time_end = min(time_result), max(time_result)
            # time_stride = np.arange(time_start, time_end, 125)
            np_bw_result = np.array(bw_result)
            np_al_result = np.array(al_result)
            np_uti_result = np_bw_result / np_al_result
            uti_result = list(np_uti_result)

            total_bw = abs(np.trapz(np_bw_result, time_result))
            total_al = abs(np.trapz(np_al_result, time_result))
            total_utilization = round(total_bw / total_al, 1)
            if total_utilization < 0:
                logging.critical('странно')
            total_utilization_dict[flow_name] = total_utilization
            # print("Утилизация в потоке", flow_name, round(total_utilization_dict[flow_name], 1))

            # и отдельно график занятости буферов
            cur_buf_result = self.buffer_result[flow_name]
            buf_time_result = list(cur_buf_result.keys())
            buf_time_result.sort()
            buf_result = list(cur_buf_result[t] for t in buf_time_result)

            # data_to_plot["total_bw"].append(time_result, total_uti_result)
            if flow_name not in data_to_plot:
                data_to_plot[flow_name] = list()
            data_to_plot[flow_name].append((time_result, (bw_result, al_result)))
            data_to_plot[flow_name].append((time_result, uti_result))
            data_to_plot[flow_name].append((buf_time_result, buf_result))
            # data_to_plot[flow_name].append((time_result, buf_result))

            data_total["total"] = {"uti": total_utilization}
            if flow_name not in data_total:
                data_total[flow_name] = dict()
            data_total[flow_name]["uti"] = round(sum(np_uti_result)/len(np_uti_result), 2)
            data_total[flow_name]["bw"] = round(sum(bw_result)/len(bw_result), 2)
            data_total[flow_name]["buf"] = max(buf_result)
        return "traffic_utilization", data_total, data_to_plot

    @staticmethod
    def export_counters(devices):
        for dev_name, dev in devices.items():
            if re.search("[ON|LT]", dev_name) is not None:
                print("{} : {}".format(dev_name, dev.counters.export_to_console()))
            if re.search("OLT", dev_name) is not None:
                print("{} : {}".format("OLT0_recv", dev.p_sink.p_counters.export_to_console()))
            if re.search("ONT", dev_name) is not None:
                for tg_name in dev.traffic_generators:
                    tg = dev.traffic_generators[tg_name]
                    print("{} : {}".format(tg_name, tg.p_counters.export_to_console()))
