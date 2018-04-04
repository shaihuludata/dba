# from pon_device import PonDevice
# from collections import OrderedDict
from signal import Signal
# import random
from active_optics import Ont

class test_Ont(Ont):

    def plan_next_act(self, time):
        #эту часть надо поместить в тестирование
        if "time_start" in self.config and "time_end" in self.config:
            time_start = int(self.config["time_start"])
            time_end = int(self.config["time_end"])
            data = 'bugaga'
            sig = Signal('{}:{}:{}'.format(time, self.name, time_start), data)
            if time_start in self.device_scheduler:
                return {}
            else:
                self.device_scheduler[time_start] = sig.id
                return {time_start: [{"dev": self, "state": "s_start", "sig": sig, "port": 0}],
                        time_end: [{"dev": self, "state": "s_end", "sig": sig, "port": 0}]
                        }
        else:
            print('Тестовое время старта не установлено')

