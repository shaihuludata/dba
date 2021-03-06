import json
import logging
from simpy import Environment
from dba_pon_networks.net_fabric import NetFabric
import sys
import time

# TODO: 1. переделать логгинг

def timeit(method):
    def timed(*args, **kw):
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()
        if 'log_time' in kw:
            name = kw.get('log_name', method.__name__.upper())
            kw['log_time'][name] = int((te - ts) * 1000)
        else:
            print('%r  %2.2f ms' % \
                  (method.__name__, (te - ts) * 1000))
        return result
    return timed


def create_simulation():
    # исходные условия, описывающие контекст симуляции
    # sim_config имеет настройки:
    # "debug" - используется некоторыми классами для отображения отладочной информации
    # "horizon" - горизонт моделирования в микросекундах (максимальное симуляционное время)
    # "observers" - аспекты наблюдения классом observer за событиями модели
    # сюда же будут помещаться всякие исследуемые аспекты сети
    with open("./dba.json") as f:
        sim_config = json.load(f)

    # env - общая среда выполнения симуляционного процесса.
    # обеспечивает общее время и планирование всех событий, происходящих в модели
    # при включенном дебаге работает профилирование
    env = Environment()
    return env, sim_config


@timeit
def simulate(env, sim_config, jargs):
    time_horizon = sim_config["horizon"] if "horizon" in sim_config else 1000

    # структуры сетей описаны в соответствующей директории
    # там описаны устройства, их параметры и их соединения друг с другом
    net = json.load(open("./dba_pon_networks/network9.json"))
    kwargs = json.loads(jargs)
    if "DbaTMLinearFair_fair_multipliers" in kwargs:
        net["OLT0"].update(kwargs)
    logging.info("Net description: ", net)

    # описание сети net используется фабрикой для порождения устройств,
    # их соединения друг с другом в едином пространстве env
    # devices содержит список инициализированных устройств
    # obs - наблюдатель симуляции, накапливает информацию и
    # обрабатывает, выдаёт графики
    devices, obs = NetFabric().net_fabric(net, env, sim_config)

    # запуск симуляции
    logging.info("Start simulation")
    env.run(until=time_horizon)

    # по окончанию симуляции показать общие результаты
    logging.info("{} End of simulation ...".format(env.now),
          "\n***Preparing results***".format())

    # по окончанию отдельным потокам наблюдателя сообщить чтобы отключались
    obs.end_flag = True
    obs.ev_th_wait.wait()
    # накопленные наблюдателем obs результаты визуализировать
    # и сохранить в директорию result
    result = obs.make_results()
    return result


if __name__ == '__main__':
    # if len(sys.argv) > 1:
    #     jargs = sys.argv[1]
    # else:
    kwargs = {'DbaTMLinearFair_fair_multipliers': {0: {"bw": 1.0, "uti": 2},
                                                   1: {"bw": 0.9, "uti": 3},
                                                   2: {"bw": 0.8, "uti": 4},
                                                   3: {"bw": 0.7, "uti": 5}},
              'dba_min_grant': 10}
    jargs = json.dumps(kwargs, ensure_ascii=False).encode("utf-8")
    env, sim_config = create_simulation()
    ret = simulate(env, sim_config, jargs)
    print("___tpi={}___".format(ret))
