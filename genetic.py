import random
import time
import inspyred
from main import simulate
from datetime import datetime


result_dir = "./result/genetic/"
result_file = result_dir + "genetic_data"


def bin_list_to_int(lst):
    bin_string = "0b"
    for i in lst:
        bin_string += str(i)
    return int(bin_string, base=0)


def generate_binary(random, args):
    bits = args.get('num_bits', 8)
    return [random.choice([0, 1]) for i in range(bits)]


@inspyred.ec.evaluators.evaluator
def evaluate_binary(candidate, args):
    ret = int("".join([str(c) for c in candidate]), 2)
    return ret


@inspyred.ec.evaluators.evaluator
def gene_simulate(candidate, args):
    kwargs = interpret_gene(candidate)
    tpi = simulate(**kwargs)
    f = open(result_file, "a")
    f.writelines(str(bin_list_to_int(candidate)) + " {}\n".format(tpi))
    f.close()
    return 1/tpi


def genetic():
    rand = random.Random()
    rand.seed(int(time.time()))
    ga = inspyred.ec.GA(rand)
    ga.observer = inspyred.ec.observers.stats_observer
    ga.terminator = inspyred.ec.terminators.evaluation_termination
    final_pop = ga.evolve(evaluator=gene_simulate,
                          generator=generate_binary,
                          max_evaluations=500,
                          num_elites=3,
                          pop_size=10,
                          num_bits=72)
    final_pop.sort(reverse=True)
    for ind in final_pop:
        print(str(ind))


def interpret_gene(gene: list):
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
    for tr_cl in [0,1,2,3]:
        bw = round(bin_list_to_int(chromosomes.pop(0)) * 10 / 255, 1)
        uti = round(bin_list_to_int(chromosomes.pop(0)) * 10 / 255, 1)
        multipliers[tr_cl] = {"bw": bw, "uti": uti}
    return {'DbaTMLinearFair_fair_multipliers': multipliers,
            "dba_min_grant": dba_min_grant}


if __name__ == "__main__":
    f = open(result_file, "w")
    f.writelines("Simulation suite started {}\n".format(datetime.now(tz=None)))
    f.close()
    genetic()
    # dba_fair_multipliers = {0: {"bw": 1.0, "uti": 2},
    #                         1: {"bw": 0.9, "uti": 3},
    #                         2: {"bw": 0.8, "uti": 4},
    #                         3: {"bw": 0.7, "uti": 5}}
    # kwargs = {'DbaTMLinearFair_fair_multipliers': dba_fair_multipliers,
    #           'dba_min_grant': 1}
    # main(**kwargs)
