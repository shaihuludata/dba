from random import expovariate
import simpy
from examples_and_tries.SimComponents import PacketGenerator, PacketSink
from addict import Dict
import json


class Signal:
    def __init__(self, env, name, data, source, delay):
        self.env = env
        self.name = name
        self.alive = True
        self.physics = dict()
        self.physics['type'] = 'electric'
        self.physics['collision'] = False
        self.physics['distance_passed'] = 0
        self.data = data
        self.delay = delay
        self.source = source
        self.action = env.process(self.run())

    def run(self):
        while self.alive:
            l_dev, l_port = self.source[0], self.source[1]
            r_dev, sig, r_port = l_dev.s_start(self, l_port)
            r_dev.r_start(sig, r_port)
            yield self.env.timeout(self.delay)
            l_dev.s_end(self, l_port)
            r_dev.r_end(sig, r_port)
            self.alive = False


class Dev(object):
    def __init__(self, env, name, config):
        self.config = config
        self.name = name
        # self.rate = config['type']
        self.env = env
        self.out = dict()

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
        self.STATE = 'Offline'
        self.power_matrix = 0
        self.cycle_duration = 125
        self.next_cycle_start = 0
        # словарь порт: принимаемый сигнал. используется для обнаружения коллизий
        self.rec_port_sig = dict()
        for port in config['ports']:
            self.rec_port_sig[int(port)] = list()
        # self.counters = Counters()
        self.action = env.process(self.run())

    def run(self):
        while True:
            yield self.env.timeout(125)

    def s_start(self, sig, l_port):
        sig = self.eo_transform(sig)
        r_port, r_dev = self.out[l_port]
        return r_dev, sig, r_port

    def s_end(self, sig, port: int):
        return self.name, port, sig

    def r_start(self, sig, port):
        print('{} : {} : принимаю {}'.format(self.env.now, self.name, sig.name))
        self.rec_port_sig[port].append(sig)
        rec_sigs = self.rec_port_sig[port]
        num_of_sigs = len(rec_sigs)
        if num_of_sigs > 1:
            print('Time {} {} ИНТЕРФЕРЕНЦИОННАЯ КОЛЛИЗИЯ. Сигналов: {}!!!'
                  .format(self.env.now, self.name, num_of_sigs))
            sn = False
            for i in rec_sigs:
                if 'sn_response' in i.data:
                    sn = True
            if not sn:
                print('плохая коллизия')
                #print(list((sig.name, sig.data['cycle_num']) for sig in rec_sigs))
                print(list(sig.name for sig in rec_sigs))
                # raise Exception('плохая коллизия')

            for i in rec_sigs:
                i.physics['collision'] = True
        return 0

    def r_end(self, sig, port: int):
        rec_sig = self.rec_port_sig[port]
        sig_index = rec_sig.index(sig)
        rec_sig.pop(sig_index)
        self.oe_transform(sig)
        # следующее можно удалить?
        output = {"sig": sig, "delay": self.cycle_duration}
        return {port: output}

    def eo_transform(self, sig):
        optic_parameters = {'power': float(self.config['transmitter_power']),
                            'wavelength': float(self.config['transmitter_wavelength'])}
        assert sig.physics['type'] == 'electric'
        sig.physics['type'] = 'optic'
        sig.physics.update(optic_parameters)
        return sig

    def oe_transform(self, sig):
        optic_parameters = {}
        assert sig.physics['type'] == 'optic'
        sig.physics['type'] = 'electric'
        sig.physics.update(optic_parameters)
        return sig


class Ont(ActiveDev):
    def stub(self):
        pass



class Olt(ActiveDev):
    def run(self):
        while True:
            for l_port in self.out:
                data_to_send = {}
                start = self.env.now
                delay = self.cycle_duration
                end = start + delay
                sig_id = '{}:{}:{}'.format(start, self.name, end)
                sig = Signal(self.env, sig_id, data_to_send, (self, l_port), delay)
            yield self.env.timeout(125)

    def r_end(self, sig, port: int):
        ret = dict()
        # обработка интерференционной коллизии
        # каждый принимаемый сигнал должен быть помечен как коллизирующий
        for r_sig in self.rec_port_sig[port]:
            if r_sig.name == sig.name:
                r_sig_index = self.rec_port_sig[port].index(r_sig)
                self.rec_port_sig[port].pop(r_sig_index)
                # if rec_sig.physics['collision']:
                #     self.counters.ingress_collision += 1
                #     return {}
                break

        self.oe_transform(sig)
        # проверка на содержание ответов на запросы регистрации в сообщении
        # if 'sn_response' in sig.data and self.time < self.sn_request_quiet_interval_end:
        #     s_number = sig.data['sn_response'][0]
        #     allocs = sig.data['sn_response'][1]
        #     self.dba.register_new_ont(s_number, allocs)
        #     self.counters.number_of_ont = len(self.dba.ont_discovered)
        #     if 'sn_ack' not in self.data_to_send:
        #         self.data_to_send['sn_ack'] = list()
        #     self.data_to_send['sn_ack'].extend(allocs)
        #     # output = {"sig": sig, "delay": delay}
        #     return {}
        # нормальный приём сообщения
        if False: pass
        else:
            ont_allocs = list(alloc for alloc in sig.data if 'ONT' in alloc)
            for alloc in ont_allocs:
                for packet in sig.data[alloc]:
                    pass
                    # ret_upd = self.defragmentation(packet)
                    # for t in ret_upd:
                    #     evs = ret_upd[t]
                    #     if t not in ret:
                    #         ret[t] = list()
                    #     ret[t].extend(evs)
                # self.dba.register_packet(alloc, sig.data[alloc])
            return ret

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
            delay = sig.delay
            new_sig = Signal(self.env, sig_id, data_to_send, (self, l_port), delay)
            new_sig.physics['power'] = new_power
            new_sig.physics['distance_passed'] += self.length
            return new_sig
        return False

    def s_start(self, sig, l_port):
        r_port, r_dev = self.out[l_port]
        return r_dev, sig, r_port

    def s_end(self, sig, port):
        return

    def r_start(self, sig, port):
        matrix_ratios = self.power_matrix[port]
        for l_port in range(len(matrix_ratios)):
            ratio = matrix_ratios[l_port]
            splitted_sig = self.multiply_power(sig, ratio, l_port)
            if splitted_sig is not False:
                splitted_sig.name += ':{}:{}'.format(self.name, l_port)
                splitted_sig.source = (self, l_port)
        return self.delay

    def r_end(self, sig, port):
        return

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
