import simpy
from addict import Dict
import json
import random
import logging
import re
import time
import copy
import random
from sympy import EmptySet, Interval
import numpy as np
import matplotlib.pyplot as plt
from threading import Thread, Event


class Packet(object):
    """ A very simple class that represents a packet.
        This packet will run through a queue at a switch output port.
        We use a float to represent the size of the packet in bytes so that
        we can compare to ideal M/M/1 queues.

        Parameters
        ----------
        time : float
            the time the packet arrives at the output queue.
        size : float
            the size of the packet in bytes
        id : int
            an identifier for the packet
        src, dst : int
            identifiers for source and destination
        flow_id : int
            small integer that can be used to identify a flow
    """
    def __init__(self, time, size, id, src="a", dst="z", flow_id=0, cos_class=0, packet_num=0):
        # "interval": self.send_interval,
        self.time = time
        self.size = size
        self.t_size = size
        self.f_offset = 0
        self.num = packet_num
        self.id = id
        self.src = src
        self.dst = dst
        self.cos = cos_class
        self.flow_id = flow_id

    def __repr__(self):
        return "id: {}, src: {}, time: {}, size: {}, t_size {}, f_offset: {},".\
            format(self.id, self.src, self.time, self.size, self.t_size, self.f_offset)

    def make_args_for_defragment(self):
        args = [self.time, self.t_size, self.id, self.src, self.dst, self.flow_id, self.cos, self.num]
        return args


class PacketGenerator(object):
    """ Generates packets with given inter-arrival time distribution.
        Set the "out" member variable to the entity to receive the packet.
        Parameters
        ----------
        env : simpy.Environment
            the simulation environment
        adist : function
            a no parameter function that returns the successive inter-arrival times of the packets
        sdist : function
            a no parameter function that returns the successive sizes of the packets
        initial_delay : number
            Starts generation after an initial delay. Default = 0
        finish : number
            Stops generation at the finish time. Default is infinite
    """
    def __init__(self, env, id,  adist, sdist, initial_delay=0, finish=float("inf"), flow_id=0):
        # self.traf_class = config["class"]
        # self.service = config["service"]
        # self.packet_counter = 0
        # self.max_queue_size = config["max_queue_size"]  # in number_of_packets
        self.id = id
        self.env = env
        self.adist = adist
        self.sdist = sdist
        self.initial_delay = initial_delay
        self.finish = finish
        self.out = None
        self.packets_sent = 0
        self.action = env.process(self.run())
        self.flow_id = flow_id

    def run(self):
        yield self.env.timeout(self.initial_delay)
        while self.env.now < self.finish:
            # wait for next transmission
            send_interval = self.adist()
            yield self.env.timeout(send_interval)
            self.packets_sent += 1
            p = Packet(self.env.now, round(self.sdist()), self.packets_sent, src=self.id, flow_id=self.flow_id)
            self.out.put(p)


class PacketSink(object):
    """ Receives packets and collects delay information into the
        waits list. You can then use this list to look at delay statistics.

        Parameters
        ----------
        env : simpy.Environment
            the simulation environment
        debug : boolean
            if true then the contents of each packet will be printed as it is received.
        rec_arrivals : boolean
            if true then arrivals will be recorded
        absolute_arrivals : boolean
            if true absolute arrival times will be recorded, otherwise the time between consecutive arrivals
            is recorded.
        rec_waits : boolean
            if true waiting time experienced by each packet is recorded
        selector: a function that takes a packet and returns a boolean
            used for selective statistics. Default none.
    """
    def __init__(self, env, rec_arrivals=False, absolute_arrivals=False, rec_waits=True, debug=False, selector=None):
        self.store = simpy.Store(env)
        self.env = env
        self.rec_waits = rec_waits
        self.rec_arrivals = rec_arrivals
        self.absolute_arrivals = absolute_arrivals
        self.waits = []
        self.arrivals = []
        self.debug = debug
        self.packets_rec = 0
        self.bytes_rec = 0
        self.selector = selector
        self.last_arrival = 0.0

    def put(self, pkt):
        if not self.selector or self.selector(pkt):
            now = self.env.now
            if self.rec_waits:
                self.waits.append(self.env.now - pkt.time)
            if self.rec_arrivals:
                if self.absolute_arrivals:
                    self.arrivals.append(now)
                else:
                    self.arrivals.append(now - self.last_arrival)
                self.last_arrival = now
            self.packets_rec += 1
            self.bytes_rec += pkt.size
            self.store.put(pkt)
            dfg_pkt = self.defragmentation(pkt)
            if self.debug:
                print(self.env.now, dfg_pkt)

    def defragmentation(self, pkt: Packet):
        flow_id = pkt.flow_id
        total_size = pkt.t_size
        fragments = list(msg for msg in self.store.items)
        defragment = EmptySet().union(Interval(frg.f_offset, frg.f_offset + frg.size) for frg in fragments)
        if defragment.measure == total_size:
            for frg in fragments:
                self.store.items.remove(frg)
        pkt = Packet(*pkt.make_args_for_defragment())
        return pkt


