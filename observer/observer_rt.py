from threading import Thread
from threading import Event as ThEvent
from sympy import EmptySet, Interval


class DevObserverRealTime(Thread):
    result_dir = "./result/"

    def __init__(self, config):
        Thread.__init__(self)
        self.name = "Traffic visualizer"
        # {dev.name + "::" + port: [(time, sig.__dict__)]}
        time_ranges_to_show = config["observers"]["flow"]["time_ranges"]
        self.time_ranges_to_show = EmptySet().union(Interval(i[0], i[1]) for i in time_ranges_to_show)
        self.match_conditions = [self.traf_vis_cond]
        self.result_makers = [self.traf_vis_res_rt]
        self.time_horizon = max(self.time_ranges_to_show.boundary)
        self.new_data = list()
        self.observer_result = dict()
        self.traf_mon_raw = dict()
        self.traf_mon_raw_new_data = dict()
        self.traf_mon_flow_indexes = dict()
        self.ev_wait = ThEvent()

    def run(self):
        fig = plt.figure(1, figsize=(15, 15))
        fig.show()
        self.ev_wait.wait(timeout=5)  # wait for event
        for i in self.new_data:
            cur_time, sig, dev, operation = i
            for matcher in self.match_conditions:
                matcher(*i)
            for res_make in self.result_makers:
                res_make(fig)
            self.new_data.remove(i)
            self.ev_wait.clear()  # clean event for future

    def notice(self, func):
        def wrapped(dev, sig, port):
            cur_time = sig.env.now
            self.new_data.append((cur_time, sig, dev, func.__name__))
            self.ev_wait.set()
            return func(dev, sig, port)
        return wrapped

    def traf_vis_cond(self, cur_time, sig, dev, operation):
        if cur_time not in self.time_ranges_to_show:
            return False
        if "OLT" not in dev.name:
            return False
        if operation is not "r_end":
            return False
        for flow_id in sig.data:
            if "ONT" not in flow_id:
                continue
            if flow_id not in self.traf_mon_raw:
                self.traf_mon_raw[flow_id] = dict()
                cur_index = max(self.traf_mon_flow_indexes.values()) + 1\
                    if len(self.traf_mon_flow_indexes) > 0\
                    else 0
                self.traf_mon_flow_indexes[flow_id] = cur_index
            assert cur_time not in self.traf_mon_raw[flow_id]
            pkts = sig.data[flow_id]
            self.traf_mon_raw[flow_id][cur_time] = pkts
            # self.traf_mon_raw_new_data[flow_id][cur_time] = pkts
            # {имя сигнала : {время: данные сигнала}}
        return True

    def traf_vis_res_rt(self, fig):
        # number_of_sigs = len(self.observer_result)
        flow_time_result = self.traf_mon_raw
        flow_pack_result = dict()
        for flow in flow_time_result:
            time_result = flow_time_result[flow]
            flow_pack_result[flow] = dict()
            for time_r in time_result:
                pkts = time_result[time_r]
                for pkt in pkts:
                    pkt.e_time = time_r
                    flow_pack_result[flow][pkt.num] = pkt
        number_of_flows = len(self.traf_mon_flow_indexes)
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
                latency_result.append(pkt.e_time - pkt.s_time)
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
        # plt.show()
        fig.savefig(self.result_dir + "packets_static_allocs.png", bbox_inches="tight")

    def make_results(self):
        pass
        # for res_make in self.result_makers:
        #     fig = plt.figure(1, figsize=(15, 15))
        #     fig.show()
        #     res_make(fig)
