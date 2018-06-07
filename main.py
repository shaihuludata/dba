import json
import time
import cProfile
import logging
import simpy
import re
from net_fabric import NetFabric


def profile(func):
    """
    Профилирующий декоратор полезен для поиска критически замедляющих участков кода
    # python3 -m cProfile -o ./proceed.prof ./main.py
    # gprof2dot -f pstats proceed.prof | dot -Tpng -o proceed.png
    """
    def wrapper(*args, **kwargs):
        profile_filename = './result/' + func.__name__ + '.prof'
        profiler = cProfile.Profile()
        result = profiler.runcall(func, *args, **kwargs)
        profiler.dump_stats(profile_filename)
        return result
    return wrapper


class ProfiledEnv(simpy.Environment):
    @profile
    def run(self, until=None):
        simpy.Environment.run(self, until)


def main():
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
    net = json.load(open("./networks/network7.json"))
    logging.info("Net description: ", net)

    # env - общая среда выполнения симуляционного процесса.
    # обеспечивает общее время и планирование всех событий, происходящих в модели
    # при включенном дебаге работает профилирование
    env = ProfiledEnv() if sim_config["debug"] else simpy.Environment()

    # описание сети net используется фабрикой для порождения устройств,
    # их соединения друг с другом в едином пространстве env
    nf = NetFabric()
    devices, obs = nf.net_fabric(net, env, sim_config)

    # t_start нужен, чтобы оценить длительность выполнения
    t_start = time.time()
    # запуск симуляции
    env.run(until=time_horizon)

    # по окончанию симуляции показать общие результаты
    print("{} End of simulation in {}...".format(env.now, round(time.time() - t_start, 2)),
          "\n***Preparing results***".format())
    for dev_name in devices:
        if re.search("[ON|LT]", dev_name) is not None:
            dev = devices[dev_name]
            print("{} : {}".format(dev_name, dev.counters.export_to_console()))
        if re.search("OLT", dev_name) is not None:
            print("{} : {}".format("OLT0_recv", dev.p_sink.p_counters.export_to_console()))
        if re.search("ONT", dev_name) is not None:
            for tg_name in dev.traffic_generators:
                tg = dev.traffic_generators[tg_name]
                print("{} : {}".format(tg_name, tg.p_counters.export_to_console()))

    # накопленные наблюдателем obs результаты визуализировать и сохранить в директорию result
    obs.make_results()
    # а по окончанию отдельным потокам наблюдателя сообщить чтобы отключались
    obs.end_flag = True


if __name__ == '__main__':
    main()
