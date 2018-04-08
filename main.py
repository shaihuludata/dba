import json
from time import sleep
from scheduler import ModelScheduler


def main():
    net = json.load(open('./networks/network4.json'))
    print('Net description: ', net)
    sched = ModelScheduler(net)
    time_horisont = 15000
    cur_time = 0
    while cur_time < time_horisont and len(sched.schedule.events) > 0:
        cur_time = min(sched.schedule.events)
        print('time: {}'.format(cur_time))
        #print(sched.schedule)
        sched.proceed_schedule(cur_time)
        #sleep(1)
        if cur_time > 10000:
            pass

    sched.make_results()
    print('End of simulation')


if __name__ == '__main__':
    main()
