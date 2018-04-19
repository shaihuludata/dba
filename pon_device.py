

class PonDevice:

    def __init__(self, name, config):
        self.name = name
        self.config = config

    def s_start(self, sig, port: int):
        pass

    def r_start(self, sig, port: int):
        pass

    def s_end(self, sig, port: int):
        print('Not implemented')
        pass

    def r_end(self, sig, port: int):
        print('Not implemented')
        pass


