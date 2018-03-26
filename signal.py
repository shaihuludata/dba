
class Signal:

    def __init__(self, id, data):
        self.id = id
        self.physics = dict()
        self.physics['type'] = 'electric'
        self.data = data

