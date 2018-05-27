from old.pon_device import PonDevice
import copy
import math

light_velocity = 2*10**8


class PassiveDevice(PonDevice):

    def __init__(self, name, config):
        PonDevice.__init__(self, name, config)


class Splitter(PassiveDevice):

    def __init__(self, name, config):
        PassiveDevice.__init__(self, name, config)
        # self.name = name
        self.length = 0.000001
        self.type = self.config['type']
        if self.type == '1:2':
            self.power_matrix = [[0, 0.25, 0.25],
                                 [0.25, 0, 0],
                                 [0.25, 0, 0]]
        elif self.type == '1:4':
            self.power_matrix = [[0, 0.25, 0.25, 0.25, 0.25],
                                 [0.25, 0, 0, 0, 0],
                                 [0.25, 0, 0, 0, 0],
                                 [0.25, 0, 0, 0, 0],
                                 [0.25, 0, 0, 0, 0]]
        else:
            raise Exception('Unknown splitter type {}'.format(self.type))

    def multiply_power(self, sig, ratio):
        new_sig = copy.deepcopy(sig)
        new_sig.physics['power'] *= ratio
        new_sig.external.distance_passed += self.length
        return new_sig

    def s_start(self, sig, port):
        return self.name, port, sig

    def r_start(self, sig, port):
        transitted_signals = dict()
        matrix_ratios = self.power_matrix[port]
        for out_port in range(len(matrix_ratios)):
            ratio = matrix_ratios[out_port]
            splitted_sig = self.multiply_power(sig, ratio)
            splitted_sig.id += ':{}:{}'.format(self.name, out_port)
            if splitted_sig.physics['power'] > 0:
                transitted_signals[out_port] = {"sig": splitted_sig, "delay": 0}
        return transitted_signals

    def s_end(self, sig, port: int):
        output = (self.name, port, sig)
        return output

    def r_end(self, sig, port: int):
        # output = {"sig": sig, "delay": 0}
        return self.r_start(sig, port)


class Fiber(Splitter):

    def __init__(self, name, config):
        PassiveDevice.__init__(self, name, config)
        self.type = self.config['type']
        self.length = float(self.config['length'])
        self.delay = int(round(10**6 * 1000 * self.length / light_velocity))
        if self.type == "G657":
            self.att = 0.22
        else:
            raise Exception('Fiber type {} not implemented'.format(self.type))
        ratio = math.exp(- self.att * self.length / 4.34)
        self.power_matrix = [[0, ratio],
                             [ratio, 0]]

    def r_start(self, sig, port: int):
        transitted_signals = dict()
        matrix_ratios = self.power_matrix[port]
        for out_port in range(len(matrix_ratios)):
            ratio = matrix_ratios[out_port]
            out_sig = self.multiply_power(sig, ratio)
            out_sig.id += ':{}:{}'.format(self.name, out_port)
            if out_sig.physics['power'] > 0:
                transitted_signals[out_port] = {"sig": out_sig, "delay": self.delay}
        return transitted_signals

