import json
import time
import logging
import simpy
from dba_pon_networks.net_fabric import NetFabric
from support.profiling import profile, timeit


class ProfiledEnv(simpy.Environment):
    @timeit
    @profile
    def run(self, until=None):
        simpy.Environment.run(self, until)

@timeit
def simulate(jargs):
    # исходные условия, описывающие контекст симуляции
    # sim_config имеет настройки:
    # "debug" - используется некоторыми классами для отображения отладочной информации
    # "horizon" - горизонт моделирования в микросекундах (максимальное симуляционное время)
    # "observers" - аспекты наблюдения классом observer за событиями модели
    # сюда же будут помещаться всякие исследуемые аспекты сети
    sim_config = json.load(open("./dba.json"))
    time_horizon = sim_config["horizon"] if "horizon" in sim_config else 1000

    # структуры сетей описаны в соответствующей директории
    # там описаны устройства, их параметры и их соединения друг с другом
    net = json.load(open("./dba_pon_networks/network8.json"))
    kwargs = json.loads(jargs)
    if "DbaTMLinearFair_fair_multipliers" in kwargs:
        net["OLT0"].update(kwargs)
    logging.info("Net description: ", net)

    # env - общая среда выполнения симуляционного процесса.
    # обеспечивает общее время и планирование всех событий, происходящих в модели
    # при включенном дебаге работает профилирование
    env = ProfiledEnv() if sim_config["debug"] else simpy.Environment()

    # описание сети net используется фабрикой для порождения устройств,
    # их соединения друг с другом в едином пространстве env
    # devices содержит список инициализированных устройств
    # obs - наблюдатель симуляции, накапливает информацию и обрабатывает, выдаёт графики
    devices, obs = NetFabric().net_fabric(net, env, sim_config)

    # запуск симуляции
    env.run(until=time_horizon)

    # по окончанию симуляции показать общие результаты
    print("{} End of simulation ...".format(env.now),
          "\n***Preparing results***".format())

    # по окончанию отдельным потокам наблюдателя сообщить чтобы отключались
    obs.end_flag = True
    obs.ev_th_wait.wait()
    # накопленные наблюдателем obs результаты визуализировать и сохранить в директорию result
    result = obs.make_results()
    del obs
    for dev in devices:
        del dev
    del env
    return result


if __name__ == '__main__':
    kwargs = {'DbaTMLinearFair_fair_multipliers': {0: {"bw": 1.0, "uti": 2},
                                                   1: {"bw": 0.9, "uti": 3},
                                                   2: {"bw": 0.8, "uti": 4},
                                                   3: {"bw": 0.7, "uti": 5}},
              'dba_min_grant': 10}
    # kwargs = {'DbaTMLinearFair_fair_multipliers': {0: {'bw': 7.8, 'uti': 5.6},
    #                                                1: {'bw': 1.2, 'uti': 2.4},
    #                                                2: {'bw': 4.9, 'uti': 9.8},
    #                                                3: {'bw': 9.6, 'uti': 9.2}},
    #           'dba_min_grant': 99}
    simulate(**kwargs)
