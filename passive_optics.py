from pon_device import PonDevice
from signal import Signal
import copy


class PassiveDevice(PonDevice):
    def __init__(self):
        self.power_matrix = 0


class Splitter(PassiveDevice):
    def __init__(self, name, config):
        self.name = name
        self.type = config['type']
        if self.type == '1:4':
            self.power_matrix = [[0, 0.25, 0.25, 0.25, 0.25],
                                 [0.25, 0, 0, 0, 0],
                                 [0.25, 0, 0, 0, 0],
                                 [0.25, 0, 0, 0, 0],
                                 [0.25, 0, 0, 0, 0]]
        else:
            print('Unknown Splitter type')
            #raise Error

    def split_power(self, sig, ratio):
        new_sig = copy.deepcopy(sig)
        new_sig.physics['power'] *= ratio
        return new_sig

    def recv_signal(self, port:int, sig:Signal):
        splitted_signals = dict()
        matrix_ratios = self.power_matrix[port]
        for out_port in range(len(matrix_ratios)):
            ratio = matrix_ratios[out_port]
            splitted_sig = self.split_power(sig, ratio)
            if splitted_sig.physics['power'] > 0:
                splitted_signals[out_port] = [splitted_sig, 0]
        return splitted_signals

