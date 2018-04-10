import json
from time import sleep
from scheduler import ModelScheduler


def main():
    net = json.load(open('./networks/network4.json'))
    print('Net description: ', net)
    sched = ModelScheduler(net)
    time_horisont = 10000
    cur_time = 0
    while cur_time < time_horisont and len(sched.schedule.events) > 0:
        cur_time = min(sched.schedule.events)
        print('time: {}'.format(cur_time))
        #print(sched.schedule)
        sched.proceed_schedule(cur_time)
        #sleep(1)

    print('End of simulation... Preparing results.')
    sched.make_results()


if __name__ == '__main__':
    main()
