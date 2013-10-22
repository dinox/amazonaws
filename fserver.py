from twisted.web import server, resource
from twisted.internet import reactor

def f(n):
    k = 1
    for i in range(1,n+1):
        k *= i
    return k


class FacultyResource(resource.Resource):
    isLeaf = True

    def __init__(self, n):
        resource.Resource.__init__(self)
        self.n = n

    def render_GET(self, request):
        request.setHeader("content-type", "text/plain")
        return str(f(self.n) % 100003) + "\n"

class Faculty(resource.Resource):
    def getChild(self, name, request):
        return FacultyResource(int(name))

reactor.listenTCP(8080, server.Site(Faculty()))
reactor.run()
