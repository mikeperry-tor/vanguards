#!/usr/bin/env python

import getpass
import sys
import logging
import copy
import random
import os
import time
import functools

import stem
import stem.connection
import stem.descriptor
from stem.control import Controller
from NodeSelection import BwWeightedGenerator, NodeRestrictionList, FlagsRestriction
from logger import plog

import argparse
import pickle

NUM_LAYER1_GUARDS = 0 # Use Tor default
NUM_LAYER2_GUARDS = 3
NUM_LAYER3_GUARDS = 4

# In days:
LAYER1_LIFETIME = 0 # Use tor default

# In hours
MIN_LAYER2_LIFETIME = 24*1
MAX_LAYER2_LIFETIME = 24*32

# In hours
MIN_LAYER3_LIFETIME = 1
MAX_LAYER3_LIFETIME = 18

CONTROL_HOST = "127.0.0.1"
CONTROL_PORT = 9051
CONTROL_SOCKET = None

SEC_PER_HOUR = (60*60)

# Experimentation:
# 0. Percentile restrictions? MTBF restrictions?
# 1. Onionperf scripts
# 2. Log circuit paths; verify proper path restrictions
# 3. Log CBT learning and timeout rate
# 4. Tools to audit+verify it follows our vanguard settings

def get_rlist_and_rdict(controller):
  sorted_r = list(controller.get_network_statuses())
  dict_r = {}
  sorted_r.sort(lambda x, y: cmp(y.measured, x.measured))

  for i in xrange(len(sorted_r)): sorted_r[i].list_rank = i

  for r in sorted_r: dict_r[r.fingerprint] = r

  return (sorted_r, dict_r)

def connect():
  if CONTROL_SOCKET != None:
    try:
      controller = Controller.from_socket_file(CONTROL_SOCKET)
    except stem.SocketError as exc:
      print("Unable to connect to Tor Control Socket at "+CONTROL_SOCKET+": %s" % exc)
      sys.exit(1)
  else:
    try:
      controller = Controller.from_port(CONTROL_HOST, CONTROL_PORT)
    except stem.SocketError as exc:
      print("Unable to connect to Tor Control Port at "+CONTROL_HOST+":"
             +str(CONTROL_PORT)+" %s" % exc)
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

def get_consensus_weights(controller):
  consensus = os.path.join(controller.get_conf("DataDirectory"),
                           "cached-microdesc-consensus")
  parsed_consensus = next(stem.descriptor.parse_file(consensus,
                          document_handler =
                            stem.descriptor.DocumentHandler.BARE_DOCUMENT))

  assert(parsed_consensus.is_consensus)
  return parsed_consensus.bandwidth_weights

