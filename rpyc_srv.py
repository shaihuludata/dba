import rpyc
from rpyc.utils.registry import TCPRegistryServer, TCPRegistryClient
from rpyc.utils.server import Server, ThreadedServer, ForkingServer
import socket
# from main import simulate
from threading import Thread
from functools import wraps
import json
from multiprocessing import Pool
from multiprocessing.dummy import Pool as ThPool
import time


def fake_sim(*args, **kwargs):
    print("Получил условия: {}".format(kwargs))
    print("Типа симулирую")
    time.sleep(60)
    print("Типа досимулировал")
    return 1


class MyService(rpyc.Service):
    def __init__(self):
        self.exposed_simulate = fake_sim


MY_HOSTNAME = "10.22.252.100"
REGISTRY_PORT = 18811
RPYC_PORT = 12345


class ReggaeSrv:
    S_STATE_INITIAL = "Offline"
    S_STATE_REGISTERED = "Registered"
    S_STATE_WORKING = "Working"
    S_SERVICE = "REMOTESIM"
    def __init__(self, registry=TCPRegistryServer):
        self.registry = registry()
        self.hostname = socket.gethostname()

    def registry_async(self):
        func = self.registry.start
        @wraps(func)
        def async_func(*args, **kwargs):
            func_hl = Thread(target=func, args=args, kwargs=kwargs)
            func_hl.start()
            return func_hl
        return async_func

    def rpyc_connect_to_simulate(self, args):
        cond, s_host, sim_args = args
        # conn = rpyc.connect(s_host, RPYC_PORT, config={'sync_request_timeout': 70})
        # tpi = conn.root.simulate(**sim_args)
        try:
            conn = rpyc.connect(s_host, RPYC_PORT, config={'sync_request_timeout': 70})
            tpi = conn.root.simulate(**sim_args)
        except Exception as e:
            print(s_host, e)
            tpi = False
        return cond, s_host, tpi

    def services_loop(self):
        """подбирается список необслуженных аттрибутов
        словарь атрибутов для симуляции в формате ген: условия
        пул потоков для удалённой симуляции ограничен количеством доступных участников
        map использует пул, чтобы запустить многопоточный опрос rpyc серверов
        выдаёт результат в виде словаря"""
        services = self.registry.services
        service_states = dict()

        import socket
        sock = socket.socket()
        socket_opened = False
        while not socket_opened:
            try:
                sock.bind(('', 9090))
                sock.listen(1)
                print("Waiting for client")
                conn, addr = sock.accept()
                print("Connected")
                socket_opened = True
            except OSError as e:
                print("Сокет занят. Ожидаю освобождения. ", e)
                time.sleep(10)

        results = dict()
        conds = {}
        pool = list()

        try:
            while True:
                if len(conds) == 0:
                    print("No conditions found")
                    size_of_conds = conn.recv(10)
                    if not size_of_conds:
                        time.sleep(5)
                        continue
                    print("Получена какашечка", size_of_conds)
                    sizeoc = int(size_of_conds.decode("utf-8"))
                    data = conn.recv(sizeoc)
                    if not data:
                        time.sleep(5)
                        continue
                    conn.send("working".encode("utf-8"))
                    conds = json.loads(data.decode("utf-8"))
                    print("Conditions: {} : ".format(len(conds)), conds)
                elif len(services) == 0:
                    print("No services found")
                    time.sleep(5)
                    continue
                elif self.S_SERVICE not in services:
                    print("No appropriate remote services")
                    print(services)
                    time.sleep(5)
                    continue
                else:
                    service_hosts = services[self.S_SERVICE]
                    print("Service_hosts: {} : ".format(len(service_hosts)), service_hosts)

                    # список доступных сервисов
                    services_free = list()
                    rpc_hosts = service_hosts
                    for s_socket, s_time in service_hosts.items():
                        s_host, s_port = s_socket
                        if s_host not in service_states:
                            service_states[s_host] = self.S_STATE_REGISTERED
                            services_free.append(s_host)
                        elif s_host in service_states:
                            if service_states[s_host] == self.S_STATE_REGISTERED:
                                services_free.append(s_host)
                    print(service_states)
                    if len(services_free) == 0:
                        time.sleep(1)
                        print("Нет свободных сервисов")
                        continue

                    # словарь условий, которые ещё не были обслужены,
                    # но сейчас будут
                    conditions = {}
                    for cond in conds:
                        if cond not in results and len(services_free) > 0:
                            conditions[cond] = (cond, services_free.pop(0), conds[cond])

                    # в словарь обслуживаемых условий
                    # занести ip обслуживающей станции
                    results.update({cond: False for cond in conditions})
                    # num_of_genes_to_serve = min(len(services_free), len(conditions))

                    pool = ThPool(len(conditions))
                    try:
                        sim_results = pool.map(self.rpyc_connect_to_simulate, conditions.values())
                        # TODO: надо адекватную обработку результатов
                        print("получены результаты", sim_results)
                        for gene_id, s_host, tpi in sim_results:
                            service_states[s_host] = self.S_STATE_REGISTERED
                            # if gene_id in results:
                            #     results.pop(gene_id)
                            if tpi is not False:
                                results[gene_id] = tpi
                            else:
                                results.pop(gene_id)
                    except ConnectionError as e:
                        # наверно тут надо работающие треды обрубить
                        print("Ошибка. Одна из станций не отвечает", e)
                        print("Список станций: ", services)
                        pool.close()
                        time.sleep(3)

                    # for s_host, s_state in service_states.items():
                    pool.close()
                    pool.join()

                    # results.update(sim_results)
                    time.sleep(2)

                # когда результаты накоплены, передаёт длину сообщения,
                # а следом - само сообщение
                if len(results) > 0 and len(results) >= len(conds):
                    res_str = json.dumps(results, ensure_ascii=False).encode("utf-8")
                    len_of_res_str = str(len(res_str)) + "\n"
                    while len(len_of_res_str) < 10:
                        len_of_res_str = "0" + len_of_res_str
                    conn.send(len_of_res_str.encode("utf-8"))
                    del len_of_res_str

                    conn.send(res_str)
                    conds = {}
                    results = {}
        except KeyboardInterrupt as e:
            print("Закрываю открытые соединения. ", e)
            conn.close()
            sock.close()


if __name__ == "__main__":
    reggy_srv = ReggaeSrv()
    reggy_srv.registry_async()()  # <-- Сиськи!
    reggy_srv.services_loop()
