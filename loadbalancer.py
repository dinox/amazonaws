from twisted.application import service
import os, sys, time, atexit, json, traceback, boto.ec2, socket
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


logger = {"host" : "erikhenriksson.se", "tcp_port" : 10000}



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
    aws = None

    def __init__(self, o):
        self.overlay = o
        self.aws = o.aws

    def OK(self, reply):
        pass

    def JoinAccepted(self, reply):
        self.overlay.members = reply["members"]
        self.overlay.my_node["id"] = reply["id"]
        send_log("JOIN","Joined coordinator")
        return None

    def Join(self, reply):
        if self.overlay.is_coordinator:
            reply["node"]["id"] = self.overlay.nextid
            self.overlay.members[reply["node"]["host"]] = reply["node"]
            print self.overlay.members
            msg = {"command":"join_accept","members":self.overlay.members\
                    ,"id":self.overlay.nextid}
            send_log("JOIN","Node " + self.overlay.nextid + " joined.")
            send_log("MEMBERS",str(self.overlay.members))
            self.overlay.nextid = self.overlay.nextid + 1
            return msg
        return {"command":"fail"}

    def OverlayMembers(self, reply):
        send_log("Debug", "OverlayMembers msg received")
        self.overlay.members = reply["members"]
        return {"command":"ok"}

    def LbWorkers(self, reply):
        send_log("Debug", "LbWorkers msg received")
        self.aws.workers = reply["workers"]
        return {"command":"ok"}

    def Error(self, reply):
        send_log("Warning", "Error msg received")
        return "error"

    commands = {"ok" : OK,
                "join_accept" : JoinAccepted,
                "join" : Join,
                "hb_members" : OverlayMembers,
                "hb_workers" : LbWorkers,
                "error" : Error}

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
            send_log("Error", "Command <%s> does not exist!" % command)
            self.transport.loseConnection()
            return self.factory.deferred.errback(0)
        self.factory.handleReply(command, reply)

class LogClientProtocol(NetstringReceiver):
    def connectionMade(self):
        self.sendRequest(self.factory.request)

    def sendRequest(self, request):
        self.sendString(json.dumps(request))

    def stringReceived(self, reply):
        pass

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

class LogClientFactory(ClientFactory):
    protocol = LogClientProtocol

    def __init__(self, request):
        self.request = request
        self.deferred = Deferred()

    def clientConnectionFailed(self, connector, reason):
        if self.deferred is not None:
            d, self.deferred = self.deferred, None
            d.errback(reason)


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
        self.service.commands[command](self.service, reply)
        self.deferred.callback(0)

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

# UDP serversocket, answers to ping requests

class UDPServer(DatagramProtocol):
    def datagramReceived(self, data, (host, port)):
        self.transport.write(data, (host, port))

class UDPClient(DatagramProtocol):
    host = ''
    port = 0
    pings = dict()

    def __init__(self, node, pings):
        self.host = node["host"]
        self.port = node["udp_port"]
        self.pings = pings

    def startProtocol(self):
        self.transport.connect(self.host, self.port)
        self.sendDatagram()

    def datagramReceived(self, datagram, host):
        global MyNode
        s = datagram.split(":")
        t = gettime() - float(s[1])
        self.pings[s[0]] = t
        log.msg("Ping to "+s[0]+" in "+str(t)+"ms")

    def sendDatagram(self):
        msg = str(self.host)+":"+str(gettime())
        self.transport.write(msg)

# time function
def gettime():
    return int(round(time.time() * 10000))