def setup_options():
  global LAYER1_LIFETIME
  global MIN_LAYER2_LIFETIME, MAX_LAYER2_LIFETIME
  global MIN_LAYER3_LIFETIME, MAX_LAYER3_LIFETIME
  global NUM_LAYER1_GUARDS
  global NUM_LAYER2_GUARDS
  global NUM_LAYER3_GUARDS
  global CONTROL_HOST, CONTROL_PORT, CONTROL_SOCKET

  # XXX: Advanced vs simple options (--client, --service, etc)
  parser = argparse.ArgumentParser()
  parser.add_argument("--num_guards", type=int, dest="num_layer1",
                    help="Number of entry gurds (default "+str(NUM_LAYER1_GUARDS)+
                    "; 0 means use tor's value)", default=NUM_LAYER1_GUARDS)

  parser.add_argument("--num_mids", type=int, dest="num_layer2",
                    help="Number of Layer2 guards (default "+str(NUM_LAYER2_GUARDS)+
                    "; 0 disables)",
                    default=NUM_LAYER2_GUARDS)

  parser.add_argument("--num_ends", type=int, dest="num_layer3",
                    default=NUM_LAYER3_GUARDS,
                    help="Number of Layer3 guards (default "+str(NUM_LAYER3_GUARDS)+
                    "; 0 disables)")

  parser.add_argument("--guard_lifetime", type=int, dest="guard_lifetime",
                    default=LAYER1_LIFETIME,
                    help="Lifetime of Layer1 in days (default "+str(LAYER1_LIFETIME)+
                    "; 0 means use tor's value)")

  parser.add_argument("--mid_lifetime_min", type=int, dest="mid_lifetime_min",
                    default=MIN_LAYER2_LIFETIME,
                    help="Min lifetime of Layer2 in hours (default "+str(MIN_LAYER2_LIFETIME)+
                    ")")

  parser.add_argument("--mid_lifetime_max", type=int, dest="mid_lifetime_max",
                    default=MAX_LAYER2_LIFETIME,
                    help="Max lifetime of Layer2 in hours (default "+str(MAX_LAYER2_LIFETIME)+
                    ")")

  parser.add_argument("--end_lifetime_min", type=int, dest="end_lifetime_min",
                    default=MIN_LAYER3_LIFETIME,
                    help="Min lifetime of Layer3 in hours (default "+str(MIN_LAYER3_LIFETIME)+
                    ")")

  parser.add_argument("--end_lifetime_max", type=int, dest="end_lifetime_max",
                    default=MAX_LAYER3_LIFETIME,
                    help="Max lifetime of Layer3 in hours (default "+str(MAX_LAYER3_LIFETIME)+
                    ")")

  parser.add_argument("--state_file", dest="state_file", default="vanguards.state",
                    help="File to store vanguard state (default: DataDirectory/vanguards)")

  parser.add_argument("--control_host", dest="control_host", default=CONTROL_HOST,
                    help="The IP address of the Tor Control Port to connect to (default: "+
                    CONTROL_HOST+")")
  parser.add_argument("--control_port", type=int, dest="control_port",
                      default=CONTROL_PORT,
                      help="The Tor Control Port to connect to (default: "+
                      str(CONTROL_PORT)+")")

  parser.add_argument("--control_socket", dest="control_socket",
                      default=CONTROL_SOCKET,
                      help="The Tor Control Socket path to connect to "+
                      "(default: "+str(CONTROL_SOCKET)+")")

  options = parser.parse_args()

  (LAYER1_LIFETIME, MIN_LAYER2_LIFETIME, MAX_LAYER2_LIFETIME,
   MIN_LAYER3_LIFETIME, MAX_LAYER3_LIFETIME, NUM_LAYER1_GUARDS,
   NUM_LAYER2_GUARDS, NUM_LAYER3_GUARDS, CONTROL_HOST, CONTROL_PORT,
   CONTROL_SOCKET) = (options.guard_lifetime,
   options.mid_lifetime_min, options.mid_lifetime_max,
   options.end_lifetime_min, options.end_lifetime_max,
   options.num_layer1, options.num_layer2, options.num_layer3,
   options.control_host, options.control_port, options.control_socket)

  return options

class GuardNode:
  def __init__(self, idhex, chosen_at, expires_at):
    self.idhex = idhex
    self.chosen_at = chosen_at
    self.expires_at = expires_at

