import random
import time
import inspyred
import json
from support.profiling import timeit
import os
import subprocess
from memory_profiler import profile as mprofile
import logging
from mpi4py import MPI


if not os.path.isdir("./result"):
    os.mkdir("./result")

result_dir = "./result/genetic/"
result_file = result_dir + "genetic_data.json"
GENE_SRV_PORT = 9092


def retrieve_result():
    if not os.path.exists(result_dir):
        print("Creating directory for genetic_results")
        os.mkdir(result_dir)

    if not os.path.isfile(result_file):
        f = open(result_file, "w")
        f.write('{}')
        f.close()

    f = open(result_file)
    fitness_results = json.load(f)
    f.close()
    return fitness_results


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
# @mprofile
def gene_simulate(candidate, args):
    """запуск симуляции для заданного гена-кандидата
    результат симуляции - значение фитнес-функции"""
    kwargs = interpret_gene(candidate)
    jargs = json.dumps(kwargs)
    # process = subprocess.Popen(["python3", "main.py", jargs], stdout=subprocess.PIPE)
    # stdout, stderr = process.communicate()
    # env, sim_config = create_simulation()
    # tpi = simulate(env, sim_config, jargs)
    try:
        process = subprocess.Popen(["python3", "main.py", jargs], stdout=subprocess.PIPE)
        data = process.communicate(timeout=60)
        logging.info("GENE: ", data)
        stdout, stderr = data
        tpistr = str(stdout)
        tpistr = str(tpistr.split("___")[1])
        tpi = float(tpistr.split("=")[1])
    except:
        logging.critical("failed to simulate {}".format(candidate))
        tpi = float('Inf')  # 100500

    if not os.path.isdir(result_dir):
        os.mkdir(result_dir)
        print("Creating directory for genetic_results")
    # if os.path.isfile(result_file):
    #     f = open(result_file, "a")
    # else:
    #     f = open(result_file, "w")
    # f.writelines(str(bin_list_to_int(candidate)) + " {}\n".format(tpi))
    # f.close()

    fitness_dict = retrieve_result()
    f = open(result_file, "w")  # именно w!
    fitness_dict.update({bin_list_to_int(candidate): tpi})
    json.dump(fitness_dict, f)
    f.close()
    return tpi


@timeit
# @mprofile
def rpyc_simulation(candidates, args):
    fitness_results = retrieve_result()
    conds = {bin_list_to_int(c): interpret_gene(c) for c in candidates}
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
            sock.connect(('localhost', GENE_SRV_PORT))
            connected = True
        except ConnectionRefusedError as e:
            print(e)
            time.sleep(3)
    logging.info("GENE: Server connected. Sending meta-conditions")

    sock.send(len_of_conds.encode("utf-8"))
    # bytes_sent = 0
    # while len(len_of_conds) < bytes_sent:
    #     bytes_sent = sock.send(len_of_conds.encode("utf-8"), socket.MSG_DONTWAIT)
    #     time.sleep(1)
    # del len_of_conds

    sock.send(conds_str)
    data = sock.recv(10)
    print("Server answered: {}".format(data.decode("utf-8")))
    # del data

    results_valid = False
    while not results_valid:
        data = sock.recv(10)
        print("Получены данные {}".format(data))
        if not data:
            time.sleep(5)
            continue
        size_of_result = int(data.decode())
        data = sock.recv(size_of_result)
        print("Получены результаты {}".format(data))
        try:
            new_fitness_dict = json.loads(data.decode("utf-8"))
            fitness_dict.update(new_fitness_dict)
        except Exception as e:
            print("No valid data from server: ", e)
            time.sleep(5)
        # проверить, что все гены из conds есть в словаре результатов
        conds_keys = [i for i in conds]
        conds_keys.sort()
        fitness_keys = [int(i) for i in fitness_dict]
        fitness_keys.sort()
        if conds_keys == fitness_keys:
            results_valid = True
        else:
            print("ДАННЫЕ НЕ ВАЛИДНЫ!")
            print(conds_keys)
            print(fitness_keys)
    sock.close()

    f = open(result_file, "w")  # именно w!
    fitness_dict.update(fitness_results)
    json.dump(fitness_dict, f)
    f.close()

    # для всех генов из списка кандидатов
    # фитнес-функция в виде списка соответствует генам кандидатов
    fitness = [fitness_dict[str(bin_list_to_int(gene))] for gene in candidates]
    return fitness


