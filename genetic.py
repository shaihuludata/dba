import random
import time
import inspyred
from datetime import datetime
import json
import logging


result_dir = "./result/genetic/"
result_file = result_dir + "genetic_data.json"


def bin_list_to_int(lst):
    """переводит список бинарных элементов в бинарную строку"""
    bin_string = "0b"
    for i in lst:
        bin_string += str(i)
    return int(bin_string, base=0)


def generate_binary(random, args):
    """генерирует список бинарных элементов"""
    bits = args.get('num_bits', 8)
    return [random.choice([0, 1]) for i in range(bits)]


@inspyred.ec.evaluators.evaluator
def evaluate_binary(candidate, args):
    ret = int("".join([str(c) for c in candidate]), 2)
    return ret


@inspyred.ec.evaluators.evaluator
def gene_simulate(candidate, args):
    """запуск симуляции для заданного гена-кандидата
    результат симуляции - значение фитнес-функции"""
    from main import simulate
    kwargs = interpret_gene(candidate)
    try:
        tpi = simulate(**kwargs)
    except:
        print("failed to simulate {}".format(candidate))
        tpi = 100500
    f = open(result_file, "a")
    f.writelines(str(bin_list_to_int(candidate)) + " {}\n".format(tpi))
    f.close()
    return 1/tpi


def rpyc_simulation(candidates, args):
    import multiprocessing

    conds = {bin_list_to_int(c): interpret_gene(c) for c in candidates}

    fitness_results = json.load(open(result_file))
    fitness_dict = {gene_id: fitness_results[gene_id]
                        for gene_id in conds
                            if gene_id in fitness_results}

    conds_str = json.dumps(conds, ensure_ascii=False).encode("utf-8")
    len_of_conds = str(len(conds_str)) + "\n"
    while len(len_of_conds) < 10:
        len_of_conds = "0" + len_of_conds

    import socket
    sock = socket.socket()
    print("Waiting connection")
    connected = False

    while not connected:
        try:
            sock.connect(('localhost', 9090))
            connected = True
        except ConnectionRefusedError as e:
            print(e)
            time.sleep(3)

    print("Server connected. Sending meta-conditions")

    sock.send(len_of_conds.encode("utf-8"))
    del len_of_conds
    sock.send(conds_str)
    data = sock.recv(10)
    print("Server answered: {}".format(data.decode("utf-8")))
    del data

    results_valid = False
    while not results_valid:
        new_fitness_dict_json = sock.recv(1024)
        try:
            new_fitness_dict = json.loads(new_fitness_dict_json.decode("utf-8"))
        except Exception as e:
            print("No valid data from server: ", e)
            time.sleep(5)

    fitness_dict.update(new_fitness_dict)
    sock.close()

    f = open(result_file, "w")
    json.dump(fitness_dict, f)
    f.close()

    fitness = [fitness_dict[bin_list_to_int(gene)] for gene in candidates]
    return fitness


def genetic(mode):
    rand = random.Random()
    rand.seed(int(time.time()))
    ga = inspyred.ec.GA(rand)
    ga.observer = inspyred.ec.observers.stats_observer
    ga.terminator = inspyred.ec.terminators.evaluation_termination
    if mode == "network":
        evaluator = rpyc_simulation
    elif mode == "single":
        evaluator = gene_simulate
    else:
        raise NotImplemented
    final_pop = ga.evolve(evaluator=evaluator,
                          generator=generate_binary,
                          max_evaluations=500,
                          num_elites=1,
                          pop_size=3,
                          num_bits=72)
    final_pop.sort(reverse=True)
    for ind in final_pop:
        print(str(ind))


def interpret_gene(gene: list):
    """интерпрератор гена для симуляции"""
    assert len(gene) == 72

    def divide_list_to_chromosomes(lst, size_of_pieces=8):
        ret = list()
        for i in range(len(lst)//size_of_pieces):
            chromosome = lst[i:i + size_of_pieces]
            ret.append(chromosome)
        return ret

    int_gene = bin_list_to_int(gene)
    chromosomes = divide_list_to_chromosomes(gene)
    dba_min_grant = bin_list_to_int(chromosomes.pop(0))
    multipliers = dict()
    for tr_cl in [0, 1, 2, 3]:
        bw = round(bin_list_to_int(chromosomes.pop(0)) * 10 / 255, 1)
        uti = round(bin_list_to_int(chromosomes.pop(0)) * 10 / 255, 1)
        multipliers[tr_cl] = {"bw": bw, "uti": uti}
    return {'DbaTMLinearFair_fair_multipliers': multipliers,
            "dba_min_grant": dba_min_grant}


if __name__ == "__main__":
    modes = ["single", "network"]
    mode = "network"
    # f = open(result_file, "w")
    # f.writelines("Simulation suite started {}\n".format(datetime.now(tz=None)))
    # f.close()
    genetic(mode)
    # dba_fair_multipliers = {0: {"bw": 1.0, "uti": 2},
    #                         1: {"bw": 0.9, "uti": 3},
    #                         2: {"bw": 0.8, "uti": 4},
    #                         3: {"bw": 0.7, "uti": 5}}
    # kwargs = {'DbaTMLinearFair_fair_multipliers': dba_fair_multipliers,
    #           'dba_min_grant': 1}
    # main(**kwargs)