class VanguardState:
  def __init__(self):
    self.layer2 = []
    self.layer2_prev = []
    self.layer3 = []
    self.layer3_prev = []
    self.largest_circ_id = 0
    self.last_circ_for_old_guards = 0

  def write_to_file(self, outfile):
    return pickle.dump(self, outfile)

  @staticmethod
  def read_from_file(infile):
    return pickle.load(infile)

  # XXX: Log guards

  def layer2_guardset(self):
    return ",".join(map(lambda g: g.idhex, self.layer2))

  def layer3_guardset(self):
    return ",".join(map(lambda g: g.idhex, self.layer3))

  # Adds a new layer2 guard
  def add_new_layer2(self, generator):
    guard = generator.next()
    while guard.fingerprint in map(lambda g: g.idhex, self.layer2):
      guard = generator.next()

    now = time.time()
    expires = now + min(random.uniform(MIN_LAYER2_LIFETIME*SEC_PER_HOUR,
                                       MAX_LAYER2_LIFETIME*SEC_PER_HOUR),
                        random.uniform(MIN_LAYER2_LIFETIME*SEC_PER_HOUR,
                                       MAX_LAYER2_LIFETIME*SEC_PER_HOUR))
    self.layer2.append(GuardNode(guard.fingerprint, now, expires))

  def add_new_layer3(self, generator):
    guard = generator.next()
    while guard.fingerprint in map(lambda g: g.idhex, self.layer3):
      guard = generator.next()

    now = time.time()
    expires = now + max(random.uniform(MIN_LAYER3_LIFETIME*SEC_PER_HOUR,
                                       MAX_LAYER3_LIFETIME*SEC_PER_HOUR),
                        random.uniform(MIN_LAYER3_LIFETIME*SEC_PER_HOUR,
                                       MAX_LAYER3_LIFETIME*SEC_PER_HOUR))
    self.layer3.append(GuardNode(guard.fingerprint, now, expires))

  def load_tor_state(self, controller):
    circs = controller.get_circuits(None)
    if len(self.layer2_prev) == 0:
      layer2_ids = controller.get_conf("_HSLayer2Nodes").split(",")
      for fp in layer2_ids:
        self.layer2_prev.append(GuardNode(fp, 0, 0))

    if len(self.layer3_prev) == 0:
      layer3_ids = controller.get_conf("_HSLayer3Nodes").split(",")
      for fp in layer3_ids:
        self.layer3_prev.append(GuardNode(fp, 0, 0))

    if circs and len(circs):
      self.largest_circ_id = max(map(lambda c: c.id, circs))

    plog("INFO", "Got initial circ "+str(self.largest_circ_id)+
                 ", layer2 guards "+self.layer2_guardset()+
                 ", layer3 guards "+self.layer3_guardset())

  def save_previous_guards(self):
    self.layer2_prev = copy.deepcopy(self.layer2)
    self.layer3_prev = copy.deepcopy(self.layer3)

    # Used to tell when these old guards were last used.
    self.last_circ_for_old_guards = self.largest_circ_id

    plog("INFO", "New vanguard set at circ id "+str(self.largest_circ_id))

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
    self.layer2 = self.layer2[:NUM_LAYER2_GUARDS]
    self._remove_expired(self.layer3, now)
    self.layer3 = self.layer3[:NUM_LAYER2_GUARDS]

    while len(self.layer2) < NUM_LAYER2_GUARDS:
      self.add_new_layer2(generator)

    while len(self.layer3) < NUM_LAYER3_GUARDS:
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

  def consensus_update(self, dict_r, generator):
    # If any guards are down, remove them from current
    self._remove_down(self.layer2, dict_r)
    self._remove_down(self.layer3, dict_r)

    while len(self.layer2) < NUM_LAYER2_GUARDS:
      self.add_new_layer2(generator)

    while len(self.layer3) < NUM_LAYER3_GUARDS:
      self.add_new_layer3(generator)

def configure_tor(controller, vanguard_state):
  if NUM_LAYER1_GUARDS:
    controller.set_conf("NumEntryGuards", NUM_LAYER1_GUARDS)

  if LAYER1_LIFETIME:
    controller.set_conf("GuardLifetime", str(LAYER1_LIFETIME)+" days")

  controller.set_conf("_HSLayer2Nodes", vanguard_state.layer2_guardset())

  if NUM_LAYER3_GUARDS:
    controller.set_conf("_HSLayer3Nodes", vanguard_state.layer3_guardset())

  controller.save_conf()

# TODO: This might be inefficient, because we just 
# parsed the consensus for the event, and now we're parsing it
# again, twice.. Oh well. Prototype, and not critical path either.
def new_consensus_event(controller, state, options, event):
  (sorted_r, dict_r) = get_rlist_and_rdict(controller)
  weights = get_consensus_weights(controller)

  ng = BwWeightedGenerator(sorted_r,
                     NodeRestrictionList([FlagsRestriction(["Fast", "Stable"],
                                                           [])]),
                           weights, BwWeightedGenerator.POSITION_MIDDLE)
  gen = ng.generate()
  state.consensus_update(dict_r, gen)

  state.save_previous_guards()
  state.replace_expired(gen)

  # XXX: Print out current state

  configure_tor(controller, state)

  state.write_to_file(open(options.state_file, "w"))

class CircuitStat:
  def __init__(self, circ_id, is_hs):
    self.circ_id = circ_id
    self.is_hs = is_hs

