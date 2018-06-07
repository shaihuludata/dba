from uni_traffic.builders import TrafficGeneratorBuilder
import simpy
from uni_traffic.traffic_components import PacketSink

class PacketSink_traf_counter(PacketSink):
    def __init__(self, env, debug=True):
        PacketSink.__init__(self, env, debug=True)
        self.total_kbits = 0

    def check_dfg_pkt(self, dfg):
        if self.debug:
            print(round(self.env.now, 3), dfg)
            self.total_kbits += 8*dfg.size
            # print(self.total_kbits)


tgb = TrafficGeneratorBuilder(traf_types="./traffic_types.json")
env = simpy.Environment()


flow_id = "test1"
traf_type = "type4"
traffic_activation_time = 0
pg = tgb.packet_source(env, flow_id, traf_type, traffic_activation_time)
#uni = self.tgb.uni_input_for_ont(env, pg, flow_id)

ps = PacketSink_traf_counter(env, debug=True)  # debugging enable for simple output
pg.out = ps

horizon = 1000000
env.run(until=horizon)
print("Итог: {} kbps".format(ps.total_kbits/horizon*1000))
