import rpyc
from rpyc.utils.registry import TCPRegistryServer, TCPRegistryClient
from rpyc.utils.server import Server, ThreadedServer, ForkingServer
import socket
from main import simulate, create_simulation
from threading import Thread, Event
from functools import wraps
import json
import time
import random
import logging
import subprocess


def sub_simulate(jargs):
    try:
        process = subprocess.Popen(["python3", "main.py", jargs], stdout=subprocess.PIPE)
        data = process.communicate(timeout=60)
        logging.info("GENE: ", data)
        stdout, stderr = data
        tpistr = str(stdout)
        tpistr = str(tpistr.split("___")[1])
        tpi = float(tpistr.split("=")[1])
    except:
        tpi = float('Inf')  # 100500
    return tpi


class Job(Thread):
    def __init__(self, group=None, target=None, name=None, args=None, kwargs=None):
        Thread.__init__(self, group, target, name, args, kwargs)
        self._return = None

    def run(self):
        if self._target is not None:
            self._return = self._target(*self._args, **self._kwargs)

    def join(self, timeout=1):
        Thread.join(self, timeout)
        return self._return


class MyService(rpyc.Service):
    def __init__(self):
        self.env = None
        self.sim_config = None
        self.result_thread = None

    def exposed_create_simulation(self):
        self.env, self.sim_config = create_simulation()
        return

    def simulate_async(self):
        func = sub_simulate
        @wraps(func)
        def async_func(*args, **kwargs):
            func_hl = Job(target=func, name="Simulation_thread", args=args, kwargs=kwargs)
            func_hl.start()
            return func_hl
        return async_func

    def exposed_simulate(self, jargs):
        self.result_thread = self.simulate_async()(jargs)
        return "OK"

    def exposed_get_result(self):
        res = self.result_thread.join(timeout=1)
        return res

    def exposed_abort_simulation(self):
        self.env.end_flag = True
        self.result_thread._tstate_lock.release()
        self.result_thread._stop()
        # self.result_thread._delete()
        # del self.env
        del self.result_thread
        return "Aborted"

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
        func = self.rpc.start
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
            if self.registry.register(self.SERVICE, REGISTRY_PORT):
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