class UniPort(object):
    """ Models a switch output port with a given rate and buffer size limit in bytes.
        Set the "out" member variable to the entity to receive the packet.

        Parameters
        ----------
        env : simpy.Environment
            the simulation environment
        rate : float
            the bit rate of the port
        qlimit : integer (or None)
            a buffer size limit in bytes or packets for the queue (including items
            in service).
        limit_bytes : If true, the queue limit will be based on bytes if false the
            queue limit will be based on packets.
    """
    def __init__(self, env, rate, qlimit=None, limit_bytes=True, debug=False):
        self.store = simpy.Store(env)
        self.rate = rate
        self.env = env
        self.packets_rec = 0
        self.packets_drop = 0
        self.qlimit = qlimit
        self.limit_bytes = limit_bytes
        self.byte_size = 0  # Current size of the queue in bytes
        self.debug = debug
        self.busy = 0  # Used to track if a packet is currently being sent

    def get(self, size):
        pkt_list = list()
        tot_size_got = int()
        for pkt in self.store.items:
            if size == 0:
                break
            if size > pkt.size:
                pkt_list.append(pkt)
                self.store.items.remove(pkt)
                size -= pkt.size
                tot_size_got += pkt.size
            else:
                new_pkt = copy.deepcopy(pkt)
                new_pkt.size = size
                pkt_list.append(new_pkt)
                pkt.size -= size
                pkt.f_offset += size
                size = 0
                tot_size_got += new_pkt.size
        self.byte_size -= tot_size_got
        return pkt_list

    def put(self, pkt):
        self.packets_rec += 1
        tmp_byte_count = self.byte_size + pkt.size

        if self.qlimit is None:
            self.byte_size = tmp_byte_count
            return self.store.put(pkt)
        if self.limit_bytes and tmp_byte_count > self.qlimit:
            self.packets_drop += 1
            return
        elif not self.limit_bytes and len(self.store.items) >= self.qlimit-1:
            self.packets_drop += 1
        else:
            self.byte_size = tmp_byte_count
            return self.store.put(pkt)


class Timer:
    def __init__(self, env, timeout, func, args, condition="once"):
        self.env = env
        self.timeout = timeout
        self.func = func
        self.args = args
        if condition == "periodic":
            self.run = self.periodic
        elif condition == "once":
            self.run = self.once
        else:
            raise NotImplemented
        self.action = env.process(self.run())

    def periodic(self):
        done = False
        while not done:
            yield self.env.timeout(self.timeout)
            self.func(*self.args)
            done = True

    def once(self):
        done = False
        while not done:
            yield self.env.timeout(self.timeout)
            self.func(*self.args)
            done = True


class Counters:
    def __init__(self):
        self.ingress_unicast = int()
        self.ingress_collision = int()
        self.cycle_number = int()
        self.number_of_ont = int()

    def export_to_console(self):
        print(self.__dict__)


