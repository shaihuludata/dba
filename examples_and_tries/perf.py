import json
import math

a = json.load(open("../observer/net_performance.json"))
b = a["Parameters"]

measure = {0: {'IPDV': 1.5, 'IPTD': 1.0, 'IPLR': 1e-05},
           1: {'IPDV': 2, 'IPTD': 1.0, 'IPLR': 1e-05},
           2: {'IPDV': 0, 'IPTD': 1.0, 'IPLR': 2e-05},
           3: {'IPDV': 0, 'IPTD': 5.0, 'IPLR': 1e-05},
           4: {'IPDV': 0, 'IPTD': 10.0, 'IPLR': 2e-05}}

norm = dict()
for tr_class in range(0, 5):
    par_result = {}
    norm[tr_class] = par_result
    for par in ["IPTD", "IPDV", "IPLR"]:
        par_value = b[par][tr_class]
        if par == "IPTD":
            par_result = float(par_value.split("+")[0])
        elif par == "IPDV":
            par_result = float(par_value) if par_value != "U" else float("Inf")
        elif par == "IPLR":
            par_result = float(par_value) if par_value != "U" else float("Inf")
        else:
            raise NotImplemented
        norm[tr_class][par] = par_result

print(norm)
print(measure)
evaluations = list()
for tr_class in [0, 1, 2, 3, 4]:
    cl_norm = norm[tr_class]
    cl_measure = measure[tr_class]
    cl_evaluations = list()
    for par in cl_measure:
        measure_val = cl_measure[par]
        if par in cl_norm:
            normative = cl_norm[par]
            evaluation = (measure_val) / normative
            if measure_val > normative:
                evaluation *= 10
            if math.isnan(evaluation):
                evaluation = 0
            cl_evaluations.append(round(evaluation, 2))
    evaluations.append(cl_evaluations)
print(evaluations)
sum_evaluations = list(round(sum(evs), 2) for evs in evaluations)
print(sum_evaluations)

