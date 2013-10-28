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



class FacultyResource(resource.Resource):
    isLeaf = True

    def __init__(self):
        resource.Resource.__init__(self)

    def render_GET(self, request):
        request.setHeader("content-type", "text/plain")
        return "test\n"

class Faculty(resource.Resource):
    def getChild(self, name, request):
        return FacultyResource()

options = parse_args()
port = options.port or 8080

reactor.listenTCP(port, server.Site(Faculty()))
reactor.run()