class Signal:
    def __init__(self, env, name, data: dict,
                 source, source_port, delay,
                 sig_physics=None):
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
        if sig_physics is not None:
            self.physics.update(sig_physics)

    def run(self):
        while self.alive:
            l_dev, l_port = self.source, self.source_port
            r_dev, sig, r_port = l_dev.s_start(self, l_port)
            new_sig_args = r_dev.r_start(sig, r_port)
            if new_sig_args is not None:
                for timer_data in new_sig_args:
                    timeout, args = timer_data
                    func = Signal
                    Timer(self.env, timeout, func, args, condition="once")
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
        self.observer = None

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
            self.snd_port_sig[int(port)] = list()
        self.counters = Counters()
        self.action = env.process(self.run())
        # env, rec_arrivals = False, absolute_arrivals = False, rec_waits = True, debug = False, selector = None)
        self.p_sink = PacketSink(env, debug=True)

        if "transmitter_type" in self.config:
            trans_type = self.config["transmitter_type"]
            if trans_type == "1G":
                self.transmitter_speed = 1244160000
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
        # print("{} : {} : recv {}".format(round(self.env.now, 2), self.name, sig.name))
        self.rec_port_sig[port].append(sig)
        rec_sigs = self.rec_port_sig[port]
        num_of_sigs = len(rec_sigs)
        if num_of_sigs > 1:
            print("{} : {} : ИНТЕРФЕРЕНЦИОННАЯ КОЛЛИЗИЯ. Сигналов: {}!!!"
                  .format(self.env.now, self.name, num_of_sigs))
            sn = True
            for i in rec_sigs:
                sn = False if "sn_response" not in i.data else sn*True
            if not sn:
                print("плохая коллизия")
                print(list((sig.name, sig.data["cycle_num"]) for sig in rec_sigs))
                # print(list(sig.name for sig in rec_sigs))
                # raise Exception("плохая коллизия")
            else:
                pass
            for i in rec_sigs:
                i.physics["collision"] = True
        return

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


class TrafGeneratorBuilder:
    # elif sid == "poisson":
    #     (par, size)
    # elif sid == "normal":
    #     sigma = config["sigma_si"]
    #     self.send_interval = (par, sigma, size)
    def __init__(self):
        self.traf_configs = json.load(open("traffic_types.json"))

    def generate_distribution(self, distribution, parameters: list):
        def configured_distr():
            return distribution(*parameters)
        return configured_distr

    def packet_source(self, env, flow_id, traf_type):
        def deterministic(parameter):
            return parameter  # time interval
        distribution = {"poisson": np.random.poisson, "normal": np.random.normal, "deterministic": deterministic}
        if traf_type in self.traf_configs["traffic"]:
            config = self.traf_configs["traffic"][traf_type]
            adistrib = distribution[config["send_interval_distribution"]]
            a_dist_params = list()
            for par in ["send_interval", "sigma_si"]:
                if par in config:
                    a_dist_params.append(config[par])
            adist = self.generate_distribution(adistrib, a_dist_params)
            sdistrib = distribution[config["size_of_packet_distribution"]]
            s_dist_params = list()
            for par in ["size_of_packet", "sigma_sop"]:
                if par in config:
                    s_dist_params.append(config[par])
            sdist = self.generate_distribution(sdistrib, s_dist_params)
        else:
            raise NotImplemented
        # (env, id, adist, sdist, initial_delay = 0, finish = float("inf"), flow_id = 0
        pg = PacketGenerator(env, flow_id, adist, sdist, flow_id=flow_id)
        return pg

    def uni_input_for_ont(self, env, pg, port_type=None):
        if port_type in self.traf_configs["ports"]:
            config = self.traf_configs["ports"][port_type]
            rate, qlimit = config["rate"], config["qlimit"]
        else:
            rate = 1000000
            qlimit = 65535
        # env, rate, qlimit = None, limit_bytes = True, debug = False
        uniport = UniPort(env, rate, qlimit)
        pg.out = uniport
        return uniport


