from pon_device import PonDevice
from support import Counters

class ActiveDevice(PonDevice):
    def __init__(self, name, config):
        PonDevice.__init__(self, name, config)
        self.state = 'Offline'
        self.power_matrix = 0
        self.cycle_duration = 125
        self.next_cycle_start = 0
        self.requests = list()
        self.data_to_send = dict()
        self.device_scheduler = dict()
        # TODO: в следующей версии, предусмотреть вместо списка словарь порт: список сигналов
        # либо в дальнейшем перенести мониторинг коллизий на наблюдателя контрольных точек
        self.receiving_sig = list()
        self.time = 0
        self.counters = Counters()
        self.collision_events = list()

        if "transmitter_type" in self.config:
            trans_type = self.config["transmitter_type"]
            if trans_type == "1G":
                self.transmitter_speed = 1244160000
            elif trans_type == "2G":
                self.transmitter_speed = 2488320000
            else:
                raise Exception('Transmitter type {} not specified'.format(trans_type))
        else:
            raise Exception('Specify transmitter type!')

    def plan_next_act(self, time):
        self.time = time
        pass
        #data = 'nothing to send'
        #return {0: [data]}

    def s_start(self, sig, port: int):
        sig = self.eo_transform(sig)
        return self.name, port, sig

    def s_end(self, sig, port: int):
        return self.name, port, sig

    def r_start(self, sig, port: int):
        self.receiving_sig.append(sig)
        if len(self.receiving_sig) > 1:
            print('{} ИНТЕРФЕРЕНЦИОННАЯ КОЛЛИЗИЯ на порту {}!!!'.format(self.name, port))
            sig.physics['collision'] = True
            for rec_sig in self.receiving_sig:
                rec_sig.physics['collision'] = True
        output = {"sig": sig, "delay": self.cycle_duration}
        return {port: output}

    def r_end(self, sig, port: int):
        self.receiving_sig.remove(sig)
        sig = self.oe_transform(sig)
        output = {"sig": sig, "delay": self.cycle_duration}
        return {port: output}

    def eo_transform(self, sig):
        optic_parameters = {'power': float(self.config['transmitter_power']),
                            'wavelength': float(self.config['transmitter_wavelength'])}
        if sig.physics['type'] == 'electric':
            sig.physics['type'] = 'optic'
        else:
            raise Exception
        sig.physics.update(optic_parameters)
        return sig

    def oe_transform(self, sig):
        optic_parameters = {}
        if sig.physics['type'] == 'optic':
            sig.physics['type'] = 'electric'
        else:
            raise Exception
        sig.physics.update(optic_parameters)
        return sig

