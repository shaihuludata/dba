from pon.dev_basic import Dev
import math
from pon.signal import Signal
from support.timers import Timer
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
        for l_port in range(len(matrix_ratios)):
            ratio = matrix_ratios[l_port]
            out_sig_arg = self.multiply_power(sig, ratio, l_port)
            if out_sig_arg is not False:
                # надо породить новые сигналы на выходах
                Timer(self.env, self.delay, Signal, out_sig_arg, condition="once")

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