class Ont(ActiveDev):
    def __init__(self, env, name, config):
        ActiveDev.__init__(self, env, name, config)
        if "activation_time" in self.config:
            self.time_activation = self.config["activation_time"] * 1000
        else:
            self.time_activation = 0

        self.STATE = "Offline"
        self.range_time_delta = list()
        self.traffic_generators = dict()
        self.current_allocations = dict()  # key alloc_id : value grant_size

        tgb = TrafGeneratorBuilder()
        if "Alloc" in config:
            for alloc_num in config["Alloc"]:
                traf_type = config["Alloc"][alloc_num]
                flow_id = self.name + "_" + alloc_num
                pg = tgb.packet_source(env, flow_id, traf_type)
                uni = tgb.uni_input_for_ont(env, pg, flow_id)
                self.traffic_generators[flow_id] = uni
                # self.current_allocations[tg.id] = tg.traf_class
                self.current_allocations[flow_id] = None
        if "0" not in config["Alloc"]:
            alloc_type = "type0"

    def run(self):
        if self.STATE is "Offline":
            yield self.env.timeout(self.time_activation)
            self.STATE = "Initial"
        while True:
            if self.STATE == "Initial":
                yield self.env.timeout(self.cycle_duration)
            elif self.STATE in ["Standby", "Operation"]:
                l_port = 0
                planned = dict()
                if len(self.snd_port_sig[l_port]) > 0:
                    planned = self.snd_port_sig[l_port].pop(0)
                if "s_time" in planned and "args" in planned:
                    planned_s_time = planned["s_time"]
                    args = planned["args"]
                    timeout = planned_s_time - self.env.now
                    yield self.env.timeout(timeout)
                    s_time = planned_s_time
                    now = self.env.now
                    Signal(*args)
                else:
                    yield self.env.timeout(self.cycle_duration)
            else:
                yield self.env.timeout(self.cycle_duration)

    def r_end(self, sig, port: int):
        # обработка на случай коллизии
        assert sig in self.rec_port_sig[port]
        self.rec_port_sig[port].remove(sig)
        if sig.physics["collision"]:
            self.counters.ingress_collision += 1
            return {}

        sig = self.oe_transform(sig)
        logging.debug("{} : {} : принят {}".format(self.env.now, self.name, sig.name))
        self.next_cycle_start = self.env.now + self.cycle_duration
        if self.STATE == "Offline":
            return
        if self.STATE == "Initial":
            self.STATE = "Standby"
        if self.STATE == "Standby":
            if "sn_request" in sig.data:
                # из принятого от OLT сигнала распознаём sn_request и планируем ответ на момент planned_s_time
                # delay = random.randrange(34, 36, 1) + random.randrange(0, 50, 1)
                delay = random.randrange(0, 80, 1) + 2*self.cycle_duration
                planned_s_time = round(self.env.now + delay, 2)
                planned_e_time = planned_s_time + 2
                sig_id = "{}:{}:{}".format(planned_s_time, self.name, planned_e_time)
                alloc_ids = self.current_allocations
                data = {"sn_response": (self.name, alloc_ids)}
                self.snd_port_sig[port].append({"s_time": planned_s_time, "args": [self.env, sig_id, data, self, port, 2]})
            if "sn_ack" in sig.data:
                for alloc in sig.data["sn_ack"]:
                    if alloc in self.traffic_generators:
                        self.current_allocations[alloc] = self.traffic_generators[alloc]
                allocs_acked = list(i for i in self.current_allocations.keys()
                                    if self.current_allocations[i] is not None)
                if len(allocs_acked) > 0:
                    logging.info("{} Авторизация на OLT подтверждена, allocs: {}".format(self.name, allocs_acked))
                # Формально тут должно быть "SerialNumber"
                # но без потери смысла для симуляции должно быть Ranging
                    self.STATE = "Ranging"
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
                if alloc_id in self.current_allocations:
                    data_to_send = dict()
                    allocation_start = allocation["StartTime"]
                    allocation_stop = allocation["StopTime"]
                    grant_size = allocation_stop - allocation_start
                    data = {}
                    if grant_size > 0:
                        intra_cycle_s_start = round(8*1000000*allocation_start / self.transmitter_speed, 2)
                        intra_cycle_e_start = round(8*1000000*allocation_stop / self.transmitter_speed, 2)
                        planned_s_time = self.next_cycle_start + intra_cycle_s_start - 2*avg_half_rtt + self.cycle_duration
                        planned_s_time = round(planned_s_time, 2)
                        planned_e_time = self.next_cycle_start + intra_cycle_e_start - 2*avg_half_rtt + self.cycle_duration
                        planned_e_time = round(planned_e_time, 2)
                        # полезно для отладки
                        planned_delta = planned_e_time - planned_s_time
                        if planned_delta <= 0:
                            break
                        s_time = planned_s_time
                        now = self.env.now
                        assert planned_s_time >= self.env.now

                        tg = self.traffic_generators[alloc_id]
                        # assert tg.id == alloc_id
                        pkts = list()
                        if len(tg.store.items) == 0:
                            pass
                        else:  # len(tg.queue) > 0:
                            pkts = tg.get(grant_size)
                        data.update({alloc_id: pkts})
                        data.update({"cycle_num": sig.data["cycle_num"]})
                        data.update({"allocation": allocation})
                        sig_id = "{}:{}:{}".format(planned_s_time, self.name, planned_e_time)
                        a = len(self.snd_port_sig[port])
                        # assert len(self.snd_port_sig[port]) == 0
                        self.snd_port_sig[port].append({"s_time": planned_s_time,
                                               "args": [self.env, sig_id, data, self, port, planned_delta]})
                    break
        else:
            raise Exception("State {} not implemented".format(self.STATE))
        if self.STATE != "Offline":
            self.counters.ingress_unicast += 1
        return {}


