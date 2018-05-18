from random import expovariate
import simpy
from examples_and_tries.SimComponents import PacketGenerator, PacketSink
from addict import Dict
import json
import copy


class Signal:
    def __init__(self, env, name, data, source):
        self.env = env
        self.name = name
        self.alive = True
        self.physics = dict()
        self.physics['type'] = 'electric'
        self.physics['collision'] = False
        self.physics['distance_passed'] = 0
        self.data = data
        self.source = source
        self.action = env.process(self.run())

    def run(self):
        while self.alive:
            l_dev, l_port = self.source[0], self.source[1]
            r_dev, sig, r_port = l_dev.s_start(self, l_port)
            delay = r_dev.r_start(sig, r_port)
            yield self.env.timeout(delay)
            self.alive = False


class Dev(object):
    def __init__(self, env, name, config):
        self.config = config
        self.name = name
        # self.rate = config['type']
        self.env = env
        self.out = dict()
        self.cycle_length = 125
        self.r_port_sig = dict()
        self.s_port_sig = dict()
        self.action = env.process(self.run())

    def run(self):
        pass

    def s_start(self, sig, l_port):
        sig = self.eo_transform(sig)
        r_port, r_dev = self.out[l_port]
        return r_dev, sig, r_port

    def r_start(self, sig, port: int):
        print('{} : {} : принимаю {}'.format(self.env.now, self.name, sig.name))
        sig.alive = False
        return 0

    def eo_transform(self, sig):
        sig_type = sig.physics['type']
        optic_parameters = {'power': float(self.config['transmitter_power']),
                            'wavelength': float(self.config['transmitter_wavelength'])}
        if sig.physics['type'] == 'electric':
            sig.physics['type'] = 'optic'
        else:
            raise Exception
        sig.physics.update(optic_parameters)
        return sig


class Ont(Dev):
    def run(self):
        while True:
            for l_port in self.out:
                data_to_send = {}
                sig_id = '{}:{}:{}'.format(self.env.now, self.name, self.env.now + 125)
                sig = Signal(self.env, sig_id, data_to_send, (self, l_port))
                print('сигнал {}'.format(sig_id))
            yield self.env.timeout(125)


class Olt(Dev):
    def run(self):
        while True:
            for l_port in self.out:
                data_to_send = {}
                sig_id = '{}:{}:{}'.format(self.env.now, self.name, self.env.now + 125)
                sig = Signal(self.env, sig_id, data_to_send, (self, l_port))
                print('сигнал {}'.format(sig_id))
            yield self.env.timeout(125)


class Splitter(Dev):
    length = 0.000001
    delay = 0
    power_matrix = [[0, 0.25, 0.25, 0.25, 0.25],
                         [0.25, 0, 0, 0, 0],
                         [0.25, 0, 0, 0, 0],
                         [0.25, 0, 0, 0, 0],
                         [0.25, 0, 0, 0, 0]]

    def run(self):
        while True:
            yield self.env.timeout(125)

    def multiply_power(self, sig, ratio, l_port):
        new_power = sig.physics['power'] * ratio
        if new_power > 0:
            data_to_send = sig.data
            sig_id = sig.name
            new_sig = Signal(self.env, sig_id, data_to_send, (self, l_port))
            new_sig.physics['power'] = new_power
            new_sig.physics['distance_passed'] += self.length
            return new_sig
        return False

    def s_start(self, sig, l_port):
        r_port, r_dev = self.out[l_port]
        return r_dev, sig, r_port

    def r_start(self, sig, port):
        matrix_ratios = self.power_matrix[port]
        for l_port in range(len(matrix_ratios)):
            ratio = matrix_ratios[l_port]
            splitted_sig = self.multiply_power(sig, ratio, l_port)
            if splitted_sig is not False:
                splitted_sig.name += ':{}:{}'.format(self.name, l_port)
                splitted_sig.source = (self, l_port)
        del(sig)
        return self.delay


def NetFabric(net, env):
    classes = {'OLT': Olt, 'ONT': Ont, 'Splitter': Splitter}
    devices = dict()
    connection = dict()
    # Create devices
    for dev_name in net:
        config = net[dev_name]
        for dev_type in classes:
            if dev_type in dev_name:
                constructor = classes[dev_type]
                dev = constructor(env, dev_name, config)
                devices[dev_name] = dev
                connection[dev_name] = config['ports']
    # Interconnect devices
    for dev_name in connection:
        l_dev = devices[dev_name]
        con = connection[dev_name]
        for l_port in con:
            r_dev_name, r_port = con[l_port].split('::')
            r_dev = devices[r_dev_name]
            l_port = int(l_port)
            l_dev.out[l_port] = (int(r_port), r_dev)
            l_dev.r_port_sig[l_port] = simpy.Store(env, capacity=1)
            l_dev.s_port_sig[l_port] = simpy.Store(env, capacity=1)


def main():
    config = Dict({'horizont': 250})
    net = json.load(open('network1.json'))

    env = simpy.Environment()
    NetFabric(net, env)
    env.run(until=config.horizont)

    print('End of simulation... Preparing results.')
    # make_results()


if __name__ == '__main__':
    main()
