from random import expovariate
import simpy
from examples_and_tries.SimComponents import PacketGenerator, PacketSink
from addict import Dict
import json
import random
import logging


class Signal:
    def __init__(self, env, name, data: dict, source, source_port, delay):
        self.env = env
        self.name = name
        self.alive = True
        self.physics = dict()
        self.physics["type"] = "electric"
        self.physics["collision"] = False
        self.physics["distance_passed"] = 0
        assert type(data) is dict
        self.data = data
        self.delay = delay
        self.source = source
        self.source_port = source_port
        self.action = env.process(self.run())

    def run(self):
        while self.alive:
            l_dev, l_port = self.source, self.source_port
            r_dev, sig, r_port = l_dev.s_start(self, l_port)
            r_dev.r_start(sig, r_port)
            yield self.env.timeout(self.delay - 1e-14)
            l_dev.s_end(self, l_port)
            r_dev.r_end(sig, r_port)
            self.alive = False


class Dba:
    def __init__(self, env, config, snd_sig):
        self.env = env
        self.global_bwmap = dict()  # {time: intra_cycle_bwmap}
        self.next_cycle_start = 0
        self.ont_discovered = dict()
        self.cycle_duration = config["cycle_duration"]
        self.snd_sig = snd_sig

        self.upstream_interframe_interval = config["upstream_interframe_interval"]

        if "maximum_allocation_start_time" in config:
            self.maximum_allocation_start_time = config["maximum_allocation_start_time"]
        elif config["transmitter_type"] == "1G":
            self.maximum_allocation_start_time = 19438
        elif config["transmitter_type"] == "2G":
            self.maximum_allocation_start_time = 38878

        self.action = env.process(self.run())

    def run(self):
        while True:
            raise NotImplemented

    def sn_request(self):
        bwmap = list()
        alloc_structure = {"Alloc-ID": "to_all",  # "Flags": 0,
                           "StartTime": 0,
                           "StopTime": self.maximum_allocation_start_time}  # , "CRC": None}
        bwmap.append(alloc_structure)
        self.global_bwmap[self.next_cycle_start] = bwmap
        self.global_bwmap[self.next_cycle_start + self.cycle_duration] = bwmap
        return bwmap

    def register_new_ont(self, s_number, allocs):
        self.ont_discovered[s_number] = allocs

    def register_packet(self, alloc, size):
        pass


class DbaStatic(Dba):
    """Пробная версия, работает только для первого потока на каждой ONT"""
    def __init__(self, env, config, snd_sig):
        Dba.__init__(self, env, config, snd_sig)

    def run(self):
        while True:
            requests = self.ont_discovered
            alloc_timer = 0  # in bytes
            bwmap = list()
            onts = len(requests)
            max_alloc_time = self.maximum_allocation_start_time  # in bytes!
            # if (self.next_cycle_start not in self.global_bwmap)\
            #         or len(self.global_bwmap[self.next_cycle_start]) == 0:
            for ont in requests:
                # Выбрать первый поток от ont
                alloc = str()
                for allocation in requests[ont]:
                    if allocation.endswith("_1"):
                        alloc = allocation
                        break
                # Выделить пропускную способность ont, обратно пропорционально количеству ont
                if alloc_timer <= max_alloc_time:
                    alloc_structure = {"Alloc-ID": alloc,  # "Flags": 0,
                                       "StartTime": alloc_timer, "StopTime": None}  # , "CRC": None}
                    # для статичного DBA выделяется интервал, обратно пропорциональный
                    # self.maximum_ont_amount - количеству ONT
                    alloc_timer += round(max_alloc_time / onts) - self.upstream_interframe_interval
                    alloc_structure["StopTime"] = alloc_timer
                    bwmap.append(alloc_structure)
                alloc_timer += self.upstream_interframe_interval
            self.global_bwmap[self.next_cycle_start] = bwmap
            # olt подтянет bwmap из snd_port_sig
            if "bwmap" not in self.snd_sig:
                self.snd_sig["bwmap"] = bwmap
            else:
                pass
            self.snd_sig["s_timestamp"] = self.env.now
            yield self.env.timeout(self.cycle_duration)


class Dev(object):
    def __init__(self, env, name, config):
        self.config = config
        self.name = name
        # self.rate = config["type"]
        self.env = env
        self.out = dict()

    def s_start(self, sig, port):
        raise NotImplemented

    def r_start(self, sig, port):
        raise NotImplemented

    def s_end(self, sig, port):
        raise NotImplemented

    def r_end(self, sig, port):
        raise NotImplemented


