from twisted.application import service
import os, sys, time, atexit

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(SCRIPT_DIR, 'txlb'))

from twisted.internet import reactor
from twisted.internet.protocol import Factory, Protocol, ClientFactory,\
        ServerFactory, DatagramProtocol
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.protocols.basic import NetstringReceiver

from txlb import manager
from txlb.model import HostMapper
from txlb.schedulers import roundr, leastc
from txlb.application.service import LoadBalancedService

typ = roundr

proxyServices = [
  HostMapper(proxy='127.0.0.1:8080', lbType=typ, host='host0',
      address='127.0.0.1:10000'),
  HostMapper(proxy='127.0.0.1:8080', lbType=typ, host='host1',
      address='127.0.0.1:10001'),
  HostMapper(proxy='127.0.0.1:8080', lbType=typ, host='host2',
      address='127.0.0.1:10002'),
  HostMapper(proxy='127.0.0.1:8080', lbType=typ, host='host3',
      address='127.0.0.1:10003'),
  HostMapper(proxy='127.0.0.1:8080', lbType=typ, host='host4',
      address='127.0.0.1:10004'),
  HostMapper(proxy='127.0.0.1:8080', lbType=typ, host='host5',
      address='127.0.0.1:10005'),
  HostMapper(proxy='127.0.0.1:8080', lbType=typ, host='host6',
      address='127.0.0.1:10006'),
  HostMapper(proxy='127.0.0.1:8080', lbType=typ, host='host7',
      address='127.0.0.1:10007'),
  HostMapper(proxy='127.0.0.1:8080', lbType=typ, host='host8',
      address='127.0.0.1:10008'),
  HostMapper(proxy='127.0.0.1:8080', lbType=typ, host='host9',
      address='127.0.0.1:10009'),
]

# overlay commands
class OverlayService(service.Service):

    def __init__(self, tracker):
        self.tracker = tracker
        from twisted.internet.task import LoopingCall
        LoopingCall(self.reccuring).start(3)

    def startService(self):
        service.Service.startService(self)

    def reccuring(self):
        print self.tracker.getStats()

# Overlay Communication
class OverlayService2(object):
    def OK(self, reply):
        pass

    commands = {"ok" : OK }

class ClientProtocol(NetstringReceiver):
    def connectionMade(self):
        self.sendRequest(self.factory.request)

    def sendRequest(self, request):
        self.sendString(json.dumps(request))

    def stringReceived(self, reply):
        self.transport.loseConnection()
        reply = json.loads(reply)
        command = reply["command"]

        if command not in self.factory.service.commands:
            print "Command <%s> does not exist!" % command
            self.transport.loseConnection()
            return

        self.factory.handeReply(command, reply)

class ServerProtocol(NetstringReceiver):
    def stringReceived(self, request):
        command = json.loads(request)["command"]
        data = json.loads(request)

        if command not in self.factory.service.commands:
            print "Command <%s> does not exist!" % command
            self.transport.loseConnection()
            return

        self.commandReceived(command, data)

    def commandReceived(self, command, data):
        reply = self.factory.reply(command, data)

        if reply is not None:
            self.sendString(json.dumps(reply))

        self.transport.loseConnection()

# initialization
class ConnectOverlay(Protocol):
    def sendMessage(self, msg):
        self.transport.write("test %s\n" % msg)

class ConnectOverlayFactory(Factory):
    def buildProtocol(self, addr):
        return ConnectOverlay()

def sendMessage(p):
    p.sendMessage("1")
    reactor.callLater(1, p.transport.loseConnection)


def read_config():
    f = open("load_balancers.txt", "r")
    nodes = []
    for line in f:
        s = line.split(":")
        nodes.append({"ip":s[0],"port":int(s[1].strip())})
    return nodes

def init():
    pass

# cleanup and exit
def before_exit():
    sys.exit(0)

application = service.Application('Demo LB Service')
pm = manager.proxyManagerFactory(proxyServices)
lbs = LoadBalancedService(pm)
print pm.trackers
os = OverlayService(pm.getTracker('proxy1', 'group1'))
os.setServiceParent(application)
lbs.setServiceParent(application)

atexit.register(before_exit)

from twisted.internet import reactor
reactor.run()

