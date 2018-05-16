from . import config
from . import control

from .logger import plog

try:
  xrange
except NameError:
  xrange = range

class RendUseCount:
  def __init__(self, idhex, weight):
    self.idhex = idhex
    self.used = 0
    self.weight = weight

class RendWatcher:
  def __init__(self):
    self.use_counts = {}
    self.total_use_counts = 0

  def get_service_rend_node(self, path):
    if config.NUM_LAYER3_GUARDS:
      return path[4][0]
    else:
      return path[3][0]

  def valid_rend_use(self, purpose, path):
    r = self.get_service_rend_node(path)

    if r not in self.use_counts:
      plog("NOTICE", "Relay "+r+" is not in our consensus, but someone is using it!")
      self.use_counts[r] = RendUseCount(r, 0)

    self.use_counts[r].used += 1
    self.total_use_counts += 1.0

    # TODO: Can we base this check on statistical confidence intervals?
    if self.total_use_counts > config.USE_COUNT_TOTAL_MIN and \
       self.use_counts[r].used >= config.USE_COUNT_RELAY_MIN:
      plog("INFO", "Relay "+r+" used "+str(self.use_counts[r].used)+
                  " times out of "+str(int(self.total_use_counts)))

      if self.use_counts[r].used/self.total_use_counts > \
         self.use_counts[r].weight*config.USE_COUNT_RATIO:
        plog("WARN", "Relay "+r+" used "+str(self.use_counts[r].used)+
                     " times out of "+str(int(self.total_use_counts))+
                     ". This is above its weight of "+
                     str(self.use_counts[r].weight))
        return 0
    return 1

  def xfer_use_counts(self, node_gen):
    old_counts = self.use_counts
    self.use_counts = {}
    for r in node_gen.sorted_r:
       self.use_counts[r.fingerprint] = RendUseCount(r.fingerprint, 0)

    for i in xrange(len(node_gen.rstr_routers)):
      r = node_gen.rstr_routers[i]
      self.use_counts[r.fingerprint].weight = \
         node_gen.node_weights[i]/node_gen.weight_total

    # Periodically we divide counts by two, to avoid overcounting
    # high-uptime relays vs old ones
    for r in old_counts:
      if r not in self.use_counts: continue
      if self.total_use_counts > config.USE_COUNT_SCALE_AT:
        self.use_counts[r].used = old_counts[r].used/2
      else:
        self.use_counts[r].used = old_counts[r].used

    self.total_use_counts = sum(map(lambda x: self.use_counts[x].used,
                                    self.use_counts))
    self.total_use_counts = float(self.total_use_counts)

  def circ_event(self, controller, event):
    if event.status == "BUILT" and event.purpose == "HS_SERVICE_REND":
      if not self.valid_rend_use(event.purpose, event.path):
        control.try_close_circuit(controller, event.id)

    plog("DEBUG", event.raw_content())
