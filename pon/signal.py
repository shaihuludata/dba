
class Signal:
    def __init__(self, env, name, data: dict,
                 source, source_port, delay,
                 sig_physics=None):
        self.env = env
        self.name = name
        self.alive = True
        self.physics = dict()
        self.physics["type"] = "electric"
        self.physics["collision"] = False
        self.physics["distance_passed"] = 0
        assert type(data) is dict
        self.data = data
        self.delay = delay
        self.source = source
        self.source_port = source_port
        self.action = env.process(self.run())
        if sig_physics is not None:
            self.physics.update(sig_physics)

    def run(self):
        while self.alive:
            l_dev, l_port = self.source, self.source_port
            r_dev, sig, r_port = l_dev.s_start(self, l_port)
            assert self is sig
            r_dev.r_start(self, r_port)
            yield self.env.timeout(self.delay - 1e-14)
            l_dev.s_end(self, l_port)
            r_dev.r_end(self, r_port)
            self.alive = False
