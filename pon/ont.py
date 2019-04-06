from pon.dev_basic import ActiveDev
import random
from pon.signal import Signal
import logging
from memory_profiler import profile as mprofile


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
                    if timeout < 0:
                        print("фыв")
                    yield self.env.timeout(timeout)
                    s_time = planned_s_time
                    now = self.env.now
                    Signal(*args)
                else:
                    yield self.env.timeout(self.cycle_duration/2)
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
                planned_e_time = planned_s_time + 0.0000001
                sig_id = "{}:{}:{}".format(planned_s_time, self.name, planned_e_time)
                alloc_ids = self.current_allocations
                data = {"sn_response": (self.name, alloc_ids)}
                self.snd_port_sig[port].append({"s_time": planned_s_time, "args": [self.env, sig_id, data, self, port, 2]})
            if "sn_ack" in sig.data:
                for alloc in sig.data["sn_ack"]:
                    if alloc in self.traffic_generators:
                        self.current_allocations[alloc] = self.traffic_generators[alloc]
                allocs_acked = list(i for i in self.current_allocations.keys()
                                    if type(self.current_allocations[i]) is not int)
                if len(allocs_acked) > 0:
                    logging.debug("{} Авторизация на OLT подтверждена, allocs: {}".format(self.name, allocs_acked))
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
                    data = dict()
                    if grant_size > 0:
                        intra_cycle_s_start = round(8*1000000*allocation_start / self.transmitter_speed, 2)
                        intra_cycle_e_start = round(8*1000000*allocation_stop / self.transmitter_speed, 2)
                        correction = self.next_cycle_start - 2 * avg_half_rtt + self.cycle_duration
                        planned_s_time = round(intra_cycle_s_start + correction, 2)
                        planned_e_time = round(intra_cycle_e_start + correction, 2)
                        planned_delta = planned_e_time - planned_s_time
                        if planned_delta <= 0:
                            continue
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
                        data.update({"grant_size": grant_size})
                        sig_id = "{}:{}:{}".format(planned_s_time, self.name, planned_e_time)
                        a = len(self.snd_port_sig[port])
                        # assert len(self.snd_port_sig[port]) == 0
                        self.snd_port_sig[port].append({"s_time": planned_s_time,
                                                        "args": [self.env, sig_id, data,
                                                                 self, port, planned_delta - 1e-9]})
        else:
            raise Exception("State {} not implemented".format(self.STATE))
        if self.STATE != "Offline":
            self.counters.ingress_unicast += 1
        return {}
