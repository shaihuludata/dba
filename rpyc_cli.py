import rpyc
from rpyc.utils.registry import TCPRegistryServer
from rpyc.utils.registry import TCPRegistryClient as tcp_cl
from rpyc.utils.server import Server, ThreadedServer, ForkingServer
import socket
from main import simulate, create_simulation
from threading import Thread, Event
from functools import wraps
import json
import time
import random
import sys
import logging
import subprocess


def sub_simulate(jargs):
    try:
        process = subprocess.Popen(["python3", "main.py", jargs], stdout=subprocess.PIPE)
        data = process.communicate(timeout=500)
        logging.info("GENE: ", data)
        stdout, stderr = data
        tpistr = str(stdout)
        tpistr = str(tpistr.split("___")[1])
        tpi = float(tpistr.split("=")[1])
    except:
        tpi = float('Inf')
    return tpi


def mpi_simulate(jargs):

    from mpi4py import MPI

    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    if rank == 0:
        print(rank, "я родился")
        jargs = jargs.encode(encoding="utf_8")
        comm.Send([jargs, len(jargs)], 1, tag=11)
        tpi = comm.recv(source=1, tag=12)
        return tpi
    elif rank == 1:
        print(rank, "я пытаюсь принимать")
        jargs = comm.recv(source=0, tag=11)[0]
        tpi = sub_simulate(jargs)
        comm.send(tpi, dest=0, tag=12)
    else:
        print(rank, "не озадачен")


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
        self.simulate_method = None

    def exposed_create_simulation(self):
        self.env, self.sim_config = create_simulation()
        return

    def simulate_async(self):
        func = self.simulate_method
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


MY_HOSTNAME = "localhost"  # ip_addr
REGISTRY_PORT = 18811
RPYC_PORT = 12345


# переопределение класса, чтобы исправить утечку портов
from rpyc.core import brine


MAX_DGRAM_SIZE          = 1500


class TCPRegistryClient(tcp_cl):
    # исправленный метод закрывает сокет
    def register(self, aliases, port, interface = ""):

        self.logger.info("registering on %s:%s", self.ip, self.port)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((interface, 0))
        sock.settimeout(self.timeout)
        data = brine.dump(("RPYC", "REGISTER", (aliases, port)))
        try:
            sock.connect((self.ip, self.port))
            sock.send(data)
        except (socket.error, socket.timeout):
            self.logger.warn("could not connect to registry")
            return False
        try:
            data = sock.recv(MAX_DGRAM_SIZE)
        except socket.timeout:
            self.logger.warn("registry did not acknowledge")
            return False
        try:
            reply = brine.load(data)
        except Exception:
            self.logger.warn("received corrupted data from registry")
            return False
        if reply == "OK":
            self.logger.info("registry %s:%s acknowledged", self.ip, self.port)
        sock.close()
        return True


class ReggaeCli:
    STATE_INITIAL = "Offline"
    STATE_REGISTERED = "Registered"
    STATE_WORKING = "Working"
    REGGAE_HOSTNAME = "localhost"  # ip_addr
    SERVICE = "REMOTESIM"

    def __init__(self, registry=TCPRegistryClient, service=MyService):
        self.state = self.STATE_INITIAL
        self.registry = registry(MY_HOSTNAME)
        self.hostname = socket.gethostname()
        self.rpc_enabled = False
        for i in [1, 10, 20]:
            try:
                self.rpc = ThreadedServer(service, port=RPYC_PORT)
                self.rpc_enabled = True
                break
            except OSError as e:
                print(e, "on {} port ... waiting {} seconds".format(RPYC_PORT, i))
                time.sleep(i)

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
        time_start = - self.registry.REREGISTER_INTERVAL
        reg_result = False

        while True:
            if self.rpc_enabled:
                time_current = time.time()
                time_delta = time_current - time_start
                if time_delta > self.registry.REREGISTER_INTERVAL:
                    logging.debug("Reregistering after {} sec".format(time_delta))
                    time_start = time_current
                    reg_result = self.registry.register(self.SERVICE, REGISTRY_PORT)
                if reg_result:
                    self.state = self.STATE_REGISTERED
                    if not rpyc_th_alive:
                        rpyc_th = self.rpyc_async()()
                    if rpyc_th is not False:
                        rpyc_th_alive = rpyc_th.is_alive()
                    time.sleep(1)
                else:
                    self.state = self.STATE_INITIAL
                    time.sleep(5)
            else:
                print("Waiting for RPC up")
                time.sleep(5)


if __name__ == "__main__":
    SIM_TYPE = "MPI"  # "MPI" or "SUBPROCESS"
    simulation_methods = {"MPI": mpi_simulate, "SUBPROCESS": sub_simulate}
    class MSV(MyService):
        def __init__(self):
            MyService.__init__(self)
            self.simulate_method = simulation_methods[SIM_TYPE]

    reggy_cli = ReggaeCli(service=MSV)
    reggy_cli.services_loop()
