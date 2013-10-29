from twisted.application import service
import os, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(SCRIPT_DIR, 'txlb'))

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

class OverlayService(service.Service):

    def __init__(self, tracker):
        self.tracker = tracker
        from twisted.internet.task import LoopingCall
        LoopingCall(self.reccuring).start(3)

    def startService(self):
        service.Service.startService(self)

    def reccuring(self):
        print self.tracker.getStats()


application = service.Application('Demo LB Service')
pm = manager.proxyManagerFactory(proxyServices)
lbs = LoadBalancedService(pm)
print pm.trackers
os = OverlayService(pm.getTracker('proxy1', 'group1'))
os.setServiceParent(application)
lbs.setServiceParent(application)
