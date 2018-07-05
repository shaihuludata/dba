import rpyc
from rpyc.utils.registry import TCPRegistryServer, TCPRegistryClient
from rpyc.utils.server import Server, ThreadedServer, ForkingServer
import socket
from main import simulate
from threading import Thread
from functools import wraps
import json
import time
import random


class MyService(rpyc.Service):
    def __init__(self):
        #self.exposed_simulate = fake_sim
        pass

    @staticmethod
    def exposed_simulate(jargs):
        print(jargs)
        return simulate(jargs)

    # @staticmethod
    # def exposed_simulate(jargs):
    #     print("Получил условия: {}".format(jargs))
    #     print("Типа симулирую")
    #     time.sleep(5)
    #     print("Типа досимулировал")
    #     return random.random()

MY_HOSTNAME = "10.22.252.100"
REGISTRY_PORT = 18811
RPYC_PORT = 12345


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

    def rpyc_async(self):
        func = reggy_cli.rpc.start
        @wraps(func)
        def async_func(*args, **kwargs):
            func_hl = Thread(target=func, args=args, kwargs=kwargs)
            func_hl.start()
            return func_hl
        return async_func

    def services_loop(self):
        """Если регистрация удачна,
        то запускает тред с rpyc
        иначе ждёт 5 секунд до следующей попытки"""
        rpyc_th_alive = False
        while True:
            if reggy_cli.registry.register(self.SERVICE, REGISTRY_PORT):
                self.state = self.STATE_REGISTERED
                if not rpyc_th_alive:
                    rpyc_th = self.rpyc_async()()
                if rpyc_th is not False:
                    rpyc_th_alive = rpyc_th.is_alive()
                time.sleep(1)
            else:
                self.state = self.STATE_INITIAL
                time.sleep(5)


if __name__ == "__main__":
    reggy_cli = ReggaeCli()
    reggy_cli.services_loop()
