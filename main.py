import json
from time import sleep
import time
from scheduler import ModelScheduler
import cProfile

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


def main():#*args, **kwargs):
    config = json.load(open('./dba.json'))
    if "horisont" in config:
        time_horisont = config["horisont"]
    else:
        time_horisont = 1000

    net = json.load(open('./networks/network4.json'))
    print('Net description: ', net)
    sched = ModelScheduler(net, config)
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
        # sleep(10)

    print('End of simulation... Preparing results.')
    sched.make_results()
    print(times)


if __name__ == '__main__':
    main()
