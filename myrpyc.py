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
        s_host, sim_args = args
        conn = rpyc.connect(s_host, RPYC_PORT, config={'sync_request_timeout': 70})
        tpi = conn.root.simulate(**sim_args)
        # try:
        #     conn = rpyc.connect(s_host, RPYC_PORT)
        #     tpi = conn.root.simulate(**sim_args)
        # except Exception as e:
        #     print(s_host, e)
        #     tpi = False
        return s_host, tpi

    def services_loop(self):
        """цикл или map
        получает словарь атрибутов для симуляции
        запускает многопоточный опрос rpyc серверов
        выдаёт результат в виде словаря"""
        services = self.registry.services
        service_states = dict()

        import socket
        sock = socket.socket()
        sock.bind(('', 9090))
        sock.listen(1)
        print("Waiting for client")
        conn, addr = sock.accept()
        print("Connected")
        results = dict()
        conds = {}
        pool = list()

        while True:
            if len(conds) == 0:
                print("No conditions found")
                size_of_conds = conn.recv(10)
                sizeoc = int(size_of_conds.decode())
                data = conn.recv(sizeoc)
                if not data:
                    time.sleep(5)
                    continue
                conn.send("working".encode("utf-8"))
                conds = json.loads(data.decode("utf-8"))
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
                print("service_hosts: {} : ".format(len(service_hosts)), service_hosts)
                print("Conditions: {} : ".format(len(conds)), conds)

                # список доступных сервисов
                services_free = list()
                rpc_hosts = service_hosts
                for s_socket, s_time in service_hosts.items():
                    s_host, s_port = s_socket
                    if s_host not in service_states:
                        service_states[s_host] = self.S_STATE_REGISTERED
                        services_free.append(s_host)
                print(service_states)
                if services_free == 0:
                    continue

                # словарь условий, которые ещё не были обслужены,
                # но сейчас будут
                conditions = {}
                for cond in conds:
                    if cond not in results and len(services_free) > 0:
                        conditions[cond] = (services_free.pop(0), conds[cond])

                # в словарь обслуживаемых условий
                # занести ip обслуживающей станции
                results.update({cond: wtf[0] for cond, wtf in conditions.items()})
                #num_of_genes_to_serve = min(len(services_free), len(conditions))

                pool = ThPool(len(conditions))
                sim_results = pool.map(self.rpyc_connect_to_simulate, conditions.values())

                # for s_host, s_state in service_states.items():
                pool.close()
                pool.join()
                for res in sim_results:
                    print("получен результат", res)
                    if not res[1]:
                        for gene_id, host_addr in results.items():
                            if host_addr == res[0]:
                                results.pop(gene_id)
                                break

                results.update(sim_results)
                time.sleep(10)

            if len(results) > 0 and len(results) >= len(conds):
                conn.send(results)
                conds = {}
                results = {}
        conn.close()

class ReggaeCli:
    STATE_INITIAL = "Offline"
    STATE_REGISTERED = "Registered"
    STATE_WORKING = "Working"
    REGGAE_HOSTNAME = "10.22.252.100"
    SERVICE = "REMOTESIM"
    def __init__(self, registry=TCPRegistryClient, service=MyService):
        self.state = self.STATE_INITIAL
        self.registry = registry(MY_HOSTNAME)
        self.hostname = socket.gethostname()
        self.rpc = ThreadedServer(service, port=RPYC_PORT)

    def services_loop(self):
        while True:
            if reggy_cli.registry.register(self.SERVICE, REGISTRY_PORT):
                self.state = self.STATE_REGISTERED
                reggy_cli.rpc.start()
            else:
                self.state = self.STATE_INITIAL
                time.sleep(5)
            print("State {}".format(self.state))


if __name__ == "__main__":
    srv = True if socket.gethostname() == "sw-work" else False
    if srv:
        reggy_srv = ReggaeSrv()
        reggy_srv.registry_async()()  # <-- Сиськи!
        reggy_srv.services_loop()
        # try:
        #     reggy_srv.services_loop()
        # except Exception as e:
        #     print(e)
        #     time.sleep(10)
    else:
        reggy_cli = ReggaeCli()
        try:
            reggy_cli.services_loop()
        except Exception as e:
            print(e)
            time.sleep(10)
