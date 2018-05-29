from threading import Thread
from threading import Event as ThEvent
from sympy import EmptySet, Interval
import matplotlib.pyplot as plt
from uni_traffic.packet import Packet


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
        observer_dict = {"flow": 0, "power": 0,
                         "packets": (self.packets_matcher, self.packets_res_make),
                         "traffic_utilization": (self.traffic_utilization_matcher, self.traffic_utilization_res_make),
                         "buffers": 0, "mass": 0}
        self.match_conditions = list()
        self.result_makers = list()
        for obs_name in obs_conf:
            cur_obs_conf = obs_conf[obs_name]
            if cur_obs_conf["report"]:
                time_ranges = cur_obs_conf["time_ranges"]
                self.time_ranges_to_show[obs_name] = EmptySet().union(Interval(i[0], i[1]) for i in time_ranges)
                matcher = observer_dict[obs_name][0]
                self.match_conditions.append(matcher)
                res_maker = observer_dict[obs_name][1]
                self.result_makers.append(res_maker)

        self.time_horizon = max(list(max(self.time_ranges_to_show[i].boundary) for i in self.time_ranges_to_show))
        self.time_horizon = max(config["horizon"], self.time_horizon)

        self.new_data = list()
        self.traf_mon_result = dict()
        self.traf_mon_flow_indexes = dict()
        self.packets_result = dict()
        self.ev_wait = ThEvent()
        self.end_flag = False

    def run(self):
        while not self.end_flag:
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

    def make_results(self):
        for res_make in self.result_makers:
            fig = plt.figure(1, figsize=(15, 15))
            fig.show()
            res_make(fig)

    def packets_matcher(self, operation, cur_time, psink, pkt: Packet):
        if operation is not "check_dfg_pkt":
            return False
        if pkt is None:
            return False
        if cur_time not in self.time_ranges_to_show["packets"]:
            return False
        flow_id = pkt.flow_id
        if flow_id not in self.packets_result:
            self.packets_result[flow_id] = dict()
        if pkt.num not in self.packets_result[flow_id]:
            self.packets_result[flow_id][pkt.num] = pkt

    def packets_res_make(self, fig):
        number_of_flows = len(self.packets_result)
        flow_pack_result = self.packets_result
        subplot_index = 1
        for flow_name in flow_pack_result:
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
                dv = (pkt.e_time - pkt.s_time) / basis_latency
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
        fig.savefig(self.result_dir + "packets.png", bbox_inches="tight")

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
                cur_index = max(self.traf_mon_flow_indexes.values()) + 1\
                    if len(self.traf_mon_flow_indexes) > 0\
                    else 0
                self.traf_mon_flow_indexes[flow_id] = cur_index
            assert cur_time not in self.traf_mon_result[flow_id]
            pkts = sig.data[flow_id]
            self.traf_mon_result[flow_id][cur_time] = pkts
            # self.traf_mon_result_new_data[flow_id][cur_time] = pkts
            # {имя сигнала : {время: данные сигнала}}
        return True

    def traffic_utilization_res_make(self, fig):
        # number_of_sigs = len(self.observer_result)
        flow_time_result = self.traf_mon_result
        # flow_pack_result = dict()
        # for flow in flow_time_result:
        #     time_result = flow_time_result[flow]
        #     flow_pack_result[flow] = dict()
        #     for time_r in time_result:
        #         pkts = time_result[time_r]
        #         for pkt in pkts:
        #             pkt.e_time = time_r
        #             flow_pack_result[flow][pkt.num] = pkt
        number_of_flows = len(self.traf_mon_flow_indexes)
        subplot_index = 1
        for flow_name in flow_time_result:
            pack_res = flow_time_result[flow_name]
            time_result = list(pack_res.keys())
            time_result.sort()
            # график bw и alloc
            bw_result = list()
            alloc_result = list()
            last_time = int()

            for pkt_time in time_result:
                pkts = pack_res[pkt_time]
                bw_result.append(8*sum(list(pkt.size for pkt in pkts))/(pkt_time - last_time))
                alloc_result.append(8*sum(list(pkt.alloc for pkt in pkts))/(pkt_time - last_time))

            ax = fig.add_subplot(number_of_flows, 2, subplot_index)
            subplot_index += 1
            plt.ylabel(flow_name)
            ax.plot(time_result, bw_result)
            ax.plot(time_result, alloc_result)
            fig.canvas.draw()

            # график утилизации
            # dv_result = list()
            # basis_latency = min(latency_result)
            # basis_latency = sum(latency_result) / len(latency_result)
            # for pkt_num in pkt_nums:
            #     pkt = pack_res[pkt_num]
            #     dv = (pkt.e_time - pkt.s_time) / basis_latency
            #     dv_result.append(dv)
            # ax = fig.add_subplot(number_of_flows, 2, subplot_index)
            # subplot_index += 1
            # # plt.ylabel(flow_name)
            # ax.plot(pkt_nums, dv_result, "ro")
            # min_dv = min(dv_result)
            # max_dv = max(dv_result)
            # ax.set_ylim(bottom=min_dv - 1, top=max_dv + 1)
            # fig.canvas.draw()

        # ax.set_xticklabels(points_to_watch)
        fig.canvas.draw()
        # plt.show()
        fig.savefig(self.result_dir + "bw_utilization.png", bbox_inches="tight")
