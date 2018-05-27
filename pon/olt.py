from pon.dev_basic import ActiveDev
import logging
from pon.signal import Signal


class Olt(ActiveDev):
    def observe(fn):
        return fn

    def __init__(self, env, name, config):
        ActiveDev.__init__(self, env, name, config)
        self.sn_request_interval = config["sn_request_interval"]
        self.sn_quiet_interval = config["sn_quiet_interval"]
        self.sn_request_next = 0
        self.sn_request_quiet_interval_end = 0
        self.maximum_ont_amount = int(self.config["maximum_ont_amount"])
        self.snd_port_sig[0] = dict()
        self.dba = None

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
                yield self.env.timeout(self.cycle_duration + 1e-11)
                self.counters.cycle_number += 1
                bwmap = self.dba.sn_request()
                data = {"bwmap": bwmap, "s_timestamp": self.env.now, "cycle_num": self.counters.cycle_number}
                # data.update(self.snd_port_sig[l_port])
                start = round(self.env.now, 2)
                delay = self.cycle_duration
                end = start + delay
                sig_id = "{}:{}:{}".format(start, self.name, end)
                Signal(self.env, sig_id, data, self, l_port, delay)
                yield self.env.timeout(self.cycle_duration + 1e-11)
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
                yield self.env.timeout(self.cycle_duration + 1e-11)
                self.counters.cycle_number += 1

    @observe
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
