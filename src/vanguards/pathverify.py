""" Simple checks against bandwidth side channels """
import stem

from . import control

from .logger import plog

_ROUTELEN_FOR_PURPOSE = {
                         "HS_CLIENT_INTRO"  : 5,
                         "HS_CLIENT_REND"   : 4,
                         "HS_SERVICE_INTRO" : 4,
                         "HS_SERVICE_REND"  : 5,
                         "HS_VANGUARDS"     : 4
                        }

class PathVerify:
  def __init__(self, controller, num_layer1, num_layer2, num_layer3):
    self.controller = controller
    self.layer1 = {}
    self.layer2 = set()
    self.layer3 = set()
    self.num_layer1 = num_layer1
    self.num_layer2 = num_layer2
    self.num_layer3 = num_layer3
    self._orconn_init(controller)
    self._layers_init(controller)

  def _orconn_init(self, controller):
    for l in controller.get_info("orconn-status").split("\n"):
      if len(l):
        self.layer1[l.split("~")[0][1:]] = 0

    if len(self.layer1) < self.num_layer1:
      plog("NOTICE", "Fewer guards in use than configured.. Currently only "+ \
           str(self.layer1.keys()))
    elif len(self.layer1) > self.num_layer1:
      plog("NOTICE", "More guards in use than configured.. Currently using "+ \
           str(self.layer1.keys()))

  def _layers_init(self, controller):
    layer2 = controller.get_conf("HSLayer2Nodes", None)
    layer3 = controller.get_conf("HSLayer3Nodes", None)

    # These may be empty at startup
    if layer2:
      self.layer2 = set(layer2.split(","))
      if len(self.layer2) != self.num_layer2:
       plog("NOTICE", "Wrong number of layer2 guards. " + \
            str(self.num_layer2)+" vs: "+str(self.layer2))
    if layer3:
      self.layer3 = set(layer3.split(","))
      if len(self.layer3) != self.num_layer3:
        plog("NOTICE", "Wrong number of layer3 guards. " + \
             str(self.num_layer3)+" vs: "+str(self.layer3))

  def conf_changed_event(self, event):
    if "HSLayer2Nodes" in event.changed:
      self.layer2 = set(event.changed["HSLayer2Nodes"][0].split(","))

    if "HSLayer3Nodes" in event.changed:
      self.layer3 = set(event.changed["HSLayer3Nodes"][0].split(","))

    # These can become empty briefly on sighup. Aka set([''])
    if len(self.layer2) > 1:
      if len(self.layer2) != self.num_layer2:
        plog("NOTICE", "Wrong number of layer2 guards. " + \
            str(self.num_layer2)+" vs: "+str(self.layer2))

    if len(self.layer3) > 1:
      if len(self.layer3) != self.num_layer3:
        plog("NOTICE", "Wrong number of layer3 guards. " + \
             str(self.num_layer3)+" vs: "+str(self.layer3))

    plog("DEBUG", event.raw_content())

  def orconn_event(self, event):
    if event.status == "CONNECTED":
      self.layer1[event.endpoint_fingerprint] = 0
    elif event.status == "CLOSED" or event.status == "FAILED" and \
         event.endpoint_fingerprint in self.layer1:
      del self.layer1[event.endpoint_fingerprint]

    if len(self.layer1) < self.num_layer1:
      plog("NOTICE", "Fewer guards in use than configured. Currently only "+ \
           str(self.layer1))
    elif len(self.layer1) > self.num_layer1:
      plog("NOTICE", "More guards in use than configured. Currently using "+ \
           str(self.layer1))

  def circ_event(self, event):
    if event.purpose[0:3] == "HS_" and (event.status == stem.CircStatus.BUILT or \
       event.status == "GUARD_WAIT"):
      if len(event.path) != _ROUTELEN_FOR_PURPOSE[event.purpose]:
        plog("NOTICE", "Route len "+str(len(event.path))+ " is not " + \
             str(_ROUTELEN_FOR_PURPOSE[event.purpose])+ " for purpose " + \
             event.purpose +":"+str(event.hs_state)+" + " + \
             event.raw_content())
      if not event.path[0][0] in self.layer1:
        plog("WARN", "Guard "+event.path[0][0]+" not in "+ \
             str(self.layer1))
      else:
        self.layer1[event.path[0][0]] += 1

      if not event.path[1][0] in self.layer2:
         plog("WARN", "Layer2 "+event.path[1][0]+" not in "+ \
             str(self.layer2))
      if not event.path[2][0] in self.layer3:
         plog("WARN", "Layer3 "+event.path[1][0]+" not in "+ \
             str(self.layer3))

      if len(filter(lambda x: self.layer1[x], self.layer1.iterkeys())) != \
         self.num_layer1:
        plog("NOTICE", "Circuits built with different number of guards " + \
             "than configured. Currently using: " + str(self.layer1))

      if len(self.layer2) != self.num_layer2:
        plog("WARN", "Circuit built with different number of layer2 nodes " + \
             "than configured. Currently using: " + str(self.layer2))

      if len(self.layer3) != self.num_layer3:
        plog("WARN", "Circuit built with different number of layer3 nodes " + \
             "than configured. Currently using: " + str(self.layer3))

  def circ_minor_event(self, event):
    if event.purpose[0:3] == "HS_" and event.old_purpose[0:3] != "HS_":
      plog("WARN", "Purpose switched from non-hs to hs: "+ \
           str(event.raw_content()))
    elif event.purpose[0:3] != "HS_" and event.old_purpose[0:3] == "HS_":
      if event.purpose != "CIRCUIT_PADDING" and \
         event.purpose != "MEASURE_TIMEOUT":
        plog("WARN", "Purpose switched from hs to non-hs: "+ \
             str(event.raw_content()))

    if event.purpose[0:3] == "HS_" or event.old_purpose[0:3] == "HS_":
      if not event.path[0][0] in self.layer1:
        plog("WARN", "Guard "+event.path[0][0]+" not in "+ \
             str(self.layer1.keys()))
      if len(event.path) > 1 and not event.path[1][0] in self.layer2:
         plog("WARN", "Layer2 "+event.path[1][0]+" not in "+ \
             str(self.layer2))
      if len(event.path) > 2 and not event.path[2][0] in self.layer3:
         plog("WARN", "Layer3 "+event.path[1][0]+" not in "+ \
             str(self.layer3))

