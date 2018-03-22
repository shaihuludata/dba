
class PassiveDevice:
    def __init__(self):
        self.power_matrix = 0


class Splitter(PassiveDevice):
    def __init__(self, type):
        if type == "1:4":
            self.power_matrix = [[0, 0.25, 0.25, 0.25, 0.25],
                                 [0.25, 0, 0, 0, 0],
                                 [0.25, 0, 0, 0, 0],
                                 [0.25, 0, 0, 0, 0],
                                 [0.25, 0, 0, 0, 0]]
        else:
            print('Unknown Splitter type')
            #raise Error

    def transit(self, port, signal):
        splitted_signals = dict()
        matrix_ratios = self.power_matrix[port]
        for out_port in range(len(matrix_ratios)):
            ratio = matrix_ratios[out_port]
            #signal_port = signal
            #signal_port.physics['power'] = signal_port.physics['power'] * ratio
            splitted_signals[out_port] = signal.split(ratio)
        return splitted_signals
