
class Signal:

    def __init__(self, data):
        self.physics = dict()
        self.physics['power'] = 0

        self.data = data

    def emit(self):
        return True
