import halp
import queue

class DBA_scheduller:
    def __init__(self, net_filename):
        print('')
    def make_bwmap(self):
        bwmap = 'bwmap_structure'
        return bwmap

class OLT:
    def __init__(self):
        print('New OLT')

class ONT:
    def __init__(self, type, id):
        self.id = id
        print('New ONT')
    def send(self, data):
        header = 'current header'
        rdata = header + data
        return rdata
    def request_BW(self):
        print('Sending req')