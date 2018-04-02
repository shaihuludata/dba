import json
from time import sleep
from scheduler import ModelScheduler


def main():
    net = json.load(open('./networks/network3.json'))
    print('Net description: ', net)
    sched = ModelScheduler(net)
    time_horisont = 500
    cur_time = 0
    while cur_time < time_horisont and len(sched.schedule) > 0:
        cur_time = min(sched.schedule)
        print('time: {}'.format(cur_time))
        #print(sched.schedule)
        sched.proceed_schedule(cur_time)
        #sleep(1)

    sched.make_results()
    print('End of simulation')


if __name__ == '__main__':
    main()
