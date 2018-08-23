import rpyc
from rpyc.utils.registry import TCPRegistryServer as tcp_rs
from rpyc.utils.registry import TCPRegistryClient
from rpyc.utils.server import Server, ThreadedServer, ForkingServer
import socket
# from main import simulate
from threading import Thread
from functools import wraps
import json
from multiprocessing import Pool
from multiprocessing.dummy import Pool as ThPool
import time
import logging


MY_HOSTNAME = "localhost"  # ip_addr
REGISTRY_PORT = 18811
RPYC_PORT = 12345
GENE_SRV_PORT = 9092
TERMINAL_TIMEOUT = 500


class TCPRegistryServer(tcp_rs):
    # этот метод надо исправить
    def cmd_register(self, host, names, port):
        """implementation of the ``register`` command"""
        self.logger.debug("registering %s:%s as %s", host, port, ", ".join(names))
        if isinstance(names, str):
            self._add_service(names.upper(), (host, port))
        else:
            for name in names:
                self._add_service(name.upper(), (host, port))
        return "OK"


class ReggaeSrv:
    S_STATE_INITIAL = "Offline"
    S_STATE_REGISTERED = "Registered"
    S_STATE_WORKING = "Working"
    S_SERVICE = "REMOTESIM"

    def __init__(self, registry=TCPRegistryServer):
        for i in [1, 10, 20]:
            try:
                self.registry = registry()
                break
            except OSError as e:
                print(e, " ... waiting {} seconds".format(i))
                time.sleep(i)
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
        try:
            conn = rpyc.connect(s_host, RPYC_PORT,
                                config={'sync_request_timeout': TERMINAL_TIMEOUT})
        except ConnectionRefusedError:
            logging.critical("{} не отвечает".format(s_host))
            tpi = False
            return cond, s_host, tpi
        jargs = json.dumps(sim_args)
        # conn.root.create_simulation()
        start_time = time.time()
        try:
            reply = conn.root.simulate(jargs)
            if reply == "OK":
                print("SRV: {} replied {}: simulation started".format(s_host, reply))
                time.sleep(1)
            else:
                raise NotImplemented
        except Exception as e:
            print("SRV: ", s_host, "Error ", e)
            tpi = False
            return cond, s_host, tpi
        while time.time() - start_time < TERMINAL_TIMEOUT:
            try:
                result = conn.root.get_result()
            except EOFError as e:
                print(e, " Случилась вот такая беда")
                result = False
            if result is not None:
                tpi = result
                return cond, s_host, tpi
            time.sleep(1)

        reply = conn.root.abort_simulation()
        print("SRV: ", s_host, "таймаут", reply)
        tpi = float("inf")

        # try:
        #     tpi = conn.root.simulate(jargs)
        # except TimeoutError:
        #     reply = conn.root.abort_simulation()
        #     print(s_host, "таймаут ", reply)
        #     tpi = 100500
        # try:
        #      conn = rpyc.connect(s_host, RPYC_PORT,
        #                          config={'sync_request_timeout': TERMINAL_TIMEOUT})
        #     jargs = json.dumps(sim_args)
        #     tpi = conn.root.simulate(jargs)
        # except Exception as e:
        #     print(s_host, e)
        #     tpi = False
        return cond, s_host, tpi

    def services_loop(self):
        """подбирается список необслуженных аттрибутов
        словарь атрибутов для симуляции в формате ген: условия
        пул потоков для удалённой симуляции ограничен количеством доступных участников
        map использует пул, чтобы запустить многопоточный опрос rpyc серверов
        выдаёт результат в виде словаря"""
        service_states = dict()

        import socket
        sock = socket.socket()
        socket_opened = False

        while not socket_opened:
            try:
                sock.bind(('', GENE_SRV_PORT))
                socket_opened = True
            except OSError:
                logging.warning("SRV: Сокет порта {} занят. Ожидаю освобождения. "
                                .format(GENE_SRV_PORT))
                time.sleep(10)

        sock.listen(1)
        try:
            while True:
                logging.info("SRV: Waiting for client")
                conn, addr = sock.accept()
                logging.warning("SRV: Conditions source connected")

                results = dict()
                conds = {}
                pool = list()

                while len(results) == 0 or len(results) < len(conds):
                    services = self.registry.services
                    if len(conds) == 0:
                        logging.warning("SRV: No new conditions found")
                        size_of_conds = conn.recv(10)
                        if not size_of_conds:
                            time.sleep(5)
                            continue
                        logging.debug("SRV: got size of new conditions", size_of_conds)
                        sizeoc = int(size_of_conds.decode("utf-8"))
                        data = conn.recv(sizeoc)
                        if not data:
                            time.sleep(5)
                            continue
                        conn.send("working".encode("utf-8"))
                        conds = json.loads(data.decode("utf-8"))
                        logging.info("SRV: {} New conditions arrived: ".format(len(conds)), conds)
                    elif len(services) == 0:
                        logging.warning("SRV: No services found")
                        time.sleep(5)
                        continue
                    elif self.S_SERVICE not in services:
                        logging.error("No appropriate remote services")
                        logging.error(services)
                        time.sleep(5)
                        continue
                    else:
                        service_hosts = services[self.S_SERVICE]
                        logging.info("SRV: {} service_hosts available: ".format(len(service_hosts)), service_hosts)

                        # список доступных сервисов
                        services_free = list()
                        for s_socket, s_time in service_hosts.items():
                            s_host, s_port = s_socket
                            if s_host not in service_states:
                                service_states[s_host] = self.S_STATE_REGISTERED
                                services_free.append(s_host)
                            elif s_host in service_states:
                                if service_states[s_host] == self.S_STATE_REGISTERED:
                                    services_free.append(s_host)
                        # print(service_states)
                        if len(services_free) == 0:
                            time.sleep(1)
                            logging.warning("SRV: Нет свободных сервисов")
                            self.registry.services = {}
                            service_states = {}
                            continue

                        # словарь условий, которые ещё не были обслужены,
                        # но сейчас будут
                        conditions = {}
                        for cond in conds:
                            if cond not in results and len(services_free) > 0:
                                conditions[cond] = (cond, services_free.pop(0), conds[cond])

                        results.update({cond: False for cond in conditions})
                        # num_of_genes_to_serve = min(len(services_free), len(conditions))

                        pool = ThPool(len(conditions))
                        try:
                            sim_results = pool.map(self.rpyc_connect_to_simulate, conditions.values())
                            # TODO: задокументировать обработку результатов
                            logging.warning("SRV: Получен результат {}".format(sim_results))
                            for gene_id, s_host, tpi in sim_results:
                                # if gene_id in results:
                                #     results.pop(gene_id)
                                if tpi is not False:
                                    service_states[s_host] = self.S_STATE_REGISTERED
                                    results[gene_id] = tpi
                                else:
                                    service_states.pop(s_host)
                                    service_states[s_host] = self.S_STATE_INITIAL
                                    results.pop(gene_id)
                        except ConnectionError as e:
                            # TODO наверно тут надо работающие треды обрубить
                            logging.error("SRV: Ошибка. Одна из станций не отвечает", e)
                            logging.info("SRV: Список станций: ", services)
                            pool.close()
                            time.sleep(3)

                        # for s_host, s_state in service_states.items():
                        pool.close()
                        pool.join()
                self.registry.cmd_query("localhost", self.S_SERVICE)

                # когда результаты накоплены, передаёт длину сообщения,
                # а следом - само сообщение
                res_str = json.dumps(results, ensure_ascii=False).encode("utf-8")
                len_of_res_str = str(len(res_str)) + "\n"
                while len(len_of_res_str) < 10:
                    len_of_res_str = "0" + len_of_res_str
                conn.send(len_of_res_str.encode("utf-8"))
                del len_of_res_str

                conn.send(res_str)

                conn.close()
                conds = {}
                results = {}
        except KeyboardInterrupt as e:
            logging.error("SRV: Закрываю открытые соединения. ", e)
            sock.close()


if __name__ == "__main__":
    reggy_srv = ReggaeSrv()
    reggy_srv.registry_async()()  # <-- Сиськи!
    reggy_srv.services_loop()
