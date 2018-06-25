import json


new_config_name = "network9.json"
example_config = "network8.json"

number_of_ont = 32
ex_net = json.load(open(example_config))
new_net = dict()

OLT_name = "OLT0"
OLT = ex_net[OLT_name]

oltFiber_name = "Fiber0"
oltFiber = ex_net[oltFiber_name]

ont_dict = dict()
fiber_dict = dict()
ex_ont = ex_net["ONT1"]
ex_fiber = ex_net["Fiber1"]

Splitter_name = "Splitter1"
Splitter = ex_Splitter = ex_net[Splitter_name]
for ont_num in range(1, number_of_ont+1):
    ONTname = "ONT{}".format(ont_num)
    ontFiber_name = "Fiber{}".format(ont_num)

    if ONTname in ex_net:
        ONT = ex_net[ONTname]
    else:
        ONT = dict()
        ONT.update(ex_ont)
    ONT["ports"]["0"] = "Fiber{}::0".format(ont_num)

    if ontFiber_name in ex_net:
        ontFiber = ex_net[ontFiber_name]
    else:
        ontFiber = dict()
        ontFiber.update(ex_fiber)
    ontFiber["ports"] = {"1": "Splitter1::{}".format(ont_num), "0": "ONT{}::0".format(ont_num)}

    ont_dict[ONTname] = ONT
    fiber_dict[ontFiber_name] = ontFiber

    Splitter["ports"][str(ont_num)] = "Fiber{}::1".format(ont_num)

Splitter["type"] = "1:{}".format(number_of_ont)
new_net.update({OLT_name: OLT, oltFiber_name: oltFiber, Splitter_name: Splitter})
new_net.update(ont_dict)
new_net.update(fiber_dict)
for dev in new_net:
    print(dev, new_net[dev])

f = open(new_config_name, "w")
ex_net = json.dump(new_net, f)
f.close()
