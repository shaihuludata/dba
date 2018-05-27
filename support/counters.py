
class Counters:
    def __init__(self):
        self.ingress_unicast = int()
        self.ingress_collision = int()
        self.cycle_number = int()
        self.number_of_ont = int()

    def export_to_console(self):
        return self.__dict__
