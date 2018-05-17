
class Clock:
    def __init__(self, initial_t):
        self.t = initial_t


class Dev:
    def __init__(self, id, c):
        self.out = None
        self.clock = c
        self.id = id

    def send(self, sig, port):
        delay = 5
        print('{} : {} отправляю сигнал: {}'.format(self.clock.t, self.id, sig))
        return delay, self.out[1].recv, sig

    def recv(self, sig, port):
        print('{} : {} принимаю сигнал: {}'.format(self.clock.t, self.id, sig))
        delay = 2
        return delay, self.out[1].send, sig


c = Clock(0)
a = Dev('a', c)
b = Dev('b', c)

a.out = (1, b)
b.out = (1, a)

sig = 'жопа'
schedule = {1: (a.send, sig)}

time_horizont = 20
for t in range(1, time_horizont):
    if t in schedule:
        ev = schedule[t]
        proc = ev[0]
        ret = proc(ev[1], 1)
        schedule[t+ret[0]] = ret[1], ret[2]
    c.t = t
