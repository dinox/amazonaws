import subprocess, time, optparse, csv, collections

def parse_args():
    usage = """usage: %prog [options]"""

    parser = optparse.OptionParser(usage)

    help = "The output file for the benchmark. Default is out.dat"
    parser.add_option('-o', '--out', type='string', help=help)

    help = "The input file for the benchmark. Default is in.dat"
    parser.add_option('-i', '--inputfile', type='string', help=help)

    options, args = parser.parse_args()

    return options

def process():
    global inputfile, outfile
    try:
        print inputfile
        print outfile
        dat = dict()
        f = open(outfile, "w")
        mintime = 99999999999
        count = 0
        with open(inputfile, 'r') as csvfile:
            spamreader = csv.reader(csvfile, delimiter='\t')
            for row in spamreader:
                if count > 0:
                    if row[1] in dat:
                        dat[row[1]] = str((float(dat[row[1]])+float(row[4]))/2)
                    else:
                        dat[row[1]] = row[4]
                    if mintime > float(row[1]):
                        mintime = float(row[1])
                count += 1
        od = collections.OrderedDict(sorted(dat.items()))
        for k, v in od.iteritems():
            t = float(k)-mintime
            f.write(str(t)+"\t"+v+"\n")
    except Exception, e:
        print e


options = parse_args()
inputfile = options.inputfile or "in.dat"
outfile = options.out or "out.dat"

process()
