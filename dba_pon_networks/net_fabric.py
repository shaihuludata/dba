import re
from pon.olt import Olt
from pon.ont import Ont
from pon.opaque import Fiber, Splitter
from observer.observer import Observer
from uni_traffic.traffic_components import PacketSink, UniPort
from uni_traffic.builders import TrafficGeneratorBuilder
from dba.dba_static import DbaStatic, DbaStaticAllocs
from dba.dba_tm import DbaTM, DbaTrafficMonLinear, DbaTMLinearFair
import logging


class NetFabric:
    classes = {"OLT": Olt, "ONT": Ont, "Splitter": Splitter, "Fiber": Fiber}

    def __init__(self):
        self.env = None
        self.dbg = None
        self.obs = None
        self.tgb = TrafficGeneratorBuilder()

    def net_fabric(self, net, env, sim_config):
        max_bw = self.bandwidth_prognosis(net)
        logging.info("Максимальная прогнозная нагрузка {} Мбит/с".format(max_bw))

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
        obs.devices = devices
        return devices, obs

    def bandwidth_prognosis(self, net):
        max_bw_prognosis = float()
        allocs = list()
        bws = list()
        for dev in net:
            if 'ONT' in dev:
                allocs.extend(net[dev]["Alloc"].values())
        # typs = json.load(open('./uni_traffic/traffic_types.json'))
        typs = self.tgb.traf_configs
        for typ_name in allocs:
            typ = typs["traffic"][typ_name]
            bw = round(8 * 1 * typ["size_of_packet"] / typ["send_interval"], 3)
            bws.append(bw)
        max_bw_prognosis = round(sum(bws), 3)
        return max_bw_prognosis

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
                        "tm_basic": DbaTM, "tm_linear_traftype_aware": DbaTrafficMonLinear,
                        "tm_fair": DbaTMLinearFair}
        dba_config = dict()
        # self.upstream_interframe_interval = self.config["upstream_interframe_interval"]  # in bytes
        for dba_par in ["cycle_duration", "transmitter_type",
                        "maximum_allocation_start_time", "upstream_interframe_interval"]:
            dba_config[dba_par] = config[dba_par] if dba_par in config else None
        dba_type_name = config["dba_type"]
        dba_type = olt_dba_dict[dba_type_name]
        if "dba_min_grant" in config and "tm_" in dba_type_name:
            dba_type.min_grant = config["dba_min_grant"]
        if "DbaTMLinearFair_fair_multipliers" in config and dba_type_name == "tm_fair":
            DbaTMLinearFair.fair_multipliers = config["DbaTMLinearFair_fair_multipliers"]
        dba = dba_type(env, dba_config, dev.snd_port_sig[0])
        return dba

    def create_traffic_entities(self, dev, dev_name, config):
        # Create traffic entities
        env = self.env
        dbg = self.dbg
        if re.search("[OL|NT]", dev_name) is not None:
            new_p_sink_class = self.make_observable_psink_class(self.obs, PacketSink)
            dev.p_sink = new_p_sink_class(env, debug=dbg)
        if re.search("ONT", dev_name) is not None:
            traffic_activation_time = 1000*config["traffic_activation_time"]
            if "Alloc" in config:
                for alloc_num in config["Alloc"]:
                    traf_type = config["Alloc"][alloc_num]
                    flow_id = dev.name + "_" + alloc_num
                    pg = self.tgb.packet_source(env, flow_id, traf_type, traffic_activation_time)
                    new_uni_class = self.make_observable_uni_port(self.obs, UniPort)
                    uni = self.tgb.uni_input_for_ont(env, pg.service, new_uni_class, flow_id)
                    pg.out = uni
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

    def make_observable_uni_port(self, obs, parent_class):
        class ObservableUniPort(parent_class):
            observe = obs.notice

            @observe
            def put(self, pkt):
                parent_class.put(self, pkt)
        return ObservableUniPort

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