def subprocess_mpi_mapper(args):
    candidate, args = args[0], args[1]
    jargs = json.dumps(args)
    try:
        process = subprocess.Popen(["python3", "main.py", jargs], stdout=subprocess.PIPE)
        # new_fitness_dict = json.loads(data.decode("utf-8"))
        data = process.communicate(timeout=60)
        logging.info("GENE: ", data)
        stdout, stderr = data
        tpistr = str(stdout)
        tpistr = str(tpistr.split("___")[1])
        tpi = float(tpistr.split("=")[1])
    except:
        logging.critical("failed to simulate {}".format(candidate))
        tpi = float('Inf')  # 100500
    return candidate, tpi


# @mprofile
def mpi_simulate(candidates, args):
    time.sleep(1)
    for i in candidates: print(i)

    from mpi4py.futures import MPIPoolExecutor

    fitness_results = retrieve_result()
    conds = {bin_list_to_int(c): interpret_gene(c) for c in candidates}
    # старые результаты симуляции могут содержать текущий ген. его можно восстановить
    fitness_dict = {gene_id: fitness_results[gene_id]
                    for gene_id in conds
                    if gene_id in fitness_results}

    results_valid = False

    print(len(candidates))
    while not results_valid:
        with MPIPoolExecutor() as executor:
            new_fitness = executor.map(subprocess_mpi_mapper, conds.items())

        new_fitness_dict = {fit[0]: fit[1] for fit in new_fitness}
        fitness_dict.update(new_fitness_dict)
        # проверить, что все гены из conds есть в словаре результатов
        conds_keys = [i for i in conds]; conds_keys.sort()
        fitness_keys = [int(i) for i in fitness_dict]; fitness_keys.sort()
        if conds_keys == fitness_keys:
            print("ДАННЫЕ ВАЛИДНЫ!")
            results_valid = True
        else:
            print("ДАННЫЕ НЕ ВАЛИДНЫ!")

    if not os.path.isdir(result_dir):
        os.mkdir(result_dir)
        print("Creating directory for genetic_results")

    f = open(result_file, "w")  # именно w!
    fitness_dict.update(fitness_results)
    json.dump(fitness_dict, f)
    f.close()

    fitness = list()
    for gene in candidates:
        gene = bin_list_to_int(gene)
        fitness.append(fitness_dict[gene])
    return fitness


@timeit
def genetic(evalr):
    rand = random.Random()
    rand.seed(int(time.time()))
    ga = inspyred.ec.GA(rand)
    ga.observer = inspyred.ec.observers.stats_observer
    ga.terminator = inspyred.ec.terminators.evaluation_termination
    final_pop = ga.evolve(evaluator=evalr,
                          generator=generate_binary,
                          max_evaluations=50,
                          num_elites=1,
                          pop_size=5,
                          maximize=False,
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
    modes = {"network": rpyc_simulation, "single": gene_simulate, "mpi": mpi_simulate}
    mode = "mpi"
    evaluator = modes[mode]
    # f = open(result_file, "w")
    # f.writelines("Simulation suite started {}\n".format(datetime.now(tz=None)))
    # f.close()

    if mode == "mpi":
        comm = MPI.COMM_WORLD
        rank = comm.Get_rank()
        if rank == 0:
            print(rank, "выполняю")
            genetic(evaluator)
        else:
            print(rank, "готов к работе")
    elif mode in ["network", "single"]:
        genetic(evaluator)
    else:
        raise Exception("Режим не определён")
