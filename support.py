

class Counters:
    def __init__(self):
        self.ingress_unicast = int()
        self.ingress_collision = int()
        self.cycle_number = int()

    def export_to_console(self):
        print(self.__dict__)#'{}'.format(self.__dict__))
        # for counter in self.__dict__:
        #     if counter is not None:
        #         print('{} = {}'.format(counter, self.__dict__[counter]))