class Olt(ActiveDev):
    def __init__(self, env, name, config):
        ActiveDev.__init__(self, env, name, config)
        self.sn_request_interval = config["sn_request_interval"]
        self.sn_quiet_interval = config["sn_quiet_interval"]
        self.sn_request_next = 0
        self.sn_request_quiet_interval_end = 0
        self.maximum_ont_amount = int(self.config["maximum_ont_amount"])
        dba_config = dict()
        # self.upstream_interframe_interval = self.config["upstream_interframe_interval"]  # 10 # in bytes
        for dba_par in ["cycle_duration", "transmitter_type",
                        "maximum_allocation_start_time", "upstream_interframe_interval"]:
            if dba_par in config:
                dba_config[dba_par] = config[dba_par]

        self.snd_port_sig[0] = dict()
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
                data = {"bwmap": bwmap, "sn_request": True, "s_timestamp": self.env.now, "cycle_num": self.counters.cycle_number}
                # тут лучше сделать таймер
                # data.update(self.snd_port_sig[l_port])
                # self.snd_port_sig[l_port].clear()
                start = round(self.env.now, 2)
                delay = self.cycle_duration
                end = start + delay
                sig_id = "{}:{}:{}".format(start, self.name, end)
                Signal(self.env, sig_id, data, self, l_port, delay)
                yield self.env.timeout(self.cycle_duration + 1e-12)
                self.counters.cycle_number += 1
                bwmap = self.dba.sn_request()
                data = {"bwmap": bwmap, "s_timestamp": self.env.now, "cycle_num": self.counters.cycle_number}
                # data.update(self.snd_port_sig[l_port])
                start = round(self.env.now, 2)
                delay = self.cycle_duration
                end = start + delay
                sig_id = "{}:{}:{}".format(start, self.name, end)
                Signal(self.env, sig_id, data, self, l_port, delay)
                yield self.env.timeout(self.cycle_duration + 1e-12)
                self.counters.cycle_number += 1
                self.STATE = "Normal"
            elif self.STATE == "Normal":
                l_port = 0
                data = {"cycle_num": self.counters.cycle_number}
                data.update(self.snd_port_sig[l_port])
                self.snd_port_sig[l_port].clear()
                start = round(self.env.now, 2)
                delay = self.cycle_duration
                end = start + delay
                sig_id = "{}:{}:{}".format(start, self.name, end)
                Signal(self.env, sig_id, data, self, l_port, delay)
                yield self.env.timeout(self.cycle_duration + 1e-12)
                self.counters.cycle_number += 1

    def r_end(self, sig, port):
        ret = dict()
        # обработка интерференционной коллизии
        # каждый принимаемый сигнал должен быть помечен как коллизирующий
        for r_sig in self.rec_port_sig[port]:
            if r_sig.name == sig.name:
                self.rec_port_sig[port].remove(r_sig)
                if r_sig.physics["collision"]:
                    self.counters.ingress_collision += 1
                    return {}
                break

        self.counters.ingress_unicast += 1
        logging.debug("{} : {} : принят {}".format(self.env.now, self.name, sig.name))
        self.oe_transform(sig)
        if "sn_response" in sig.data and self.env.now <= self.sn_request_quiet_interval_end:
            # проверка на содержание ответов на запросы регистрации в сообщении
            s_number = sig.data["sn_response"][0]
            allocs = sig.data["sn_response"][1]
            self.dba.register_new_ont(s_number, allocs)
            self.counters.number_of_ont = len(self.dba.ont_discovered)
            if "sn_ack" not in self.snd_port_sig[port]:
                self.snd_port_sig[port]["sn_ack"] = list()
            self.snd_port_sig[port]["sn_ack"].extend(allocs)
        else:
            # нормальный приём сообщения
            ont_allocs = list(alloc for alloc in sig.data if "ONT" in alloc)
            for alloc in ont_allocs:
                pkts = sig.data[alloc]
                for pkt in pkts:
                    self.p_sink.put(pkt)
                    self.dba.register_packet(alloc, sig.data[alloc])
            return ret


