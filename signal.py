
class Signal:

    def __init__(self, data):
        self.physics = dict()
        self.physics['type'] = 'electric'
        self.data = data

    def eo_transform(self, optic_parameters):
        if self.physics['type'] == 'electric':
            self.physics['type'] = 'optic'
        else:
            raise Exception
        self.physics.update(optic_parameters)

    def oe_transform(self, optic_parameters):
        if self.physics['type'] == 'optic':
            self.physics['type'] = 'electric'
        else:
            raise Exception
        self.physics.update(optic_parameters)