import subprocess, time, optparse

repetitions = 1

def parse_args():
    usage = """usage: %prog [options]"""

    parser = optparse.OptionParser(usage)

    help = "The output file for the benchmark. Default is bench.dat"
    parser.add_option('-f', '--file', type='string', help=help)

    help = "Number or requests. Default is 400"
    parser.add_option('-r', '--req', type='int',help=help)

    options, args = parser.parse_args()

    return options

def benchmark(c):
    global repetitions, number_of_requests, logfile
    t = float(0)
    i = 0
    while i < repetitions:
        time.sleep(1)
        tmp = benchmark_ab(c)
        if (tmp > 0):
            t += tmp
            i += 1
    print "Total %i:\t%f" % (c,t)
    t = t / float(repetitions)
    t = t / float(number_of_requests)
    print "Benchmark %i:\t%f" % (c,t)
    f = open(logfile,"a")
    f.write("%i\t%f\n" % (c,t))
    f.close()

def benchmark_ab(c):
    global number_of_requests
    command = "ab -n %i -c %i -q 54.201.11.70:8080/6000" % (number_of_requests,c)
    print command
    start = time.time()
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    process.wait()
    end = time.time()
    if not process.returncode == 0:
        print "ab failed, retry"
        time.sleep(10)
        return -1
    return end - start

options = parse_args()
logfile = options.file or "bench.dat"
number_of_requests = options.req or 400
for c in [10,20,50,100,200]:
    benchmark(c)
