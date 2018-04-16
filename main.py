import json
from time import sleep
from scheduler import ModelScheduler


def main():
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

    while cur_time < time_horisont and len(sched.schedule.events) > 0:
        cur_time = min(sched.schedule.events)
        if cur_time >= cur_report:
            print('Time: {}'.format(cur_report))
            cur_report += step_report
        #print('time: {}'.format(cur_time))
        #print(sched.schedule)
        sched.proceed_schedule(cur_time)
        #sleep(10)

    print('End of simulation... Preparing results.')
    sched.make_results()


if __name__ == '__main__':
    main()
