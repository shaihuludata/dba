from random import expovariate
import simpy
from examples_and_tries.SimComponents import PacketGenerator, PacketSink
from addict import Dict
import json
import copy


class Signal:
    def __init__(self, name, data, source):
        self.name = name
        self.physics = dict()
        self.physics['type'] = 'electric'
        self.physics['collision'] = False
        self.physics['distance_passed'] = 0
        self.data = data
        self.source = source


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

    def put_r(self, l_port, sig):
        self.r_port_sig[l_port].put(sig)
        return

    def put_s(self, l_port, sig):
        self.s_port_sig[l_port].put(sig)
        return

    def get_r(self, l_port):
        gen = (yield self.r_port_sig[l_port].get())
        print(gen)
        if gen is not None:
            for s in gen:
                print(s)
        return

    def get_s(self, l_port):
        return self.s_port_sig[l_port].get()

    def s_start(self, sig, port: int):
        pass

    def r_start(self, sig, port: int):
        pass

    def s_end(self, sig, port: int):
        print('Not implemented')
        pass

    def r_end(self, sig, port: int):
        print('Not implemented')
        pass


class ActiveDev(Dev):
    def __init__(self, env, name, config):
        Dev.__init__(self, env, name, config)


class Ont(ActiveDev):
    def run(self):
        while True:
            for l_port in self.r_port_sig:
                sig = self.get_r(l_port)
                if sig is not None:
                    self.r_start(sig, l_port)
            yield self.env.timeout(1)

    # def r_start(self, sig, port):
    #     transitted_signals = dict()
    #     matrix_ratios = self.power_matrix[port]
    #     for l_port in range(len(matrix_ratios)):
    #         ratio = matrix_ratios[l_port]
    #         splitted_sig = self.multiply_power(sig, ratio)
    #         splitted_sig.name += ':{}:{}'.format(self.name, l_port)
    #         if splitted_sig.physics['power'] > 0:
    #             r_port, r_dev = self.out[l_port]
    #             r_dev.put_r(r_port, sig)

    def r_start(self, sig, port: int):
        for s in sig:
            print(type(s))
            #print('{} : {} : принимаю {}'.format(self.env.now, self.name, s.name))


class Olt(ActiveDev):
    def run(self):
        while True:
            for l_port in self.out:
                data_to_send = {}
                sig_id = '{}:{}:{}'.format(self.env.now, self.name, self.env.now + 125)
                sig = Signal(sig_id, data_to_send, source=self.name)
                print('сигнал {}'.format(sig_id))
                self.s_start(sig, l_port)
            yield self.env.timeout(125)

    def s_start(self, sig, l_port):
        sig = self.eo_transform(sig)
        r_port, r_dev = self.out[l_port]
        r_dev.put_r(r_port, sig)
        return sig

    def eo_transform(self, sig):
        optic_parameters = {'power': float(self.config['transmitter_power']),
                            'wavelength': float(self.config['transmitter_wavelength'])}
        if sig.physics['type'] == 'electric':
            sig.physics['type'] = 'optic'
        else:
            raise Exception
        sig.physics.update(optic_parameters)
        return sig


class PassiveDev(Dev):
    def __init__(self, env, name, config):
        Dev.__init__(self, env, name, config)


class Splitter(PassiveDev):
    length = 0.000001
    power_matrix = [[0, 0.25, 0.25, 0.25, 0.25],
                         [0.25, 0, 0, 0, 0],
                         [0.25, 0, 0, 0, 0],
                         [0.25, 0, 0, 0, 0],
                         [0.25, 0, 0, 0, 0]]

    def run(self):
        while True:
            for l_port in self.r_port_sig:
                sig = self.get_r(l_port)
                if type(sig) is Signal:
                    self.s_start(sig, l_port)
            yield self.env.timeout(1)

    def multiply_power(self, sig, ratio):
        new_sig = copy.deepcopy(sig)
        new_sig.physics['power'] *= ratio
        new_sig.physics['distance_passed'] += self.length
        return new_sig

    def s_start(self, sig, l_port):
        r_port, r_dev = self.out[l_port]
        r_dev.put_r(r_port, sig)
        return sig

    def r_start(self, sig, port):
        transitted_signals = dict()
        matrix_ratios = self.power_matrix[port]
        for l_port in range(len(matrix_ratios)):
            ratio = matrix_ratios[l_port]
            splitted_sig = self.multiply_power(sig, ratio)
            splitted_sig.name += ':{}:{}'.format(self.name, l_port)
            if splitted_sig.physics['power'] > 0:
                r_port, r_dev = self.out[l_port]
                self.put_s(l_port, sig)


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
    config = Dict({'horizont': 10})
    net = json.load(open('network1.json'))

    env = simpy.Environment()
    NetFabric(net, env)
    env.run(until=config.horizont)

    print('End of simulation... Preparing results.')
    # make_results()


if __name__ == '__main__':
    main()
