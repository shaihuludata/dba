
class Signal:

    def __init__(self, data):
        self.physics = dict()
        self.physics['power'] = 0

        self.data = data

    def emit(self):
        return True

    def split(self, ratio):
        self.physics['power'] = self.physics * ratio
        return self