class ActiveDev(Dev):
    def __init__(self, env, name, config):
        Dev.__init__(self, env, name, config)
        self.STATE = "Offline"
        self.power_matrix = 0
        self.cycle_duration = 125
        self.next_cycle_start = 0
        # словарь порт: принимаемый сигнал. используется для обнаружения коллизий
        self.rec_port_sig = dict()
        self.snd_port_sig = dict()
        for port in config["ports"]:
            self.rec_port_sig[int(port)] = list()
        for port in config["ports"]:
            self.snd_port_sig[int(port)] = dict()
        # self.counters = Counters()
        self.action = env.process(self.run())

        if "transmitter_type" in self.config:
            trans_type = self.config["transmitter_type"]
            if trans_type == "1G":
                self.transmitter_speed = 1244160000
                # self.transmitter_speed = 1000000000
                self.maximum_allocation_start_time = 19438
            elif trans_type == "2G":
                self.transmitter_speed = 2488320000
                self.maximum_allocation_start_time = 38878
            else:
                raise Exception("Transmitter type {} not specified".format(trans_type))
        else:
            raise Exception("Specify transmitter type!")

    def run(self):
        raise NotImplemented

    def s_start(self, sig, l_port):
        logging.debug("{} : {} : send {}".format(round(self.env.now, 2), self.name, sig.name))
        sig = self.eo_transform(sig)
        r_port, r_dev = self.out[l_port]
        return r_dev, sig, r_port

    def s_end(self, sig, port: int):
        return self.name, port, sig

    def r_start(self, sig, port):
        logging.debug("{} : {} : recv {}".format(round(self.env.now, 2), self.name, sig.name))
        self.rec_port_sig[port].append(sig)
        rec_sigs = self.rec_port_sig[port]
        num_of_sigs = len(rec_sigs)
        if num_of_sigs > 1:
            print("{} : {} : ИНТЕРФЕРЕНЦИОННАЯ КОЛЛИЗИЯ. Сигналов: {}!!!"
                  .format(self.env.now, self.name, num_of_sigs))
            sn = False
            for i in rec_sigs:
                if "sn_response" in i.data:
                    sn = True
            if not sn:
                print("плохая коллизия")
                #print(list((sig.name, sig.data["cycle_num"]) for sig in rec_sigs))
                print(list(sig.name for sig in rec_sigs))
                # raise Exception("плохая коллизия")

            for i in rec_sigs:
                i.physics["collision"] = True
        return 0

    def r_end(self, sig, port: int):
        rec_sig = self.rec_port_sig[port]
        rec_sig.remove(sig)
        self.oe_transform(sig)

    def eo_transform(self, sig):
        optic_parameters = {"power": float(self.config["transmitter_power"]),
                            "wavelength": float(self.config["transmitter_wavelength"])}
        assert sig.physics["type"] == "electric"
        sig.physics["type"] = "optic"
        sig.physics.update(optic_parameters)
        return sig

    def oe_transform(self, sig):
        optic_parameters = {}
        assert sig.physics["type"] == "optic"
        sig.physics["type"] = "electric"
        sig.physics.update(optic_parameters)
        return sig


