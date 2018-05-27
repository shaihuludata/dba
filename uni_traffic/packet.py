
class Packet(object):
    """ A very simple class that represents a packet.
        This packet will run through a queue at a switch output port.
        We use a float to represent the size of the packet in bytes so that
        we can compare to ideal M/M/1 queues.

        Parameters
        ----------
        time : float
            the time the packet arrives at the output queue.
        size : float
            the size of the packet in bytes
        id : int
            an identifier for the packet
        src, dst : int
            identifiers for source and destination
        flow_id : int
            small integer that can be used to identify a flow
    """
    def __init__(self, s_time, size, id: str, src="a", dst="z", flow_id=0, cos_class=0, packet_num=0):
        # "interval": self.send_interval,
        self.s_time = s_time
        self.e_time = 0
        self.size = size
        self.t_size = size
        self.f_offset = 0
        self.num = packet_num
        self.id = id
        self.src = src
        self.dst = dst
        self.cos = cos_class
        self.flow_id = flow_id

    def __repr__(self):
        return "id: {}, src: {}, time: {}, size: {}, t_size {}, f_offset: {},".\
            format(self.id, self.src, self.s_time, self.size, self.t_size, self.f_offset)

    def make_args_for_defragment(self):
        args = [self.s_time, self.t_size, self.id, self.src, self.dst, self.flow_id, self.cos, self.num]
        return args
