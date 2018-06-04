import json

a = json.load(open("../observer/net_performance.json"))
b = a["Parameters"]

params = dict()
for tr_class in range(0, 5):
    for par in ["IPTD", "IPDV", "IPLR"]:
        par_value = b[par][tr_class]
        if par == "IPTD":
            par_result = float(par_value.split("+")[0])
        elif par == "IPDV":
            par_result = float(par_value) if par_value != "U" else 0
        elif par == "IPLR":
            par_result = float(par_value) if par_value != "U" else 0
        else:
            raise NotImplemented
        params[par] = par_result
    print(tr_class, params)

