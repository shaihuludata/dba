import re
from pon.olt import Olt
from pon.ont import Ont
from pon.opaque import Fiber, Splitter
from observer.observer import Observer
from uni_traffic.traffic_components import TrafficGeneratorBuilder, PacketSink
from dba.dba_static import DbaStatic, DbaStaticAllocs
from dba.dba_tm import DbaTM, DbaTrafficMonLinear


def net_fabric(net, env, sim_config):
    obs = Observer(sim_config)
    dbg = sim_config["debug"] if "debug" in sim_config else False
    classes = {"OLT": Olt, "ONT": Ont, "Splitter": Splitter, "Fiber": Fiber}
    olt_dba_dict = {"static": DbaStatic, "static_allocs": DbaStaticAllocs,
                    "tm_basic": DbaTM, "tm_linear_traftype_aware": DbaTrafficMonLinear}

    for class_name in ["OLT", "ONT"]:
        classes[class_name].observe = obs.notice
    obs.start()

    devices = dict()
    connection = dict()
    # Create devices
    for dev_name in net:
        config = net[dev_name]
        for dev_type in classes:
            if dev_type in dev_name:
                constructor = classes[dev_type]
                dev = constructor(env, dev_name, config)
                connection[dev_name] = config["ports"]
                # Configure OLT DBA
                if dev_type == "OLT":
                    dba_config = dict()
                    # self.upstream_interframe_interval = self.config["upstream_interframe_interval"]  # 10 # in bytes
                    for dba_par in ["cycle_duration", "transmitter_type",
                                    "maximum_allocation_start_time", "upstream_interframe_interval"]:
                        dba_config[dba_par] = config[dba_par] if dba_par in config else None
                    dba = olt_dba_dict[config["dba_type"]](env, dba_config, dev.snd_port_sig[0])
                    dev.dba = dba
                # Create traffic entities
                if re.search("[OL|NT]", dev_name) is not None:
                    dev.p_sink = PacketSink(env, debug=dbg)
                if re.search("ONT", dev_name) is not None:
                    tgb = TrafficGeneratorBuilder()
                    if "Alloc" in config:
                        for alloc_num in config["Alloc"]:
                            traf_type = config["Alloc"][alloc_num]
                            flow_id = dev.name + "_" + alloc_num
                            pg = tgb.packet_source(env, flow_id, traf_type)
                            uni = tgb.uni_input_for_ont(env, pg, flow_id)
                            dev.traffic_generators[flow_id] = uni
                            dev.current_allocations[flow_id] = uni.traf_class
                    if "0" not in config["Alloc"]:
                        alloc_type = "type0"
                devices[dev_name] = dev

    # Interconnect devices
    for dev_name in connection:
        l_dev = devices[dev_name]
        con = connection[dev_name]
        for l_port in con:
            r_dev_name, r_port = con[l_port].split("::")
            r_dev = devices[r_dev_name]
            l_port = int(l_port)
            l_dev.out[l_port] = (int(r_port), r_dev)
    return devices, obs
