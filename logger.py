import optparse, os, json, traceback, time, sys, signal

from twisted.internet.protocol import ServerFactory, Protocol
from twisted.protocols.basic import NetstringReceiver
from twisted.internet.task import LoopingCall

def parse_args():
    usage = """usage: %prog [options]"""

    parser = optparse.OptionParser(usage)

    help = "The port to listen on. Default to a random available port."
    parser.add_option('-p', '--port', type='int', help=help)

    help = "The interface to listen on. Default is 0.0.0.0."
    parser.add_option('--iface', help=help, default='0.0.0.0')

    help = "If you want debug output. Default is no."
    parser.add_option('-d', help=help, default=False)

    options, args = parser.parse_args()

    return options

class Logger(object):
    @staticmethod
    def log(time, id, event, desc):
        global is_debug_mode
        if id != "Monitor":
            id = "node%s" % id
        if event != "Debug" or is_debug_mode: 
            print "[%s] %s: %s: %s" % (time, id, event, desc)

    @staticmethod
    def log_self(event, desc):
        Logger.log(time.strftime("%H:%M:%S"), "Monitor", event, desc)

class LoggerService(object):
    def Log(self, data):
        def message(command, d):
            d["command"] = command
            return json.dumps(d)
        if not "id" in data:
            return message("error", {"reason" : "id not in log message"})
        if not "time" in data:
            return message("error", {"reason" : "time not in log message"})
        if not "event" in data:
            return message("error", {"reason" : "event not in log message"})
        if not "desc" in data:
            return message("error", {"reason" : "desc not in log message"})
        Logger.log(data["time"], data["id"], data["event"], data["desc"])
        return message("ok", {})

    commands = {"log" : Log}

class LoggerProtocol(NetstringReceiver):
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
            self.sendString(reply)

        self.transport.loseConnection()

class LoggerFactory(ServerFactory):

    protocol = LoggerProtocol

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

def main():
    options = parse_args()
    service = LoggerService()
    factory = LoggerFactory(service)
    from twisted.internet import reactor
    port = reactor.listenTCP(options.port or 0, factory,
                             interface=options.iface)
    print 'Listening on %s.' % (port.getHost())
    reactor.run()

if __name__ == '__main__':
    main()

