import rpyc
from rpyc.utils.registry import TCPRegistryServer, TCPRegistryClient
from rpyc.utils.server import Server, ThreadedServer, ForkingServer
import socket
from main import simulate
from threading import Thread
from functools import wraps
import json
from multiprocessing import Pool
from multiprocessing.dummy import Pool as ThPool
import time


def fake_sim(args):
    return 1


class MyService(rpyc.Service):
    def __init__(self):
        self.exposed_simulate = fake_sim


MY_HOSTNAME = "10.22.252.100"
REGISTRY_PORT = 18811
RPYC_PORT = 12345


class ReggaeSrv:
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
        conn = rpyc.connect(s_host, RPYC_PORT)
        tpi = conn.root.simulate(**sim_args)
        return s_host, 1 / tpi

    def services_loop(self):
        """цикл или map
        получает словарь атрибутов для симуляции
        запускает многопоточный опрос rpyc серверов
        выдаёт результат в виде словаря"""
        services = self.registry.services
        import socket
        sock = socket.socket()
        sock.bind(('', 9090))
        sock.listen(1)
        conn, addr = sock.accept()
        results = dict()

        while True:
            data = conn.recv(1024)
            if not data:
                break
            conds = json.loads(data.decode("utf-8"))
            while len(results) < len(conds):
                if len(services) == 0:
                    time.sleep(1)
                print("Services ", services)

                genes = list(conds.keys())[:len(services)]
                conditions = list()
                serv_ips = list(services.values())
                for cond in genes:
                    serv_ip = serv_ips.pop(0)
                    conditions.append((serv_ip, conds[cond]))
                    results[cond] = serv_ip

                pool = ThPool(len(services))
                sim_results = pool.map(self.rpyc_connect_to_simulate, conditions)
                pool.close()
                pool.join()
                results.update(sim_results)
            conn.send(results)

        conn.close()

class ReggaeCli:
    def __init__(self, registry=TCPRegistryClient, service=MyService):
        self.registry = registry(MY_HOSTNAME)
        self.hostname = socket.gethostname()
        self.rpc = ThreadedServer(service, port=RPYC_PORT)


if __name__ == "__main__":
    srv = True
    if srv:
        reggy_srv = ReggaeSrv()
        reggy_srv.registry_async()
        reggy_srv.services_loop()
        # server = ThreadedServer(MyService, port = 12345)
        # server.start()
    else:
        reggy_cli = ReggaeCli()
        if reggy_cli.registry.register(reggy_cli.hostname, REGISTRY_PORT):
            reggy_cli.rpc.start()
