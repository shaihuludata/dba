import json
import time
import cProfile
import logging
import simpy
import re
from net_fabric import NetFabric

# python3 -m cProfile -o ./proceed.prof ./main.py
# gprof2dot -f pstats proceed.prof | dot -Tpng -o proceed.png


def profile(func):
    """Decorator for run function profile"""
    def wrapper(*args, **kwargs):
        profile_filename = './result/' + func.__name__ + '.prof'
        profiler = cProfile.Profile()
        result = profiler.runcall(func, *args, **kwargs)
        profiler.dump_stats(profile_filename)
        return result
    return wrapper


def bandwidth_prognosis(net):
    max_bw_prognosis = float()
    allocs = list()
    bws = list()
    for dev in net:
        if 'ONT' in dev:
            allocs.extend(net[dev]["Alloc"].values())
    typs = json.load(open('./uni_traffic/traffic_types.json'))
    for typ_name in allocs:
        typ = typs["traffic"][typ_name]
        bw = round(8 * 1 * typ["size_of_packet"] / typ["send_interval"], 3)
        bws.append(bw)
        print(typ_name, bw)
    max_bw_prognosis = round(sum(bws), 3)
    return max_bw_prognosis


def main():
    sim_config = json.load(open("./dba.json"))
    net = json.load(open("./networks/network3.json"))
    time_horizon = sim_config["horizon"] if "horizon" in sim_config else 1000
    logging.info("Net description: ", net)
    max_bw = bandwidth_prognosis(net)
    print("Максимальная прогнозная нагрузка {} Мбит/с".format(max_bw))

    env = simpy.Environment()
    nf = NetFabric()
    devices, obs = nf.net_fabric(net, env, sim_config)
    t_start = time.time()
    env.run(until=time_horizon)

    print("{} End of simulation in {}...".format(env.now, round(time.time() - t_start, 2)),
          "\n***Preparing results***".format())
    for dev_name in devices:
        if re.search("[ON|LT]", dev_name) is not None:
            dev = devices[dev_name]
            print("{} : {}".format(dev_name, dev.counters.export_to_console()))
        if re.search("ONT", dev_name) is not None:
            for tg_name in dev.traffic_generators:
                tg = dev.traffic_generators[tg_name]
                print("{} : {}".format(tg_name, tg.p_counters.export_to_console()))

    obs.make_results()
    obs.end_flag = True


if __name__ == '__main__':
    main()
