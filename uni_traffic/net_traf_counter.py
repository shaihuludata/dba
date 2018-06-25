from uni_traffic.builders import TrafficGeneratorBuilder
import simpy
from uni_traffic.traffic_components import PacketSink
import json
import matplotlib.pyplot as plt
from numpy import correlate
from support.profiling import timeit


class PacketSink_traf_counter(PacketSink):
    def __init__(self, env, debug=True):
        PacketSink.__init__(self, env, debug=True)
        self.total_kbits = 0
        self.time_bw = dict()

    def put(self, pkt):
        if self.env.now not in self.time_bw:
            self.time_bw[self.env.now] = 0
        self.time_bw[self.env.now] += pkt.size
        PacketSink.put(self, pkt)

    def check_dfg_pkt(self, dfg):
        if self.debug:
            print(round(self.env.now, 3), dfg)
            self.total_kbits += 8*dfg.size
            # print(self.total_kbits)


@timeit
def calc_thr(traf_types="./traffic_types.json", net_desc="../dba_pon_networks/network9.json"):
    tgb = TrafficGeneratorBuilder(traf_types)
    env = simpy.Environment()
    net_name = net_desc.split("/")[-1].split(".")[0]
    net = json.load(open(net_desc))

    ps = PacketSink_traf_counter(env, debug=True)  # debugging enable for simple output
    traffic_activation_time = tat = 0
    tgs = list()
    for dev_name in net:
        if "ONT" in dev_name:
            ont = net[dev_name]
            allocs = ont["Alloc"]
            for al in allocs:
                alloc_type = allocs[al]
                tg = tgb.packet_source(env, dev_name+al, alloc_type, tat)
                tg.out = ps
                tgs.append(tg)

    horizon = 400000
    env.run(until=horizon)

    t_stride = list(ps.time_bw.keys())
    t_stride.sort()
    bw = list()
    t_last = min(t_stride)
    for t in t_stride:
        if t == min(t_stride):
            bw.append(0)
            continue
        cur_bw = ps.time_bw[t] / (t - t_last)
        bw.append(cur_bw)
        t_last = t

    fig = plt.figure(1, figsize=(15, 15))
    ax = fig.add_subplot(1, 2, 1)
    ax.plot(t_stride, bw)

    f = open("./" + net_name + ".json", "w")
    json.dump((t_stride, bw), f)
    f.close()

    # cor = correlate(bw, bw, mode="full")
    # ax = fig.add_subplot(1, 2, 2)
    # ax.plot(cor)

    fig.show()
    fig.savefig("./" + net_name + ".png", bbox_inches="tight")
    plt.close(fig)
    print("Итог: {} kbps".format(ps.total_kbits/horizon*1000))

calc_thr()
