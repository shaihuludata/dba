from dba.dba import Dba


class Dba_SR(Dba):
    # минимальный размер гранта при утилизации 0
    min_grant = 10

    def __init__(self, env, config, snd_sig):
        Dba.__init__(self, env, config, snd_sig)
        self.mem_size = 10
        # для хранения текущих значений утилизации
        self.alloc_utilisation = dict()
        # для хранения информации о выданных грантах
        self.alloc_grants = dict()
        # для хранения информации о размерах полученных пакетов
        self.alloc_bandwidth = dict()
        self.alloc_max_bandwidth = dict()
        # для хранения информации о классах alloc"ов
        self.alloc_class = dict()
