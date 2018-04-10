

class Counters:
    def __init__(self):
        self.ingress_unicast = int()
        self.ingress_collision = int()

    def export_to_console(self):
        for counter in self.__dict__:
            print('{} = {}'.format(counter, self.__dict__[counter]))