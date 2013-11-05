from twisted.application import service
import os, sys, time, atexit, json, traceback
from twisted.internet.task import LoopingCall

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(SCRIPT_DIR, 'txlb'))

from twisted.internet import defer, reactor
from twisted.internet.defer import Deferred
from twisted.internet.protocol import Factory, Protocol, ClientFactory,\
        ServerFactory, DatagramProtocol
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.protocols.basic import NetstringReceiver
from twisted.python import log

from txlb import manager, config, model, util
from txlb.model import HostMapper
from txlb.schedulers import roundr, leastc
from txlb.application.service import LoadBalancedService
from txlb.manager import checker
from txlb.manager.base import HostTracking
from txlb import schedulers

typ = roundr

proxyServices = [
  HostMapper(proxy='127.0.0.1:8080', lbType=typ, host='host0',
      address='127.0.0.1:10000'),
  HostMapper(proxy='127.0.0.1:8080', lbType=typ, host='host1',
      address='127.0.0.1:10001'),
  ]


# Amazon AWS commands
class AmazonAWS(object):
    def __init__(self):
        self.conn = boto.ec2.connect_to_region("us-west-2")
        self.workers = []

    def start_worker(self):
        w = self.conn.run_instances("ami-64ad3554", key_name='herik#cburkhal', instance_type='t1.micro')
        self.workers.append(w)
        return w

    def term_worker(self, worker):
        self.workers.remove(worker)
        return self.conn.terminate_instances(instance_ids=[w.id for w in worker.instances])

# overlay commands
class LoadBalanceService(service.Service):

    def __init__(self, tracker):
        self.tracker = tracker
        from twisted.internet.task import LoopingCall
        LoopingCall(self.reccuring).start(3)

    def startService(self):
        service.Service.startService(self)

    def reccuring(self):
        print self.tracker.getStats()
        pass

# Overlay Communication
class OverlayService(object):
    overlay = None

    def __init__(self, o):
        self.overlay = o

    def OK(self, reply):
        pass

    def JoinAccepted(self, reply):
        print "JoinReceived"
        return None

    def Join(self, reply):
        if self.overlay.is_coordinator:
            return {"command":"join_accept"}
        return {"command":"fail"}

    def Error(self, reply):
        print "receive error"
        return "error"

    commands = {"ok" : OK,
                "join_accept" : JoinAccepted,
                "join" : Join,
                "error" : Error}

class ClientProtocol(NetstringReceiver):
    def connectionMade(self):
        self.sendRequest(self.factory.request)

    def sendRequest(self, request):
        print request
        self.sendString(json.dumps(request))

    def stringReceived(self, reply):
        print reply
        self.transport.loseConnection()
        reply = json.loads(reply)
        command = reply["command"]
        if command not in self.factory.service.commands:
            print "Command <%s> does not exist!" % command
            self.transport.loseConnection()
            return self.factory.deferred.errback(0)
        self.factory.handleReply(command, reply)

class ServerProtocol(NetstringReceiver):
    def stringReceived(self, request):
        print request
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

class NodeClientFactory(ClientFactory):

    protocol = ClientProtocol

    def __init__(self, service, request):
        self.request = request
        self.service = service
        self.deferred = defer.Deferred()

    def handleReply(self, command, reply):
        def handler(reply):
            return self.service.commands[command](self.service, reply)
        cmd_handler = self.service.commands[command]
        if cmd_handler is None:
            return None
        self.deferred.addCallback(handler)
        self.deferred.callback(reply)

    def clientConnectionFailed(self, connector, reason):
        if self.deferred is not None:
            d, self.deferred = self.deferred, None
            d.errback(reason)

class NodeServerFactory(ServerFactory):

    protocol = ServerProtocol

    def __init__(self, service):
        self.service = service

    def reply(self, command, data):
        create_reply = self.service.commands[command]
        if create_reply is None: # no such command
            return None
        try:
            return create_reply(self.service, data)
        except:
            traceback.print_exc()
            return None # command failed

# initialization
class Overlay():
    is_coordinator = False
    coordinator = None
    members = []

    def init(self, tcp, udp):
        service = OverlayService(self)
        factory = NodeServerFactory(service)
        listen_tcp = reactor.listenTCP(tcp, factory)
        log.msg("init", 'Listening on %s.' % (listen_tcp.getHost()))
        print("node init, listening on "+str(listen_tcp.getHost()))
        self.join()

    def join(self):
        print "start join"
        def send(_, node):
            print "tcp before"
            factory = NodeClientFactory(OverlayService(self), {"command" : \
                    "join"})
            reactor.connectTCP(node["host"], node["tcp_port"], factory)
            print "tcp finished"
            factory.deferred.addCallback(lambda _: node)
            def sendcallback(_):
                return node
            def senderrback(_):
                raise Exception()
            factory.deferred.addCallbacks(sendcallback,senderrback)
            return factory.deferred
        def success(node):
            print "success " + str(node)
            coordinator = node
        def error(_):
            log.err("ERROR")
            self.is_coordinator = True
            print "I am coordinator"
        # search for running loadbalancers and join the overlay network
        nodes = self.read_config()
        initialized = False
        d = Deferred()
        for node in nodes:
            print "add node" + str(node)
            d.addErrback(send, node)
        d.addCallbacks(success, error)

        d.errback(0)

    def read_config(self):
        # read loadbalancer ip's
        f = open("load_balancers.txt", "r")
        nodes = []
        for line in f:
            s = line.split(":")
            nodes.append({"host":s[0],"tcp_port":int(s[1].strip())})
        return nodes

def init():
    pass

def addServiceToPM(pm, service):
    if isinstance(service, model.HostMapper):
        [service] = model.convertMapperToModel([service])
    for groupName, group in pm.getGroups(service.name):
        proxiedHost = service.getGroup(groupName).getHosts()[0][1]
        pm.getGroup(service.name, groupName).addHost(proxiedHost)
        tracker = HostTracking(group)
        scheduler = schedulers.schedulerFactory(group.lbType, tracker)
        pm.addTracker(service.name, groupName, tracker)

# cleanup and exit
def before_exit():
    sys.exit(0)

# main
def initApplication():
    application = service.Application('Demo LB Service')

    o = Overlay()
    o.init(12345, 12346)
    print "start overlay"

    typ = roundr
    pm = manager.proxyManagerFactory(proxyServices)
#    addServiceToPM(pm, HostMapper(proxy='127.0.0.1:8080', lbType=typ,
#        host='host2', address='127.0.0.1:10002'))
    for s in pm.services:
        print s
    lbs = LoadBalancedService(pm)
    #configuration = config.Config("config.xml")
    #print pm.trackers
    os = LoadBalanceService(pm.getTracker('proxy1', 'group1'))
    os.setServiceParent(application)
    lbs.setServiceParent(application)

    atexit.register(before_exit)
    return application

application = initApplication()
