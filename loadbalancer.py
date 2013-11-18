from twisted.application import service
import os, sys, time, atexit, json, traceback, boto.ec2, socket, yaml
from twisted.internet.task import LoopingCall

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(SCRIPT_DIR, 'txlb'))

from twisted.internet import defer, reactor
from twisted.python.failure import Failure
from twisted.internet.defer import Deferred
from twisted.internet.protocol import Factory, Protocol, ClientFactory,\
        ServerFactory, DatagramProtocol
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.internet.threads import deferToThread
from twisted.protocols.basic import NetstringReceiver
from twisted.python import log
from twisted.web.client import Agent
from twisted.web.http_headers import Headers

from txlb import manager, config, model, util
from txlb.model import HostMapper
from txlb.schedulers import roundr, leastc
from txlb.application.service import LoadBalancedService
from txlb.manager import checker
from txlb.manager.base import HostTracking
from txlb import schedulers
from twisted.web import client
from txlb.manager.checker import checkBadHosts

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

    def term_workers(self):
        for w in list(self.workers):
            self.term_worker(w)

# overlay commands
class LoadBalanceService(service.Service):

    def __init__(self, tracker, pm):
        global overlay
        self.tracker = tracker
        self.pm = pm
        self.agent = Agent(reactor)
        client._HTTP11ClientFactory.noisy = False # Remove log spam
        from twisted.internet.task import LoopingCall
        LoopingCall(self.reccuring).start(3)
        def _delayed_func():
            LoopingCall(self.check_bad_workers).start(5)
            if overlay.config["autoscale"]["enabled"]:
                LoopingCall(self.poll_from_LB).start(0.5)
                LoopingCall(self.check_if_need_autoscale).start(15)
        reactor.callLater(0, _delayed_func)

    def startService(self):
        service.Service.startService(self)

    def reccuring(self):
        stats = self.tracker.getStats()
        hosts = [x for x, _ in sorted(stats["totals"].items())]
        openconns = [x for _, x in sorted(stats["openconns"].items())]
        totals = [x for _, x in sorted(stats["totals"].items())]
        bad = [x for x, _ in sorted(stats["bad"].items())]
        log_msg("Hosts: " + str(hosts))
        log_msg("Open conns: " + str(openconns))
        log_msg("Totals: " + str(totals))
        log_msg("Avg: " + str(stats['avg_process_time']))
        log_msg("Bad: " + str(bad))

    # Reccuring polling serice for measuring process time when there is no outer
    # requests happening
    def poll_from_LB(self):
        d = self.agent.request('GET', 'http://0.0.0.0:8080/10000',
                    Headers({'User-Agent': ['Twisted Web Client']}), None)
        d.addErrback(lambda _ : 0) # We dont care about errors here

    def check_bad_workers(self):
        class dummyConfig():
            class dummyManager():
                hostCheckEnabled = True
            manager = dummyManager()
        checkBadHosts(dummyConfig(), self.pm) 

    def check_if_need_autoscale(self):
        global overlay
        config = overlay.config["autoscale"]
        def _avg(numbers):
            if not len(numbers):
                return 0.0
            return sum(numbers)/float(len(numbers))
        stats = self.tracker.getStats()
        avg = _avg([x for _, x in stats['avg_process_time'].items()])
        openconns = sum([x for _, x in sorted(stats["openconns"].items())])
        if avg > config["scale-up"] and openconns > len(overlay.aws.workers):
            send_log("SCALE", "Scale up " + str(avg))
            log_msg("scale-up %f" % avg)
            self.scale_up()
        elif avg < config["scale-down"]:
            send_log("SCALE", "Scale down " + str(avg))
            log_msg("scale-down %f" % avg)
            self.scale_down()

    def scale_up(self):
        global overlay
        new_workers = len(overlay.aws.workers)
        d = Deferred()
        def _start_worker(_):
            deferred = deferToThread(overlay.aws.start_worker)
            def _addHost(w):
                log_msg("Started new host %s:10000" %
                        str(w.instances[0].private_ip_address))
                tr.newHost((w.instances[0].private_ip_address, 3000), "host" + str(id))
                return w
            deferred.addCallback(_addHost)
            return deferred
        for i in range(1, new_workers):
            d.addCallback(_start_worker)

    def scale_down(self):
        global overlay
        n_workers = len(overlay.aws.workers)
        if n_workers <= overlay.config["workers"]:
            return
        d = Deferred()
        for i in range(1, n_workers / 2):
            d.addCallback(overlay.aws.term_worker(overlay.aws.workers[i]))



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
            msg = {"command":"join_accept","members":self.overlay.members\
                    ,"id":self.overlay.nextid, "workers" : overlay.aws.workers}
            send_log("JOIN","Node " + str(self.overlay.nextid) + " joined.")
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
    my_node = None
    aws = None
    nextid = 0
    d = Deferred()
    config = None

    def init(self, tcp, udp):
        # load config
        self.load_config()
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
        self.d.addCallback(self.join)
        self.d.callback(0)
        # register heartbeat
        LoopingCall(self.heartbeat).start(5)

    def join(self, _):
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
        def error(e):
            self.is_coordinator = True
            self.my_node["id"] = 0
            self.nextid = 1
            self.members[self.my_node["host"]] = self.my_node
            send_log("Notice", "I am coordinator")
            return e
        # search for running loadbalancers and join the overlay network
        initialized = False
        d = Deferred()
        for node in self.config["nodes"]:
            d.addErrback(send, node)
        d.addCallbacks(success, error)
        d.errback(0)
        return d

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

    def load_config(self):
        global logger
        # load config, set logger
        f = open("config.yaml", "r")
        self.config = yaml.load(f)
        f.close()
        logger = self.config["logger"]
        return self.config

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
    data["id"] = overlay.my_node["id"]
    print("%s LOG: %s: %s" % (data["time"],event,desc))
    send_msg(logger, data)