import math
light_velocity = 2*10**8


class PassiveDev(Dev):
    def __init__(self, env, name, config):
        Dev.__init__(self, env, name, config)
        self.delay = 0
        self.length = 0
        self.power_matrix = [[0]]

    def s_start(self, sig, l_port):
        r_port, r_dev = self.out[l_port]
        return r_dev, sig, r_port

    def r_start(self, sig, port):
        matrix_ratios = self.power_matrix[port]
        out_sig_args = list()  # of tuples
        for l_port in range(len(matrix_ratios)):
            ratio = matrix_ratios[l_port]
            out_sig_arg = self.multiply_power(sig, ratio, l_port)
            if out_sig_arg is not False:
                out_sig_args.append((self.delay, out_sig_arg))
        return out_sig_args

    def s_end(self, sig, port):
        return

    def r_end(self, sig, port):
        return

    def multiply_power(self, sig, ratio, l_port):
        new_power = sig.physics["power"] * ratio
        if new_power > 0:
            data_to_send = sig.data
            sig_name = sig.name + ":{}:{}".format(self.name, l_port)
            delay = sig.delay
            sig_physics = {"type": "optic",
                           "power": new_power,
                           "distance_passed": sig.physics["distance_passed"] + self.length}
            sig_arg = [self.env, sig_name, data_to_send, self, l_port, delay, sig_physics]
            return sig_arg
        return False


class Splitter(PassiveDev):
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


class Fiber(PassiveDev):
    def __init__(self, env, name, config):
        PassiveDev.__init__(self, env, name, config)
        self.type = self.config["type"]
        self.length = float(self.config["length"])
        self.delay = int(round(10**6 * 1000 * self.length / light_velocity))
        if self.type == "G657":
            self.att = 0.22
        else:
            raise Exception("Fiber type {} not implemented".format(self.type))
        ratio = math.exp(- self.att * self.length / 4.34)
        self.power_matrix = [[0, ratio],
                             [ratio, 0]]


