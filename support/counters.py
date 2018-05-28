
class Counters:
    def __init__(self):
        self.ingress_unicast = int()
        self.ingress_collision = int()
        self.cycle_number = int()
        self.number_of_ont = int()

    def export_to_console(self):
        return self.__dict__


class PacketCounters:
    def __init__(self):
        self.packets_sent = int()
        self.packets_rec = int()
        self.fragments_rec = int()
        self.packets_drop = int()

    def export_to_console(self):
        return self.__dict__