class Ont(ActiveDev):
    def __init__(self, env, name, config):
        ActiveDev.__init__(self, env, name, config)
        if "activation_time" in self.config:
            self.time_activation = self.config["activation_time"] * 1000
        else:
            self.time_activation = 0

        self.STATE = "Offline"
        self.range_time_delta = list()
        # self.traffic_generators = dict()
        self.current_allocations = dict()  # key alloc_id : value grant_size

        if "Alloc" in config:
            for alloc_id in config["Alloc"]:
                alloc_type = config["Alloc"][alloc_id]
                # tg = Traffic(self.name, alloc_id, alloc_type)
                # self.traffic_generators[self.name + "_" + alloc_id] = tg
                # self.current_allocations[tg.id] = tg.traf_class
                alloc_name = self.name + "_" + alloc_id
                self.current_allocations[alloc_name] = None
        if "0" not in config["Alloc"]:
            alloc_type = "type0"

    def run(self):
        while True:
            if self.STATE is "Offline":
                yield self.env.timeout(self.time_activation)
                self.STATE = "Initial"
            elif self.STATE == "Initial":
                yield self.env.timeout(self.cycle_duration)
            elif self.STATE == "Standby":
                l_port = 0
                planned = self.snd_port_sig[l_port]
                if "s_time" in planned and "args" in planned:
                    planned_s_time = planned["s_time"]
                    args = planned["args"]
                    yield self.env.timeout(planned_s_time)
                    Signal(*args)
                    self.snd_port_sig[l_port] = {}
                else:
                    yield self.env.timeout(self.cycle_duration)
            else:
                yield self.env.timeout(self.cycle_duration)

    def r_end(self, sig, port: int):
        # обработка на случай коллизии
        assert sig in self.rec_port_sig[port]
        self.rec_port_sig[port].remove(sig)
        # if rec_sig.physics["collision"]:
        #     self.counters.ingress_collision += 1
        #     return {}

        sig = self.oe_transform(sig)
        logging.debug("{} : {} : принят {}".format(self.env.now, self.name, sig.name))
        if self.STATE == "Initial":
            self.STATE = "Standby"
        if self.STATE == "Standby":
            if "sn_request" in sig.data:
                # из принятого от OLT сигнала распознаём sn_request и планируем ответ на момент planned_s_time
                # delay = random.randrange(34, 36, 1) + random.randrange(0, 50, 1)
                delay = random.randrange(0, 80, 1) + self.cycle_duration
                planned_s_time = round(self.env.now + delay, 2)
                planned_e_time = planned_s_time + 2
                sig_id = "{}:{}:{}".format(planned_s_time, self.name, planned_e_time)
                alloc_ids = self.current_allocations
                data = {"sn_response": (self.name, alloc_ids)}
                self.snd_port_sig[port] = {"s_time": planned_s_time, "args": [self.env, sig_id, data, self, port, 2]}
            if "sn_ack" in sig.data:
                for alloc in sig.data["sn_ack"]:
                    if alloc in self.current_allocations:
                        self.current_allocations[alloc] = "sn_ack"
                allocs_acked = list(i for i in self.current_allocations.keys()
                                    if self.current_allocations[i] == "sn_ack")
                if len(allocs_acked) > 0:
                    print("{} Авторизация на OLT подтверждена, allocs: {}".format(self.name, allocs_acked))
                # Формально тут должно быть "SerialNumber"
                # но без потери смысла для симуляции должно быть Ranging
                    self.STATE = "Ranging"
                # print(sig)
                # output = {"sig": sig, "delay": delay}
        elif self.STATE == "Ranging":
            if "s_timestamp" in sig.data:
                s_timestamp = sig.data["s_timestamp"]
                if len(self.range_time_delta) > 10:
                    self.range_time_delta.pop(0)
                self.range_time_delta.append(self.env.now - s_timestamp - self.cycle_duration)
            self.STATE = "Operation"
        elif self.STATE == "Operation":
            # "Alloc-ID"
            avg_half_rtt = sum(self.range_time_delta)/len(self.range_time_delta)
            bwmap = sig.data["bwmap"]
            for allocation in bwmap:
                name = self.name
                alloc_id = allocation["Alloc-ID"]
                for dev_alloc in self.current_allocations:
                    if dev_alloc == alloc_id:
                        data_to_send = dict()
                        allocation_start = allocation["StartTime"]
                        allocation_stop = allocation["StopTime"]
                        grant_size = allocation_stop - allocation_start
                        intra_cycle_s_start = round(8*1000000*allocation_start / self.transmitter_speed, 2)
                        intra_cycle_e_start = round(8*1000000*allocation_stop / self.transmitter_speed, 2)
                        planned_s_time = self.next_cycle_start + intra_cycle_s_start - 2*avg_half_rtt + self.cycle_duration
                        planned_e_time = self.next_cycle_start + intra_cycle_e_start - 2*avg_half_rtt + self.cycle_duration
                        # полезно для отладки
                        planned_delta = planned_e_time - planned_s_time
                        if planned_delta <= 0:
                            break
                        assert planned_s_time >= self.env.now

                        # for tg_name in self.traffic_generators:
                        #     tg = self.traffic_generators[tg_name]
                        #     if tg.id == alloc_id:
                        #         if len(tg.queue) == 0:
                        #             break
                        #         else:  # len(tg.queue) > 0:
                        #             packets_to_send = list()
                        #             for message in tg.queue:
                        #                 if grant_size == 0:
                        #                     break
                        #                 send_time = time + message["interval"]
                        #                 traf_class = message["traf_class"]
                        #                 send_size = message["size"]
                        #                 packet = dict()
                        #                 packet.update(message)
                        #                 if grant_size >= send_size:
                        #                     # packets_to_send.append(packet)
                        #                     message["size"] = 0
                        #                 else:
                        #                     packet["size"] = grant_size
                        #                     message["size"] -= grant_size
                        #                     message["fragment_offset"] += grant_size
                        #                 packets_to_send.append(packet)
                        #                 grant_size -= packet["size"]
                        #                 # print("planned_s_time {}, packet_id {}, size {}"
                        #                 #       .format(planned_s_time, packet["packet_id"], packet["size"]))
                        #                 packet_alloc = packet["alloc_id"]
                        #             for packet in packets_to_send:
                        #                 for packet_q in tg.queue:
                        #                     packet_id = packet["packet_id"]
                        #                     if packet_id == packet_q["packet_id"]:
                        #                         if packet_q["size"] == 0:
                        #                             self.traffic_generators[alloc_id].queue.remove(packet_q)
                        #                             break
                        #                 if alloc_id not in data_to_send:
                        #                     data_to_send[alloc_id] = list()
                        #                 data_to_send[alloc_id].append(packet)
                        #         break
                        # data_to_send.update({"cycle_num": sig.data["cycle_num"]})
                        # data_to_send.update({"allocation": allocation})

                        # self.snd_port_sig[port] = {"s_time": planned_s_time,
                        #                            "args": [self.env, sig_id, data, self, port, 2]}
                        sig_id = "{}:{}:{}".format(planned_s_time, self.name, planned_e_time)
                        if sig_id not in self.sending_sig.values():
                            self.sending_sig[planned_s_time] = sig_id
                            req_sig = Signal(sig_id, data_to_send, source=self.name)
                            if planned_s_time not in self.planned_events:
                                self.planned_events[planned_s_time] = list()
                            if planned_e_time not in self.planned_events:
                                self.planned_events[planned_e_time] = list()
                            self.planned_events[planned_s_time].append({"dev": self, "state": "s_start", "sig": req_sig, "port": 0})
                            self.planned_events[planned_e_time].append({"dev": self, "state": "s_end", "sig": req_sig, "port": 0})
                        break
        else:
            raise Exception("State {} not implemented".format(self.STATE))
        # if self.STATE != "Offline":
        #     self.counters.ingress_unicast += 1
        return {}


