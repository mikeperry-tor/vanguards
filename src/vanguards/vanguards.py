#!/usr/bin/env python

import getpass
import sys
import logging
import copy
import random
import os
import time
import functools
import pickle

import stem
import stem.connection
import stem.descriptor
from stem.control import Controller

from .NodeSelection import BwWeightedGenerator, NodeRestrictionList
from .NodeSelection import FlagsRestriction
from .logger import plog
from .bandguards import BandwidthStats
from .cbtverify import TimeoutStats

from . import config

try:
  xrange
except NameError:
  xrange = range

SEC_PER_HOUR = (60*60)

def connect():
  if config.CONTROL_SOCKET != None:
    try:
      controller = Controller.from_socket_file(config.CONTROL_SOCKET)
    except stem.SocketError as exc:
      print("Unable to connect to Tor Control Socket at "\
            +config.CONTROL_SOCKET+": %s" % exc)
      sys.exit(1)
  else:
    try:
      controller = Controller.from_port(config.CONTROL_HOST,
                                        config.CONTROL_PORT)
    except stem.SocketError as exc:
      print("Unable to connect to Tor Control Port at "+config.CONTROL_HOST+":"
             +str(config.CONTROL_PORT)+" %s" % exc)
      sys.exit(1)

  try:
    controller.authenticate()
  except stem.connection.MissingPassword:
    pw = getpass.getpass("Controller password: ")

    try:
      controller.authenticate(password = pw)
    except stem.connection.PasswordAuthFailed:
      print("Unable to authenticate, password is incorrect")
      sys.exit(1)
  except stem.connection.AuthenticationFailure as exc:
    print("Unable to authenticate: %s" % exc)
    sys.exit(1)

  print("Tor is running version %s" % controller.get_version())

  return controller

def get_consensus_weights(consensus_filename):
  parsed_consensus = next(stem.descriptor.parse_file(consensus_filename,
                          document_handler =
                            stem.descriptor.DocumentHandler.BARE_DOCUMENT))

  assert(parsed_consensus.is_consensus)
  return parsed_consensus.bandwidth_weights

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

class GuardNode:
  def __init__(self, idhex, chosen_at, expires_at):
    self.idhex = idhex
    self.chosen_at = chosen_at
    self.expires_at = expires_at

  def __str__(self):
    return self.idhex

  def __repr__(self):
    return self.idhex

class VanguardState:
  def __init__(self):
    self.layer2 = []
    self.layer3 = []
    self.rendwatcher = RendWatcher()

  def sort_and_index_routers(self, routers):
    sorted_r = list(routers)
    dict_r = {}

    for r in sorted_r:
      if r.measured == None:
        # FIXME: Hrmm...
        r.measured = r.bandwidth
    sorted_r.sort(key = lambda x: x.measured, reverse = True)
    for i in xrange(len(sorted_r)): sorted_r[i].list_rank = i
    for r in sorted_r: dict_r[r.fingerprint] = r
    return (sorted_r, dict_r)

  def consensus_update(self, routers, weights):
    (sorted_r, dict_r) = self.sort_and_index_routers(routers)
    ng = BwWeightedGenerator(sorted_r,
                       NodeRestrictionList([FlagsRestriction(["Fast", "Stable"],
                                                             [])]),
                             weights, BwWeightedGenerator.POSITION_MIDDLE)
    gen = ng.generate()
    self.replace_down_guards(dict_r, gen)

    # FIXME: Need to check this more often
    self.replace_expired(gen)
    self.rendwatcher.xfer_use_counts(ng)

  def new_consensus_event(self, controller, event):
    routers = controller.get_network_statuses()
    consensus_file = os.path.join(controller.get_conf("DataDirectory"),
                             "cached-microdesc-consensus")
    weights = get_consensus_weights(consensus_file)
    self.consensus_update(routers, weights)

    self.configure_tor(controller)
    self.write_to_file(open(config.STATE_FILE, "wb"))

  def configure_tor(self, controller):
    if config.NUM_LAYER1_GUARDS:
      controller.set_conf("NumEntryGuards", str(config.NUM_LAYER1_GUARDS))
      try:
        controller.set_conf("NumPrimaryGuards", str(config.NUM_LAYER1_GUARDS))
      except stem.InvalidArguments:
        pass

    if config.LAYER1_LIFETIME:
      controller.set_conf("GuardLifetime", str(config.LAYER1_LIFETIME)+" days")

    controller.set_conf("HSLayer2Nodes", self.layer2_guardset())

    if config.NUM_LAYER3_GUARDS:
      controller.set_conf("HSLayer3Nodes", self.layer3_guardset())

    controller.save_conf()

  def write_to_file(self, outfile):
    return pickle.dump(self, outfile)

  @staticmethod
  def read_from_file(infile):
    return pickle.load(infile)

  def layer2_guardset(self):
    return ",".join(map(lambda g: g.idhex, self.layer2))

  def layer3_guardset(self):
    return ",".join(map(lambda g: g.idhex, self.layer3))

  # Adds a new layer2 guard
  def add_new_layer2(self, generator):
    guard = next(generator)
    while guard.fingerprint in map(lambda g: g.idhex, self.layer2):
      guard = next(generator)

    now = time.time()
    expires = now + max(random.uniform(config.MIN_LAYER2_LIFETIME*SEC_PER_HOUR,
                                       config.MAX_LAYER2_LIFETIME*SEC_PER_HOUR),
                        random.uniform(config.MIN_LAYER2_LIFETIME*SEC_PER_HOUR,
                                       config.MAX_LAYER2_LIFETIME*SEC_PER_HOUR))
    self.layer2.append(GuardNode(guard.fingerprint, now, expires))

  def add_new_layer3(self, generator):
    guard = next(generator)
    while guard.fingerprint in map(lambda g: g.idhex, self.layer3):
      guard = next(generator)

    now = time.time()
    expires = now + max(random.uniform(config.MIN_LAYER3_LIFETIME*SEC_PER_HOUR,
                                       config.MAX_LAYER3_LIFETIME*SEC_PER_HOUR),
                        random.uniform(config.MIN_LAYER3_LIFETIME*SEC_PER_HOUR,
                                       config.MAX_LAYER3_LIFETIME*SEC_PER_HOUR))
    self.layer3.append(GuardNode(guard.fingerprint, now, expires))

  def _remove_expired(self, remove_from, now):
    for g in list(remove_from):
      if g.expires_at < now:
        remove_from.remove(g)

  def replace_expired(self, generator):
    plog("INFO", "Replacing any old vanguards. Current "+
                 " layer2 guards: "+self.layer2_guardset()+
                 " Current layer3 guards: "+self.layer3_guardset())

    now = time.time()

    self._remove_expired(self.layer2, now)
    self.layer2 = self.layer2[:config.NUM_LAYER2_GUARDS]
    self._remove_expired(self.layer3, now)
    self.layer3 = self.layer3[:config.NUM_LAYER2_GUARDS]

    while len(self.layer2) < config.NUM_LAYER2_GUARDS:
      self.add_new_layer2(generator)

    while len(self.layer3) < config.NUM_LAYER3_GUARDS:
      self.add_new_layer3(generator)

    plog("INFO", "New layer2 guards: "+self.layer2_guardset()+
                 " New layer3 guards: "+self.layer3_guardset())

  def _remove_down(self, remove_from, dict_r):
    removed = []
    for g in list(remove_from):
      if not g.idhex in dict_r:
        remove_from.remove(g)
        removed.append(g)
    return removed

  def replace_down_guards(self, dict_r, generator):
    # If any guards are down, remove them from current
    self._remove_down(self.layer2, dict_r)
    self._remove_down(self.layer3, dict_r)

    while len(self.layer2) < config.NUM_LAYER2_GUARDS:
      self.add_new_layer2(generator)

    while len(self.layer3) < config.NUM_LAYER3_GUARDS:
      self.add_new_layer3(generator)

