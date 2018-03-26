import json
from time import sleep
from scheduler import ModelScheduler


def main():
    net = json.load(open('./network.json'))
    print('Net description: ', net)
    sched = ModelScheduler(net, 'basic_NSC')
    time_horisont = 500
    # timestep = 125
    # timesteps = time_horisont // timestep
    cur_time = 0
    while (cur_time < time_horisont):
        sched.renew_schedule(cur_time)
        cur_time = min(sched.schedule)
        print('time: {}'.format(cur_time))
        print(sched.schedule)
        sched.proceed_schedule(cur_time)
        sleep(1)


if __name__ == '__main__':
    main()