class TimeoutStats:
  def __init__(self):
    self.circuits = {}
    self.all_launched = 0
    self.all_built = 0
    self.all_timeout = 0
    self.hs_launched = 0
    self.hs_built = 0
    self.hs_timeout = 0
    self.hs_changed = 0

  def add_circuit(self, circ_id, is_hs):
    if circ_id in self.circuits:
      plog("WARN", "Circuit "+circ_id+" already exists in map!")
    self.circuits[circ_id] = CircuitStat(circ_id, is_hs)
    self.all_launched += 1
    if is_hs: self.hs_launched += 1

  def update_circuit(self, circ_id, is_hs):
    if circ_id not in self.circuits: return
    if self.circuits[circ_id].is_hs != is_hs:
      self.hs_changed += 1
      self.hs_launched += 1
      self.circuits[circ_id].is_hs = is_hs

  def built_circuit(self, circ_id):
    if circ_id in self.circuits:
      self.all_built += 1
      if self.circuits[circ_id].is_hs:
        self.hs_built += 1
      del self.circuits[circ_id]

  def timeout_circuit(self, circ_id):
    if circ_id in self.circuits:
      self.all_timeout += 1
      if self.circuits[circ_id].is_hs:
        self.hs_timeout += 1
      del self.circuits[circ_id]

  # TODO: Sum launched == built+timeout+circuits

  def timeout_rate_all(self):
    if self.all_launched:
      return float(self.all_timeout)/(self.all_launched)
    else: return 0.0

  def timeout_rate_hs(self):
    if self.hs_launched:
      return float(self.hs_timeout)/(self.hs_launched)
    else: return 0.0

