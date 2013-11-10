import subprocess, time

repetitions = 1
number_of_requests = 400

def benchmark(c):
    global repetitions, number_of_requests
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
    f = open("bench.dat","a")
    f.write("%i\t%f\n" % (c,t))
    f.close()

def benchmark_ab(c):
    global number_of_requests
    command = "ab -n %i -c %i -q 54.200.217.6:8080/6000" % (number_of_requests,c)
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

for c in [10,20,50,100,200]:
    benchmark(c)
