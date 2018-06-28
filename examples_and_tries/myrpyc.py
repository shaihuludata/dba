import rpyc
from rpyc.utils.registry import TCPRegistryServer, TCPRegistryClient
from rpyc.utils.server import Server, ThreadedServer, ForkingServer
import socket
from main import simulate
from threading import Thread
from functools import wraps


class MyService(rpyc.Service):
    def __init__(self):
        self.exposed_simulate = simulate


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

    def services_loop(self, conditions):
        """цикл или map
        получает словарь атрибутов для симуляции
        запускает многопоточный опрос rpyc серверов
        выдаёт результат в виде словаря"""
        services = self.registry.services
        # ну какое-то такое
        # results = map(services, conditions)
        # for s, s_host in services.items():
        #     conn = rpyc.connect(s_host, RPYC_PORT)


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
        # server = ThreadedServer(MyService, port = 12345)
        # server.start()
    else:
        reggy_cli = ReggaeCli()
        if reggy_cli.registry.register(reggy_cli.hostname, REGISTRY_PORT):
            reggy_cli.rpc.start()