# cleanup and exit
def before_exit():
    global overlay
    overlay.aws.term_workers()
    sys.exit(0)

# main
def initApplication():
    global overlay
    application = service.Application('Demo LB Service')
    # This is because you have to add a first host. It will not be used for
    # anything.
    proxyServices = [HostMapper(proxy='0.0.0.0:8080', lbType=leastc, host='host0',
        address='127.0.0.1:10000'),]

    overlay = Overlay()
    overlay.init(12345, 12346)
    pm = manager.proxyManagerFactory(proxyServices)
    tr = pm.getTracker("proxy1", "group1")

    def start_workers(_):
        d = Deferred()
        # load number of workers
        f = open("config.yaml", "r")
        config = yaml.load(f)
        f.close()
        N = config["workers"]
        print "Start %i number of workers!" % N
        #N = 2

        def _start_worker(_):
            deferred = deferToThread(overlay.aws.start_worker)
            def _addHost(w):
                print "Started new host %s:10000" % str(w.instances[0].private_ip_address)
                tr.newHost((w.instances[0].private_ip_address, 3000), "host" + str(id))
                return w
            deferred.addCallback(_addHost)
            return deferred

        for id in range(1,N+1):
            d.addCallback(_start_worker)
        d.callback(0)
        return d

    def add_workers(_):
        for w in overlay.aws.workers:
            print "Added host " + str(w.instances[0].private_ip_address)
            tr.newHost((w.instances[0].private_ip_address, 3000), "host" + str(id))
            id += 1

    overlay.d.addCallbacks(add_workers, start_workers)

    def remove_default_worker(_):
        tr.delHost('127.0.0.1:10000')
    #overlay.d.addBoth(remove_default_worker)

    for s in pm.services:
        print s
    lbs = LoadBalancedService(pm)
    #configuration = config.Config("config.xml")
    #print pm.trackers
    os = LoadBalanceService(pm.getTracker('proxy1', 'group1'), pm)
    os.setServiceParent(application)
    lbs.setServiceParent(application)

    atexit.register(before_exit)
    return application

application = initApplication()