class Olt(ActiveDev):
    def __init__(self, env, name, config):
        ActiveDev.__init__(self, env, name, config)
        self.sn_request_interval = config["sn_request_interval"]
        self.sn_quiet_interval = config["sn_quiet_interval"]
        self.sn_request_next = 0
        self.sn_request_quiet_interval_end = 0
        self.maximum_ont_amount = int(self.config["maximum_ont_amount"])
        # self.counters.number_of_ont = int()
        # self.defragmentation_buffer = dict()
        dba_config = dict()
        # self.upstream_interframe_interval = self.config["upstream_interframe_interval"]  # 10 # in bytes
        for dba_par in ["cycle_duration", "transmitter_type",
                        "maximum_allocation_start_time", "upstream_interframe_interval"]:
            if dba_par in config:
                dba_config[dba_par] = config[dba_par]

        if config["dba_type"] == "static":
            self.dba = DbaStatic(env, dba_config, self.snd_port_sig[0])

    def run(self):
        while True:
            if self.STATE == "Offline":
                self.STATE = "Initial"
                yield self.env.timeout(10)
            elif self.STATE == "Initial":
                self.STATE = "Normal"
                yield self.env.timeout(10)

            if self.env.now > self.sn_request_next:
                self.sn_request_next += self.sn_request_interval
                self.STATE = "SN_request"
                self.sn_request_quiet_interval_end = self.env.now + self.sn_quiet_interval + \
                                                     236 + 2 * self.cycle_duration
            if self.STATE == "SN_request":
                l_port = 0
                bwmap = self.dba.sn_request()
                data = {"bwmap": bwmap, "sn_request": True, "s_timestamp": self.dba.next_cycle_start}
                data.update(self.snd_port_sig[l_port])
                self.snd_port_sig[l_port].clear()
                start = round(self.env.now, 2)
                delay = self.cycle_duration
                end = start + delay
                sig_id = "{}:{}:{}".format(start, self.name, end)
                Signal(self.env, sig_id, data, self, l_port, delay)
                yield self.env.timeout(self.cycle_duration + 1e-12)
                self.STATE = "Normal"
            elif self.STATE == "Normal":
                l_port = 0
                data.update(self.snd_port_sig[l_port])
                self.snd_port_sig[l_port].clear()
                start = round(self.env.now, 2)
                delay = self.cycle_duration
                end = start + delay
                sig_id = "{}:{}:{}".format(start, self.name, end)
                Signal(self.env, sig_id, data, self, l_port, delay)
                yield self.env.timeout(self.cycle_duration + 1e-12)

    def r_end(self, sig, port: int):
        ret = dict()
        # обработка интерференционной коллизии
        # каждый принимаемый сигнал должен быть помечен как коллизирующий
        for r_sig in self.rec_port_sig[port]:
            if r_sig.name == sig.name:
                self.rec_port_sig[port].remove(r_sig)
                # if rec_sig.physics["collision"]:
                #     self.counters.ingress_collision += 1
                #     return {}
                break

        self.oe_transform(sig)
        if "sn_response" in sig.data and self.env.now <= self.sn_request_quiet_interval_end:
            # проверка на содержание ответов на запросы регистрации в сообщении
            s_number = sig.data["sn_response"][0]
            allocs = sig.data["sn_response"][1]
            self.dba.register_new_ont(s_number, allocs)
            # self.counters.number_of_ont = len(self.dba.ont_discovered)
            if "sn_ack" not in self.snd_port_sig[port]:
                self.snd_port_sig[port]["sn_ack"] = list()
            self.snd_port_sig[port]["sn_ack"].extend(allocs)
        else:
            # нормальный приём сообщения
            ont_allocs = list(alloc for alloc in sig.data if "ONT" in alloc)
            for alloc in ont_allocs:
                for packet in sig.data[alloc]:
                    pass
                    # ret_upd = self.defragmentation(packet)
                    # for t in ret_upd:
                    #     evs = ret_upd[t]
                    #     if t not in ret:
                    #         ret[t] = list()
                    #     ret[t].extend(evs)
                # self.dba.register_packet(alloc, sig.data[alloc])
            return ret


