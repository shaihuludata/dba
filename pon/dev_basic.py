from support.counters import Counters
import logging


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
        self.p_sink = None

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
            logging.debug("{} : {} : ИНТЕРФЕРЕНЦИОННАЯ КОЛЛИЗИЯ. Сигналов: {}!!!"
                  .format(self.env.now, self.name, num_of_sigs))
            # если все коллизирующие сигналы - запросы серийников, то ничего страшного
            sn = True
            for i in rec_sigs:
                sn = False if "sn_response" not in i.data else sn*True
            # иначе их все надо пометить как коллизирующие
            if not sn:
                print("плохая коллизия")
                print(list((sig.name, sig.data["cycle_num"]) for sig in rec_sigs))
                # print(list(sig.name for sig in rec_sigs))
                # raise Exception("плохая коллизия")
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
