
class Clock:
    def __init__(self, start):
        self.t = start


class Sched:
    def __init__(self, t: float, objects):
        clock = Clock(t)
        self._clock = clock
        self.t = self._clock.t
        self.devs = list()
        self.attr = dict()

        for o_name in objects:
            o = A(o_name, clock)
            self.devs.append(o)


class A:
    def __init__(self, o_name, clock):
        self.t = float()
        self._clock = clock
        self.t = self._clock.t
        self.name = o_name
        self.attr = dict()

# import examples_and_tries.timing_objects as to
# sc = to.Sched(0, ["a", "b", "c"])


# def main():
#     sc = Sched(0, ["a", "b", "c"])
#     print(sc.t)
#     print()
#
#
# if __name__ == '__main__':
#     main()