def try_close_circuit(controller, circ_id):
  try:
    controller.close_circuit(circ_id)
    plog("NOTICE", "We force-closed circuit "+str(circ_id))
  except stem.InvalidRequest as e:
    plog("INFO", "Failed to close circuit "+str(circ_id)+": "+str(e.message))

def circuit_event(state, timeouts, event, controller):
  if event.status == "BUILT" and event.purpose == "HS_SERVICE_REND":
    if not state.rendwatcher.valid_rend_use(event.purpose, event.path):
      try_close_circuit(controller, event.id)

  plog("DEBUG", event.raw_content())

def main():
  config.setup_options()
  try:
    # TODO: Use tor's data directory.. or our own
    f = open(config.STATE_FILE, "rb")
    state = VanguardState.read_from_file(f)
  except:
    state = VanguardState()

  stem.response.events.PARSE_NEWCONSENSUS_EVENTS = False
  controller = connect()
  state.new_consensus_event(controller, None)
  timeouts = TimeoutStats()
  bandwidths = BandwidthStats(controller)

  # Thread-safety: state, timeouts, and bandwidths are effectively
  # transferred to the event thread here. They must not be used in
  # our thread anymore.
  # XXX: Make rendwatcher optional by config (on by default)
  circuit_handler = functools.partial(circuit_event, state, timeouts,
                                      controller)
  controller.add_event_listener(circuit_handler,
                                stem.control.EventType.CIRC)

  # XXX: Make bandgaurds optional by config (on by default)
  controller.add_event_listener(
               functools.partial(BandwidthStats.circ_event, bandwidths),
                                stem.control.EventType.CIRC)
  controller.add_event_listener(
               functools.partial(BandwidthStats.bw_event, bandwidths),
                                stem.control.EventType.BW)
  controller.add_event_listener(
               functools.partial(BandwidthStats.circbw_event, bandwidths),
                                stem.control.EventType.CIRC_BW)

  # XXX: Make circ_timeouts by config (off by default)
  controller.add_event_listener(
               functools.partial(TimeoutStats.circ_event, timeouts),
                                stem.control.EventType.CIRC)
  controller.add_event_listener(
               functools.partial(TimeoutStats.cbt_event, timeouts),
                                stem.control.EventType.BUILDTIMEOUT_SET)

  # Thread-safety: We're effectively transferring controller to the event
  # thread here.
  controller.add_event_listener(
               functools.partial(VanguardState.new_consensus_event,
                                 state, controller),
                                stem.control.EventType.NEWCONSENSUS)

  # Blah...
  while controller.is_alive():
    time.sleep(1)

if __name__ == '__main__':
  main()
