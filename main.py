import json
import time
import cProfile
import logging
import simpy
from networks.net_fabric import NetFabric


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
    # devices содержит список инициализированных устройств
    # obs - наблюдатель симуляции, накапливает информацию и обрабатывает, выдаёт графики
    devices, obs = NetFabric().net_fabric(net, env, sim_config)

    # t_start нужен, чтобы оценить длительность выполнения
    t_start = time.time()
    # запуск симуляции
    env.run(until=time_horizon)

    # по окончанию симуляции показать общие результаты
    print("{} End of simulation in {}...".format(env.now, round(time.time() - t_start, 2)),
          "\n***Preparing results***".format())
    obs.export_counters(devices)
    # накопленные наблюдателем obs результаты визуализировать и сохранить в директорию result
    obs.make_results()
    # а по окончанию отдельным потокам наблюдателя сообщить чтобы отключались
    obs.end_flag = True


if __name__ == '__main__':
    main()
