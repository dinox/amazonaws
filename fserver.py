from twisted.web import server, resource
from twisted.internet import reactor, threads
from twisted.internet.defer import Deferred
from multiprocessing import Process, Queue

import optparse

def parse_args():
    usage = """usage: %prog [options]"""

    parser = optparse.OptionParser(usage)

    help = "The port to listen on. Default to a random available port."
    parser.add_option('-p', '--port', type='int', help=help)

    options, args = parser.parse_args()

    return options



def f(n):
    d = Deferred()
    def _f(k, n0, nE):
        for i in range(n0,nE+1):
            k *= i
        return k
    if n <= 1000:
        d.addCallback(_f, 1, n)
    else:
        d.addCallback(_f, 1, 1000)
        for i in range(1001, n+1):
            d.addCallback(_f, i, i+1)
    d.callback(1)
    return d

class FacultyResource(resource.Resource):
    isLeaf = True

    def __init__(self, n):
        resource.Resource.__init__(self)
        self.n = n

    def render_GET(self, request):
        request.setHeader("content-type", "text/plain")
        d = Deferred()
        d.addCallback(f)

        def write_reply(msg):
            request.write(str(msg) + "\n")
            request.finish()

        d.addCallback(write_reply)
        d.callback(self.n)

        return server.NOT_DONE_YET

class Faculty(resource.Resource):
    def getChild(self, name, request):
        return FacultyResource(int(name))

options = parse_args()
port = options.port or 8080

reactor.listenTCP(port, server.Site(Faculty()))
reactor.run()
