import simpy
import logging
import copy
from sympy import EmptySet, Interval
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
    def __init__(self, env, id,
                 adist, sdist,
                 active_dist=None, passive_dist=None,
                 initial_delay=0, finish=float("inf"), flow_id=0,
                 cos=0, service=None):
        # self.traf_class = config["class"]
        # self.service = config["service"]
        # self.max_queue_size = config["max_queue_size"]  # in number_of_packets
        self.id = id
        self.env = env
        self.adist = adist
        self.sdist = sdist
        if active_dist is not None and passive_dist is not None:
            self.active_dist = active_dist
            self.passive_dist = passive_dist
        self.initial_delay = initial_delay
        self.finish = finish
        self.out = None
        self.action = env.process(self.run())
        self.flow_id = flow_id
        self.service = service
        self.cos = cos
        self.p_counters = PacketCounters()

    def run(self):
        yield self.env.timeout(self.initial_delay)
        while self.env.now < self.finish:
            activity_time = self.env.now + self.active_dist()
            while self.env.now < activity_time:
                # wait for next transmission
                send_interval = self.adist()
                yield self.env.timeout(send_interval)
                self.p_counters.packets_sent += 1
                pkt_id = "{}_{}".format(self.id, self.env.now)
                p = Packet(self.env.now,
                           round(self.sdist()),
                           pkt_id,
                           src=self.id, flow_id=self.flow_id,
                           cos_class=self.cos,
                           packet_num=self.p_counters.packets_sent)
                self.out.put(p)
                if "ONT4" in self.id:
                    pass
                    # print(.flow_id, pkt.num, pkt.size)
            yield self.env.timeout(self.passive_dist())

    def active_dist(self):
        return self.finish

    def passive_dist(self):
        return 0


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

    def defragmentation(self, frg):
        flow_id = frg.flow_id
        total_size = frg.t_size
        fragments = list(msg for msg in self.store.items if msg.id == frg.id)

        defragment = EmptySet().union(Interval(frg.f_offset, frg.f_offset + frg.size)
                                      for frg in fragments)
        dfg_measure = defragment.measure
        if dfg_measure == total_size:
            for frg in fragments:
                self.store.items.remove(frg)

            pkt = Packet(*frg.make_args_for_defragment())
            pkt.dfg_time = self.env.now
            logging.debug(self.env.now, pkt)
            return pkt

    def check_dfg_pkt(self, dfg):
        if self.debug:
            print(round(self.env.now, 3), dfg)
            if "ONT4" in dfg.flow_id:
                print(dfg.flow_id, dfg.num, dfg.size)


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
        pkts_to_extract = list()
        pkts_to_remove = list()
        tot_size_got = int()
        # pkt_numbered = dict()
        # for pkt in self.store.items:
        #     pkt_nums_list.append(pkt.num)
        # pkt_nums_list.sort()
        pkts = self.store.items
        for pkt in self.store.items:
            if alloc_size == 0:
                break
            if alloc_size >= pkt.size:
                pkts_to_extract.append(pkt)
                pkts_to_remove.append(pkt)
                self.p_counters.packets_sent += 1
                alloc_size -= pkt.size
                tot_size_got += pkt.size
            else:
                new_pkt = copy.deepcopy(pkt)
                new_pkt.size = alloc_size
                pkts_to_extract.append(new_pkt)
                pkt.size -= alloc_size
                pkt.f_offset += alloc_size
                alloc_size = 0
                tot_size_got += new_pkt.size
            # if "ONT4" in pkt.flow_id:
            #     print(pkt.flow_id, pkt.num, pkt.size)

        for pkt in pkts_to_remove:
            self.store.items.remove(pkt)
        self.byte_size -= tot_size_got
        return pkts_to_extract

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
