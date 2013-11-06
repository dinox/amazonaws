import subprocess, time

repetitions = 3
number_of_requests = 250

def benchmark(c):
    global repetitions, number_of_requests
    t = float(0)
    i = 0
    while i < repetitions:
        tmp = benchmark_ab(c)
        if (tmp > 0):
            t += tmp
            i += 1
    print "Total %i:\t%f" % (c,t)
    t = t / float(repetitions)
    t = t / float(number_of_requests)
    print "Benchmark %i:\t%f" % (c,t)

def benchmark_ab(c):
    global number_of_requests
    command = "ab -n %i -c %i -q localhost:8080/3000" % (number_of_requests,c)
    start = time.time()
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    process.wait()
    end = time.time()
    if not process.returncode == 0:
        print "ab failed, retry"
        return -1
    return end - start

for c in [1,10,20,50,100,250]:
    benchmark(c)
