
class Signal:

    def __init__(self, id, data, source):
        self.id = id
        self.physics = dict()
        self.physics['type'] = 'electric'
        self.physics['collision'] = False
        self.data = data
        self.name = source

    def export(self):
        # sig = dict()
        # sig['name'] = self.id
        # sig['physics'] = self.physics
        # sig['data']
        return self.__dict__