class Splitter(Dev):
    def __init__(self, env, name, config):
        Dev.__init__(self, env, name, config)
        self.delay = 0
        self.length = 0.000001
        typ = self.config["type"]
        if typ == "1:2":
            self.power_matrix = [[0, 0.25, 0.25],
                                 [0.25, 0, 0],
                                 [0.25, 0, 0]]
        elif typ == "1:4":
            self.power_matrix = [[0, 0.25, 0.25, 0.25, 0.25],
                                 [0.25, 0, 0, 0, 0],
                                 [0.25, 0, 0, 0, 0],
                                 [0.25, 0, 0, 0, 0],
                                 [0.25, 0, 0, 0, 0]]
        else:
            raise Exception("Unknown splitter type {}".format(typ))

    def multiply_power(self, sig, ratio, l_port):
        new_power = sig.physics["power"] * ratio
        if new_power > 0:
            data_to_send = sig.data
            sig_id = sig.name
            delay = sig.delay
            new_sig = Signal(self.env, sig_id, data_to_send, self, l_port, delay)
            new_sig.physics["type"] = "optic"
            new_sig.physics["power"] = new_power
            new_sig.physics["distance_passed"] += self.length
            return new_sig
        return False

    def s_start(self, sig, l_port):
        r_port, r_dev = self.out[l_port]
        return r_dev, sig, r_port

    def s_end(self, sig, port):
        return

    def r_start(self, sig, port):
        matrix_ratios = self.power_matrix[port]
        for l_port in range(len(matrix_ratios)):
            ratio = matrix_ratios[l_port]
            splitted_sig = self.multiply_power(sig, ratio, l_port)
            if splitted_sig is not False:
                splitted_sig.name += ":{}:{}".format(self.name, l_port)
        return self.delay

    def r_end(self, sig, port):
        return


def NetFabric(net, env):
    classes = {"OLT": Olt, "ONT": Ont, "Splitter": Splitter}
    devices = dict()
    connection = dict()
    # Create devices
    for dev_name in net:
        config = net[dev_name]
        for dev_type in classes:
            if dev_type in dev_name:
                constructor = classes[dev_type]
                dev = constructor(env, dev_name, config)
                devices[dev_name] = dev
                connection[dev_name] = config["ports"]
    # Interconnect devices
    for dev_name in connection:
        l_dev = devices[dev_name]
        con = connection[dev_name]
        for l_port in con:
            r_dev_name, r_port = con[l_port].split("::")
            r_dev = devices[r_dev_name]
            l_port = int(l_port)
            l_dev.out[l_port] = (int(r_port), r_dev)


def main():
    config = Dict({"horizont": 1500})
    net = json.load(open("network2.json"))

    env = simpy.Environment()
    NetFabric(net, env)
    env.run(until=config.horizont)

    print("{} End of simulation... Preparing results.".format(env.now))
    # make_results()


if __name__ == "__main__":
    main()
