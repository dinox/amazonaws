from twisted.web import server, resource
from twisted.internet import reactor, threads
from multiprocessing import Process, Queue

import optparse

def parse_args():
    usage = """usage: %prog [options]"""

    parser = optparse.OptionParser(usage)

    help = "The port to listen on. Default to a random available port."
    parser.add_option('-p', '--port', type='int', help=help)

    options, args = parser.parse_args()

    return options



def f(n, q):
    k = 1
    for i in range(1,n+1):
        k *= i
    q.put(k)

def MPFib(n):
    q = Queue()
    p = Process(target=f, args=(n,q))
    p.start()
    p.join()
    return q.get()


class FacultyResource(resource.Resource):
    isLeaf = True

    def __init__(self, n):
        resource.Resource.__init__(self)
        self.n = n

    def render_GET(self, request):
        request.setHeader("content-type", "text/plain")
        d = threads.deferToThread(MPFib, self.n)

        def write_reply(msg):
            request.write(str(msg) + "\n")
            request.finish()

        d.addCallback(write_reply)
        return server.NOT_DONE_YET

class Faculty(resource.Resource):
    def getChild(self, name, request):
        return FacultyResource(int(name))

options = parse_args()
port = options.port or 8080

reactor.listenTCP(port, server.Site(Faculty()))
reactor.run()