class DevObserver(Thread):
    result_dir = './result/'

    def __init__(self, config):
        Thread.__init__(self)
        self.name = "Traffic visualizer"
        # {dev.name + "::" + port: [(time, sig.__dict__)]}
        self.observer_result = dict()
        time_ranges_to_show = config["observers"]["flow"]["time_ranges"]
        self.time_ranges_to_show = EmptySet().union(Interval(i[0], i[1]) for i in time_ranges_to_show)
        self.time_horisont = max(self.time_ranges_to_show.boundary)
        self.target = self.notice
        # self.source = source
        self.ev_wait = None

    def run(self):
        while True:
            print('ну привет. я %s', self.name)
            self.ev_wait.wait()  # wait for event

            self.ev_wait.clear()  # clean event for future
        pass

    def notice(self, cur_time, data):
        if cur_time not in self.time_ranges_to_show:
            return

        # for ev_time in passed_schedule:
        #     for event in passed_schedule[ev_time]:
        #         dev, state, sig, port = event["dev"], event["state"], event["sig"], event["port"]
        #         # if sig.physics["type"] == "electric":
        #         if "OLT" in dev.name and state == "r_end":
        #             if sig.name not in self.observer_result:
        #                 self.observer_result[sig.name] = dict()
        #             data = dict()
        #             data.update(sig.data)
        #             # for dev_name in ["OLT"]:  # , "OLT"]
        #             # if dev_name in dev.name:
        #             self.observer_result[sig.name][ev_time] = data
        #         # {имя сигнала : {время: данные сигнала}}
        return

    def cook_result(self):
        flow_time_result = dict()
        for dev_name in self.observer_result:
            time_data_result = self.observer_result[dev_name]
            for time_r in time_data_result:
                tcont_data = time_data_result[time_r]
                for alloc in tcont_data:
                    if dev_name in alloc:
                        if alloc not in flow_time_result:
                            flow_time_result[alloc] = dict()
                        if time_r not in flow_time_result[alloc]:
                            flow_time_result[alloc][time_r] = tcont_data[alloc]
        return flow_time_result

    def make_results(self):
        fig = plt.figure(1, figsize=(15, 15))
        fig.show()

        # number_of_sigs = len(self.observer_result)
        flow_time_result = self.cook_result()
        number_of_flows = len(flow_time_result)
        flow_index = 1
        for flow_name in flow_time_result:
            time_result, latency_result = list(), list()
            for time_r in flow_time_result[flow_name]:
                packet_data = flow_time_result[flow_name][time_r]
                if "born_time" in packet_data:
                    time_result.append(time_r)
                    latency_result.append(time_r - packet_data["born_time"])
            ax = fig.add_subplot(number_of_flows, 1, flow_index)
            flow_index += 1
            plt.ylabel(flow_name)
            ax.plot(time_result, latency_result)
            fig.canvas.draw()
            time.sleep(1)

        # ax.set_xticklabels(points_to_watch)
        fig.canvas.draw()
        # time.sleep(1)
        # plt.show()
        fig.savefig(self.result_dir + "packets.png", bbox_inches="tight")


def NetFabric(net, env, sim_config):
    classes = {"OLT": Olt, "ONT": Ont, "Splitter": Splitter, "Fiber": Fiber}
    devices = dict()
    connection = dict()
    obs = DevObserver(sim_config)
    obs.start()
    # Create devices
    for dev_name in net:
        config = net[dev_name]
        for dev_type in classes:
            if dev_type in dev_name:
                constructor = classes[dev_type]
                dev = constructor(env, dev_name, config)
                dev.observer = obs
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
    return devices


def main():
    sim_config = Dict(json.load(open('./dba.json')))
    net = json.load(open("network3.json"))
    time_horizont = sim_config.horizont if "horizont" in sim_config else 1000

    env = simpy.Environment()
    devices = NetFabric(net, env, sim_config)
    t_start = time.time()
    env.run(until=time_horizont)

    print("{} End of simulation in {}...".format(env.now, round(time.time() - t_start, 2)),
          "\n***Preparing results***".format())
    for dev_name in devices:
        if re.search("[ON|LT]", dev_name) is not None:
            dev = devices[dev_name]
            print(dev_name, end="")
            dev.counters.export_to_console()
    # make_results()


if __name__ == "__main__":
    main()