# initialization
class Overlay():
    is_coordinator = False
    coordinator = None
    members = dict()
    pings = dict()
    my_node = ""
    aws = None
    nextid = 0

    def init(self, tcp, udp):
        #init variables
        self.aws = AmazonAWS()

        host = socket.gethostbyname(socket.gethostname())
        # init tcp server
        service = OverlayService(self)
        factory = NodeServerFactory(service)
        listen_tcp = reactor.listenTCP(tcp, factory, interface=host)
        # initialize UDP socket
        listen_udp = reactor.listenUDP(udp, UDPServer(), interface=host)
        log.msg('Listening on %s.' % (listen_udp.getHost()))
        # set my_node
        self.my_node = {"host":listen_tcp.getHost().host,"tcp_port":\
            str(listen_tcp.getHost().port),"udp_port":\
            str(listen_udp.getHost().port),"id":-1}
        # log
        send_log("INIT", "node init, listening on "+str(listen_tcp.getHost()))
        send_log("INIT","node init, listening on "+str(listen_udp.getHost()))
        # try to join the overlay
        self.join()
        # register heartbeat
        LoopingCall(self.heartbeat).start(5)

    def join(self):
        print "start join"
        def send(_, node):
            factory = NodeClientFactory(OverlayService(self), {"command" : \
                    "join","node":self.my_node})
            reactor.connectTCP(node["host"], node["tcp_port"], factory)
            factory.deferred.addCallback(lambda _: node)
            def sendcallback(_):
                return node
            def senderrback(_):
                raise Exception()
            factory.deferred.addCallbacks(sendcallback,senderrback)
            return factory.deferred
        def success(node):
            coordinator = node
        def error(_):
            self.is_coordinator = True
            self.my_node["id"] = 0
            self.nextid = 1
            self.members[self.my_node["host"]] = self.my_node
            send_log("Notice", "I am coordinator")
        # search for running loadbalancers and join the overlay network
        nodes = self.read_config()
        initialized = False
        d = Deferred()
        for node in nodes:
            print "add node" + str(node)
            d.addErrback(send, node)
        d.addCallbacks(success, error)
        d.errback(0)

    def heartbeat(self):
        try:
            if self.is_coordinator:
                for host,node in self.members.items():
                    if not node is self.my_node:
                        factory = NodeClientFactory(OverlayService(self), {"command" : \
                            "join","workers":self.aws.workers})
                        reactor.connectTCP(node["host"], node["tcp_port"], factory)
        except Exception, e:
            pass

    def read_config(self):
        # read loadbalancer ip's
        f = open("load_balancers.txt", "r")
        nodes = []
        for line in f:
            s = line.split(":")
            nodes.append({"host":s[0],"tcp_port":int(s[1].strip())})
        return nodes

# send TCP message
# msg should contain a command, se ClientService or MonitorService
def send_msg(address, msg):
    from twisted.internet import reactor
    factory = LogClientFactory(msg)
    reactor.connectTCP(address["host"], address["tcp_port"], factory)
    return factory.deferred

# Logger function
# No linebreaks in event or desc!
def send_log(event, desc): 
    global logger, overlay
    data = dict()
    data["event"] = event
    data["desc"] = desc
    data["time"] = time.strftime("%H:%M:%S")
    data["command"] = "log"
    print overlay.my_node
    print overlay.my_node["id"]
    data["id"] = overlay.my_node["id"]
    print("Send log to logger: %s" % data)
    send_msg(logger, data)


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
    global overlay
    application = service.Application('Demo LB Service')
    proxyServices = [
      HostMapper(proxy='127.0.0.1:8080', lbType=typ, host='host0',
          address='127.0.0.1:10000'),
      HostMapper(proxy='127.0.0.1:8080', lbType=typ, host='host1',
          address='127.0.0.1:10001'),
      ]

    overlay = Overlay()
    overlay.init(12345, 12346)
    if overlay.is_coordinator:
        overlay.aws.start_worker()
        overlay.aws.start_worker()
        proxyServices = []
        id = 0
        for w in overlay.aws.workers:
            proxyServices.append(HostMapper(proxy='127.0.0.1:8080', lbType=typ,
                host='host' + str(id), address=str(w.private_ip_address) + ':10000'))
            id += 1

    send_log("Notice", "Overlay LB listening on tcp %s:%s" % \
            (overlay.my_node["host"], overlay.my_node["tcp_port"]))

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
