import json
from time import sleep
import time
from scheduler import ModelScheduler
import cProfile
import pprint

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
    max_bw_prognose = float()
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
    max_bw_prognose = round(sum(bws), 3)
    return max_bw_prognose


def main():  # *args, **kwargs):
    config = json.load(open('./dba.json'))
    if "horisont" in config:
        time_horisont = config["horisont"]
    else:
        time_horisont = 1000

    net = json.load(open('./networks/network6.json'))
    print('Net description: ', net)
    sched = ModelScheduler(net, config)
    max_bw = bandwidth_prognosis(net)
    print('Максимальная прогнозная нагрузка {} Мбит/с'.format(max_bw))
    cur_time = 0

    cur_report = 0
    step_report = 1000
    last_time = time.time()
    times = list()
    while cur_time < time_horisont and len(sched.schedule.events) > 0:
        cur_time = min(sched.schedule.events)
        if cur_time >= cur_report:
            delta = round(time.time() - last_time, 2)
            print('Time: {}, delta {}'.format(cur_report, delta))
            cur_report += step_report
            times.append(delta)
            last_time = time.time()
        # print('time: {}'.format(cur_time))
        # print(sched.schedule)
        if cur_time > 3000:
            profile(sched.proceed_schedule(cur_time))
        else:
            sched.proceed_schedule(cur_time)

    print('End of simulation... Preparing results.')
    sched.make_results()


if __name__ == '__main__':
    main()
