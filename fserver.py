from twisted.web import server, resource
from twisted.internet import reactor, threads
from multiprocessing import Process, Queue

def f(n, q):
    k = 1
    for i in range(1,n+1):
        k *= i
    q.put(k % 100003)

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

reactor.listenTCP(8080, server.Site(Faculty()))
reactor.run()