def circuit_event(state, timeouts, event):
  if event.id > state.largest_circ_id:
    state.largest_circ_id = event.id

  if event.hs_state or event.purpose[0:2] == "HS":
    if "status" in event.__dict__:
      if event.status == "LAUNCHED":
        timeouts.add_circuit(event.id, 0)
      elif event.status == "BUILT":
        timeouts.built_circuit(event.id)
      elif event.reason == "TIMEOUT":
        timeouts.timeout_circuit(event.id)
      timeouts.update_circuit(event.id, 1)

    if len(event.path) > 1:
      layer2 = event.path[1][0]

      # If this circuit was from before the last vanguard update, it may have
      # old guards. Check the new and the old ones in that case. Otherwise,
      # only check the new ones.
      if event.id <= state.last_circ_for_old_guards:
        if not layer2 in map(lambda x: x.idhex, state.layer2):
          if len(state.layer2_prev) > 0 and not layer2 in \
             map(lambda x: x.idhex, state.layer2_prev):
            plog("ERROR", "Old circuit with bad layer2 node "+layer2+": "+event.raw_content())
          else:
            plog("INFO", "Old circuit with old layer2 node "+layer2+": "+event.raw_content())
      else:
        if not layer2 in map(lambda x: x.idhex, state.layer2):
          plog("ERROR", "Circuit with bad layer2 node "+layer2+": "+event.raw_content())

    if len(event.path) > 2 and NUM_LAYER3_GUARDS:
      layer3 = event.path[2][0]

      if event.id <= state.last_circ_for_old_guards:
        if not layer3 in map(lambda x: x.idhex, state.layer3):
          if len(state.layer3_prev) >0 and not layer3 in \
             map(lambda x: x.idhex, state.layer3_prev):
            plog("ERROR", "Old circuit with bad layer3 node "+layer3+": "+event.raw_content())
          else:
            plog("INFO", "Old circuit with old layer3 node "+layer3+": "+event.raw_content())
      else:
        if not layer3 in map(lambda x: x.idhex, state.layer3):
          plog("ERROR", "Circuit with bad layer3 node "+layer3+": "+event.raw_content())

    # Check lengths against route_len_for_purpose:
    # Layer2+Layer3 guards:
    #    C - G - L2 - L3 - R
    #    S - G - L2 - L3 - HSDIR
    #    S - G - L2 - L3 - I
    #    C - G - L2 - L3 - M - I
    #    C - G - L2 - L3 - M - HSDIR
    #    S - G - L2 - L3 - M - R
    # XXX: If only layer2 guards are set, some of these may still be wrong.
    if "status" in event.__dict__ and event.status == "BUILT":
        if event.purpose == "HS_VANGUARDS":
          if NUM_LAYER3_GUARDS and len(event.path) != 4:
            plog("ERROR", "Circuit with bad path: "+event.raw_content())
          elif not NUM_LAYER3_GUARDS and len(event.path) != 3:
            plog("ERROR", "Circuit with bad path: "+event.raw_content())
          else:
            plog("INFO", "Circuit "+event.id+" OK!")
        elif event.purpose == "HS_CLIENT_REND":
          if NUM_LAYER3_GUARDS and len(event.path) != 4:
            plog("ERROR", "Circuit with bad path: "+event.raw_content())
          elif not NUM_LAYER3_GUARDS and len(event.path) != 3:
            plog("ERROR", "Circuit with bad path: "+event.raw_content())
          else:
            plog("INFO", "Circuit "+event.id+" OK!")
        elif event.purpose == "HS_SERVICE_HSDIR":
          # 4 is direct built, 5 is via HS_VANGUARDS
          if len(event.path) != 4 and len(event.path) != 5:
            plog("ERROR", "Circuit with bad path: "+event.raw_content())
          else:
            plog("INFO", "Circuit "+event.id+" OK!")
        elif event.purpose == "HS_SERVICE_INTRO":
          if len(event.path) != 4:
            plog("ERROR", "Circuit with bad path: "+event.raw_content())
          else:
            plog("INFO", "Circuit "+event.id+" OK!")
        elif event.purpose == "HS_CLIENT_INTRO":
          # client intros can be extended and retried.
          if len(event.path) < 5:
            plog("ERROR", "Circuit with bad path: "+event.raw_content())
          else:
            plog("INFO", "Circuit "+event.id+" OK!")
        elif event.purpose == "HS_CLIENT_HSDIR":
          if len(event.path) != 5:
            plog("ERROR", "Circuit with bad path: "+event.raw_content())
          else:
            plog("INFO", "Circuit "+event.id+" OK!")
        elif event.purpose == "HS_SERVICE_REND":
          if len(event.path) != 5:
            plog("ERROR", "Circuit with bad path: "+event.raw_content())
          else:
            plog("INFO", "Circuit "+event.id+" OK!")
  elif "status" in event.__dict__:
    if event.status == "LAUNCHED":
      timeouts.add_circuit(event.id, 0)
    elif event.status == "BUILT":
      timeouts.built_circuit(event.id)
    elif event.reason == "TIMEOUT":
      timeouts.timeout_circuit(event.id)

  plog("INFO", event.raw_content())

def cbt_event(timeouts, event):
  plog("NOTICE", "CBT Timeout rate: "+str(event.timeout_rate)+"; Our measured timeout rate: "+str(timeouts.timeout_rate_all())+"; Hidden service timeout rate: "+str(timeouts.timeout_rate_hs()))
  plog("INFO", event.raw_content())

def main():
  options = setup_options()
  try:
    # XXX: Get tor's data directory
    f = open(options.state_file)
    state = VanguardState.read_from_file(f)
  except:
    state = VanguardState()

  controller = connect()
  state.load_tor_state(controller)
  new_consensus_event(controller, state, options, None)
  timeouts = TimeoutStats()

  # This would be thread-unsafe, but we're done with these objects now
  new_consensus_handler = functools.partial(new_consensus_event,
                                            controller, state, options)
  controller.add_event_listener(new_consensus_handler,
                                stem.control.EventType.NEWCONSENSUS)

  circuit_handler = functools.partial(circuit_event, state, timeouts)
  controller.add_event_listener(circuit_handler,
                                stem.control.EventType.CIRC)
  controller.add_event_listener(circuit_handler,
                                stem.control.EventType.CIRC_MINOR)

  cbt_handler = functools.partial(cbt_event, timeouts)
  controller.add_event_listener(cbt_handler,
                                stem.control.EventType.BUILDTIMEOUT_SET)

  # Blah...
  while controller.is_alive():
    time.sleep(1)

if __name__ == '__main__':
  main()
