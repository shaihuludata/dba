import json
import time
import cProfile
import logging
import simpy
import re
from pon.olt import Olt
from pon.ont import Ont
from pon.opaque import Fiber, Splitter

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
        typ = typs[typ_name]
        bw = round(8 * 1 * typ["size_of_packet"] / typ["send_interval"], 3)
        bws.append(bw)
        print(typ_name, bw)
    max_bw_prognosis = round(sum(bws), 3)
    return max_bw_prognosis


def net_fabric(net, env, sim_config):
    # obs = Observer(sim_config)
    # obs.start()
    classes = {"OLT": Olt, "ONT": Ont, "Splitter": Splitter, "Fiber": Fiber}
    devices = dict()
    connection = dict()
    # Create devices
    for dev_name in net:
        config = net[dev_name]
        for dev_type in classes:
            if dev_type in dev_name:
                constructor = classes[dev_type]
                dev = constructor(env, dev_name, config)
                # dev.observer = obs
                devices[dev_name] = dev
                connection[dev_name] = config["ports"]
    # Interconnect devices
    for dev_name in connection:
        l_dev = devices[dev_name]
        con = connection[dev_name]
        for l_port in con:
            r_dev_name, r_port = con[l_port].split("::")
            r_dev = devices[r_dev_name]
            l_port = int(l_port)
            l_dev.out[l_port] = (int(r_port), r_dev)
    return devices


def main():
    sim_config = json.load(open("./dba.json"))
    net = json.load(open("./networks/network6.json"))
    time_horizon = sim_config["horizon"] if "horizon" in sim_config else 1000
    logging.info("Net description: ", net)
    max_bw = bandwidth_prognosis(net)
    print("Максимальная прогнозная нагрузка {} Мбит/с".format(max_bw))

    env = simpy.Environment()
    devices = net_fabric(net, env, sim_config)
    t_start = time.time()
    env.run(until=time_horizon)

    print("{} End of simulation in {}...".format(env.now, round(time.time() - t_start, 2)),
          "\n***Preparing results***".format())
    for dev_name in devices:
        if re.search("[ON|LT]", dev_name) is not None:
            dev = devices[dev_name]
            print("{} : {}".format(dev_name, dev.counters.export_to_console()))

    Dev.observer.make_results()
    Dev.observer.end_flag = True


if __name__ == '__main__':
    main()
