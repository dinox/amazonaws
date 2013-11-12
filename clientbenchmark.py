import subprocess, time, optparse, csv

def parse_args():
    usage = """usage: %prog [options]"""

    parser = optparse.OptionParser(usage)

    help = "The output file for the benchmark. Default is bench.dat"
    parser.add_option('-f', '--file', type='string', help=help)

    #help = "Number or requests. Default is 400"
    #parser.add_option('-r', '--req', type='int',help=help)

    help = "Ip of the loadbalancer. Default is 54.200.217.6"
    parser.add_option('-i', '--ip' , type='string', help=help)

    help = "Url send to the webserver. Default is 6000"
    parser.add_option('-u', '--url', type='string', help=help)

    options, args = parser.parse_args()

    return options

def benchmark(c):
    global logfile
    t = float(0)
    ptime = -1
    while ptime < 0:
        time.sleep(1)
        ptime = benchmark_ab(c)
    reqps = 1/ptime * 1000 * c
    print "Benchmark %i:\t%f\t%f" % (c,ptime,reqps)
    f = open(logfile,"a")
    f.write("%i\t%f\t%f\n" % (c,ptime,reqps))
    f.close()

def eval_ab():
    global logfile
    try:
        ptime = 0.0
        count = -1.0
        with open('ab.tmp', 'r') as csvfile:
            spamreader = csv.reader(csvfile, delimiter='\t')
            for row in spamreader:
                if count >= 0:
                    ptime += float(row[3])
                count += 1
    except Exception, e:
        print e
    return ptime/count

def benchmark_ab(c):
    global ip,url
    # create ab params
    reqs = 4*c
    if reqs < 100:
        reqs = 100
    command = "ab -n %i -c %i -g ab.tmp %s:8080/%s" % (reqs,c,ip,url)
    print "Start apache benchmark: " + command
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    process.wait()
    if not process.returncode == 0:
        print "ab failed, retry"
        time.sleep(10)
        return -1
    return eval_ab()

options = parse_args()
logfile = options.file or "bench.dat"
ip = options.ip or "54.200.217.6"
url = options.url or "6000"

f = open(logfile,"w")
f.write("")
f.close()
for c in [10,20,50,100,200]:
    benchmark(c)
