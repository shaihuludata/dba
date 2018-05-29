import simpy
import json
import logging
import copy
from sympy import EmptySet, Interval
import numpy as np
from support.counters import PacketCounters
from uni_traffic.packet import Packet


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
        # self.max_queue_size = config["max_queue_size"]  # in number_of_packets
        self.id = id
        self.env = env
        self.adist = adist
        self.sdist = sdist
        self.initial_delay = initial_delay
        self.finish = finish
        self.out = None
        self.action = env.process(self.run())
        self.flow_id = flow_id
        self.service = None
        self.p_counters = PacketCounters()

    def run(self):
        yield self.env.timeout(self.initial_delay)
        while self.env.now < self.finish:
            # wait for next transmission
            send_interval = self.adist()
            yield self.env.timeout(send_interval)
            self.p_counters.packets_sent += 1
            pkt_id = "{}_{}".format(self.id, self.env.now)
            p = Packet(self.env.now,
                       round(self.sdist()),
                       pkt_id,
                       src=self.id, flow_id=self.flow_id,
                       packet_num=self.p_counters.packets_sent)
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
    def __init__(self, env, rec_arrivals=False,
                 absolute_arrivals=False, rec_waits=True, debug=False, selector=None):
        self.store = simpy.Store(env)
        self.env = env
        self.rec_waits = rec_waits
        self.rec_arrivals = rec_arrivals
        self.absolute_arrivals = absolute_arrivals
        self.waits = []
        self.arrivals = []
        self.debug = debug
        self.bytes_rec = 0
        self.selector = selector
        self.last_arrival = 0.0
        self.packets_to_defragment = dict()
        self.p_counters = PacketCounters()

    def put(self, pkt):
        if not self.selector or self.selector(pkt):
            now = self.env.now
            if self.rec_waits:
                self.waits.append(self.env.now - pkt.s_time)
            if self.rec_arrivals:
                if self.absolute_arrivals:
                    self.arrivals.append(now)
                else:
                    self.arrivals.append(now - self.last_arrival)
                self.last_arrival = now
            self.p_counters.fragments_rec += 1
            self.bytes_rec += pkt.size
            self.store.put(pkt)
            if pkt.id not in self.packets_to_defragment:
                self.packets_to_defragment[pkt.id] = EmptySet()
            self.packets_to_defragment[pkt.id] = self.packets_to_defragment[pkt.id]\
                .union(Interval(pkt.f_offset, pkt.f_offset + pkt.size))
            if self.packets_to_defragment[pkt.id].measure == pkt.t_size:
                defragmented_pkt = self.defragmentation(pkt)
                self.p_counters.packets_rec += 1
                self.check_dfg_pkt(defragmented_pkt)

    def run(self):
        while not self.end_flag:
            self.ev_defrag.wait(timeout=5)  # wait for event
            for pkt in self.packets_to_defragment:
                flow_id = pkt.flow_id
                total_size = pkt.t_size
                fragments = list(msg for msg in self.store.items)
                defragment = EmptySet().union(Interval(frg.f_offset, frg.f_offset + frg.size) for frg in fragments)
                if defragment.measure == total_size:
                    for frg in fragments:
                        self.store.items.remove(frg)
                pkt = Packet(*pkt.make_args_for_defragment())
                if self.debug:
                    print(self.env.now, pkt)
                    print(round(self.env.now, 3), pkt)
                self.ev_defrag.clear()  # clean event for future

    def defragmentation(self, frg):
        flow_id = frg.flow_id
        total_size = frg.t_size
        fragments = list(msg for msg in self.store.items if msg.id == frg.id)
        defragment = EmptySet().union(Interval(frg.f_offset, frg.f_offset + frg.size)
                                      for frg in fragments)
        if defragment.measure == total_size:
            for frg in fragments:
                self.store.items.remove(frg)
            pkt = Packet(*frg.make_args_for_defragment())
            pkt.dfg_time = self.env.now
            logging.debug(self.env.now, pkt)
            if self.debug:
                print(round(self.env.now, 3), pkt)
            return pkt

    def check_dfg_pkt(self, dfg):
        pass


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
        self.qlimit = qlimit
        self.limit_bytes = limit_bytes
        self.byte_size = 0  # Current size of the queue in bytes
        self.debug = debug
        self.busy = 0  # Used to track if a packet is currently being sent
        self.traf_class = None
        self.p_counters = PacketCounters()

    def get(self, alloc_size):
        pkt_list = list()
        tot_size_got = int()
        for pkt in self.store.items:
            if alloc_size == 0:
                break
            if alloc_size > pkt.size:
                pkt.alloc = alloc_size
                pkt_list.append(pkt)
                self.store.items.remove(pkt)
                self.p_counters.packets_sent += 1
                alloc_size -= pkt.size
                tot_size_got += pkt.size
            else:
                new_pkt = copy.deepcopy(pkt)
                new_pkt.size = alloc_size
                pkt.alloc = alloc_size
                pkt_list.append(new_pkt)
                pkt.size -= alloc_size
                pkt.f_offset += alloc_size
                alloc_size = 0
                tot_size_got += new_pkt.size
        self.byte_size -= tot_size_got
        return pkt_list

    def put(self, pkt):
        self.p_counters.packets_rec += 1
        tmp_byte_count = self.byte_size + pkt.size

        if self.qlimit is None:
            self.byte_size = tmp_byte_count
            return self.store.put(pkt)
        if self.limit_bytes and tmp_byte_count > self.qlimit:
            self.p_counters.packets_drop += 1
            return
        elif not self.limit_bytes and len(self.store.items) >= self.qlimit-1:
            self.p_counters.packets_drop += 1
        else:
            self.byte_size = tmp_byte_count
            return self.store.put(pkt)


class TrafficGeneratorBuilder:
    traf_classes = {"voice": 0, "video": 1, "data": 2, "best_effort": 3}
    # elif sid == "poisson":
    #     (par, size)
    # elif sid == "normal":
    #     sigma = config["sigma_si"]
    #     self.send_interval = (par, sigma, size)

    def __init__(self):
        self.traf_configs = json.load(open("./uni_traffic/traffic_types.json"))

    def generate_distribution(self, distribution, parameters: list):
        def configured_distr():
            return distribution(*parameters)
        return configured_distr

    def packet_source(self, env, flow_id, traf_type):
        def deterministic(parameter):
            return parameter  # time interval
        distribution = {"poisson": np.random.poisson,
                        "normal": np.random.normal,
                        "deterministic": deterministic}
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
        pg.service = config["service"]
        return pg

    def uni_input_for_ont(self, env, pg, port_type=None):
        if port_type in self.traf_configs["ports"]:
            config = self.traf_configs["ports"][port_type]
            rate, qlimit = config["rate"], config["qlimit"]
        else:
            rate = 1000000
            qlimit = 200000
        # env, rate, qlimit = None, limit_bytes = True, debug = False
        uniport = UniPort(env, rate, qlimit)
        uniport.traf_class = self.traf_classes[pg.service]
        pg.out = uniport
        return uniport
