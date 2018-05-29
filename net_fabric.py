import re
from pon.olt import Olt
from pon.ont import Ont
from pon.opaque import Fiber, Splitter
from observer.observer import Observer
from uni_traffic.traffic_components import TrafficGeneratorBuilder, PacketSink
from dba.dba_static import DbaStatic, DbaStaticAllocs
from dba.dba_tm import DbaTM, DbaTrafficMonLinear


class NetFabric:
    classes = {"OLT": Olt, "ONT": Ont, "Splitter": Splitter, "Fiber": Fiber}

    def __init__(self):
        self.env = None
        self.dbg = None
        self.obs = None
        pass

    def net_fabric(self, net, env, sim_config):
        self.env = env
        dbg = sim_config["debug"] if "debug" in sim_config else False
        self.dbg = dbg
        self.obs = obs = Observer(env, sim_config)

        for class_name in ["OLT", "ONT"]:
            new_class = self.make_observable_device_class(obs, class_name)
            self.classes[class_name] = new_class
        obs.start()

        devices = dict()
        connection = dict()
        # Create devices
        for dev_name in net:
            config = net[dev_name]
            for dev_type in self.classes:
                if dev_type in dev_name:
                    constructor = self.classes[dev_type]
                    dev = constructor(env, dev_name, config)
                    connection[dev_name] = config["ports"]

                    if dev_type == "OLT":
                        dba = self.create_dba(dev, config)
                        dev.dba = dba
                    dev = self.create_traffic_entities(dev, dev_name, config)
                    devices[dev_name] = dev
        devices = self.interconnect_devices(devices, connection)
        return devices, obs

    def make_observable_device_class(self, obs, class_name):
        parent_class = self.classes[class_name]

        class ObservableDev(parent_class):
            observe = obs.notice

            @observe
            def r_end(self, sig, port):
                parent_class.r_end(self, sig, port)
        return ObservableDev

    def create_dba(self, dev, config):
        # Configure OLT DBA
        env = self.env
        olt_dba_dict = {"static": DbaStatic, "static_allocs": DbaStaticAllocs,
                        "tm_basic": DbaTM, "tm_linear_traftype_aware": DbaTrafficMonLinear}
        dba_config = dict()
        # self.upstream_interframe_interval = self.config["upstream_interframe_interval"]  # in bytes
        for dba_par in ["cycle_duration", "transmitter_type",
                        "maximum_allocation_start_time", "upstream_interframe_interval"]:
            dba_config[dba_par] = config[dba_par] if dba_par in config else None
        dba = olt_dba_dict[config["dba_type"]](env, dba_config, dev.snd_port_sig[0])
        return dba

    def create_traffic_entities(self, dev, dev_name, config):
        # Create traffic entities
        env = self.env
        dbg = self.dbg
        if re.search("[OL|NT]", dev_name) is not None:
            new_p_sink = self.make_observable_psink_class(self.obs, PacketSink)
            dev.p_sink = new_p_sink(env, debug=dbg)
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
        return dev

    def make_observable_psink_class(self, obs, parent_class):
        class ObservablePSink(parent_class):
            observe = obs.notice

            @observe
            def check_dfg_pkt(self, frg):
                parent_class.check_dfg_pkt(self, frg)
        return ObservablePSink

    def interconnect_devices(self, devices, connection):
        # Interconnect devices
        for dev_name in connection:
            l_dev = devices[dev_name]
            con = connection[dev_name]
            for l_port in con:
                r_dev_name, r_port = con[l_port].split("::")
                r_dev = devices[r_dev_name]
                l_port = int(l_port)
                l_dev.out[l_port] = (int(r_port), r_dev)
        return devices
