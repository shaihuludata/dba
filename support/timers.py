
class Timer:
    def __init__(self, env, timeout, func, args, condition="once"):
        self.env = env
        self.timeout = timeout
        self.func = func
        self.args = args
        if condition == "periodic":
            self.run = self.periodic
        elif condition == "once":
            self.run = self.once
        else:
            raise NotImplemented
        self.action = env.process(self.run())

    def periodic(self):
        done = False
        while not done:
            yield self.env.timeout(self.timeout)
            self.func(*self.args)
            done = True

    def once(self):
        done = False
        while not done:
            yield self.env.timeout(self.timeout)
            self.func(*self.args)
            done = True
