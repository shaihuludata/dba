

class Sched:
    def __init__(self, time: float):
        self.time = time
        self.devs = list()
        self.attr = dict()
        self.attr['time'] = 0

    def init_devices(self, objects):
        for o_name in objects:
            o = a(o_name)
            o.time = self.time
            o.attr = self.attr
            self.devs.append(o)


class a:
    def __init__(self, o_name):
        self.time = float()
        self.name = o_name
        self.attr = dict()

