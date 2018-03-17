import queue


class Olt:
    def __init__(self, olt_desc):
        print('New OLT')

    def make_bwmap(self):
        bwmap = 'bwmap_structure'
        return bwmap


class Ont:
    def __init__(self, type, id):
        self.id = id
        print('New ONT')

    def send(self, data):
        header = 'current header'
        rdata = header + data
        return rdata

    def request_bw(self):
        print('Sending req')


