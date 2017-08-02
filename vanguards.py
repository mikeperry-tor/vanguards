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

SEC_PER_HOUR = (60*60)

# MVP Plan:
# 1. Get consensus
# 2. Pass router list through Vanguard node filter/generator
# 3. Options:
#    a. Provide client and server options
#    b. Provide num_guards options
#    c. Choose N,M Vanguards by bandwidth * Wmm
# 4. GETCONF/SETCONF torrc
# 5. Implement rotation/expiry
# 6. Subscribe to consensus events & follow prop271 for down nodes..
# 7. Percentile restrictions? MTBF restrictions?

# Experimentation:
# 1. Onionperf scripts
# 2. Log circuit paths; verify proper path restrictions
# 3. Log CBT learning and timeout rate
# 4. Tools to audit+verify it follows our vanguard settings

logger = None
loglevel = "DEBUG"
logfile = None

loglevels = { "DEBUG":  logging.DEBUG,
              "INFO":   logging.INFO,
              "NOTICE": logging.INFO + 5,
              "WARN":   logging.WARN,
              "ERROR":  logging.ERROR,
              "NONE":   logging.ERROR + 5 }

def plog(level, msg, *args):
  global logger, logfile
  if not logger:
    # Default init = old TorCtl format + default behavior
    # Default behavior = log to stdout if TorUtil.logfile is None,
    # or to the open file specified otherwise.
    logger = logging.getLogger("TorCtl")
    formatter = logging.Formatter("%(levelname)s[%(asctime)s]:%(message)s",
                                  "%a %b %d %H:%M:%S %Y")

    if not logfile:
      logfile = sys.stdout
    # HACK: if logfile is a string, assume is it the desired filename.
    if isinstance(logfile, basestring):
      f = logging.FileHandler(logfile)
      f.setFormatter(formatter)
      logger.addHandler(f)
    # otherwise, pretend it is a stream.
    else:
      ch = logging.StreamHandler(logfile)
      ch.setFormatter(formatter)
      logger.addHandler(ch)
    logger.setLevel(loglevels[loglevel])

  logger.log(loglevels[level], msg, *args)


class RestrictionError(Exception):
  "Error raised for issues with applying restrictions"
  pass

class NoNodesRemain(RestrictionError):
  "Error raised for issues with applying restrictions"
  pass

class NodeRestriction:
  "Interface for node restriction policies"
  def r_is_ok(self, r):
    "Returns true if Router 'r' is acceptable for this restriction"
    return True

class PercentileRestriction(NodeRestriction):
  """Restriction to cut out a percentile slice of the network."""
  def __init__(self, pct_skip, pct_fast, r_list):
    """Constructor. Sets up the restriction such that routers in the 
     'pct_skip' to 'pct_fast' percentile of bandwidth rankings are 
     returned from the sorted list 'r_list'"""
    self.pct_fast = pct_fast
    self.pct_skip = pct_skip
    self.sorted_r = r_list

  def r_is_ok(self, r):
    "Returns true if r is in the percentile boundaries (by rank)"
    if r.list_rank < len(self.sorted_r)*self.pct_skip/100: return False
    elif r.list_rank > len(self.sorted_r)*self.pct_fast/100: return False
    return True

  def __str__(self):
    return self.__class__.__name__+"("+str(self.pct_skip)+","+str(self.pct_fast)+")"

class FlagsRestriction(NodeRestriction):
  "Restriction for mandatory and forbidden router flags"
  def __init__(self, mandatory, forbidden=[]):
    """Constructor. 'mandatory' and 'forbidden' are both lists of router
     flags as strings."""
    self.mandatory = mandatory
    self.forbidden = forbidden

  def r_is_ok(self, router):
    for m in self.mandatory:
      if not m in router.flags: return False
    for f in self.forbidden:
      if f in router.flags: return False
    return True

  def __str__(self):
    return self.__class__.__name__+"("+str(self.mandatory)+","+str(self.forbidden)+")"

class MetaNodeRestriction(NodeRestriction):
  """Interface for a NodeRestriction that is an expression consisting of
     multiple other NodeRestrictions"""
  def add_restriction(self, rstr): raise NotImplemented()
  # TODO: these should collapse the restriction and return a new
  # instance for re-insertion (or None)
  def next_rstr(self): raise NotImplemented()
  def del_restriction(self, RestrictionClass): raise NotImplemented()

class NodeRestrictionList(MetaNodeRestriction):
  "Class to manage a list of NodeRestrictions"
  def __init__(self, restrictions):
    "Constructor. 'restrictions' is a list of NodeRestriction instances"
    self.restrictions = restrictions

  def r_is_ok(self, r):
    "Returns true of Router 'r' passes all of the contained restrictions"
    for rs in self.restrictions:
      if not rs.r_is_ok(r): return False
    return True

  def add_restriction(self, restr):
    "Add a NodeRestriction 'restr' to the list of restrictions"
    self.restrictions.append(restr)

  # TODO: This does not collapse meta restrictions..
  def del_restriction(self, RestrictionClass):
    """Remove all restrictions of type RestrictionClass from the list.
       Does NOT inspect or collapse MetaNode Restrictions (though 
       MetaRestrictions can be removed if RestrictionClass is 
       MetaNodeRestriction)"""
    self.restrictions = filter(
        lambda r: not isinstance(r, RestrictionClass),
          self.restrictions)

  def clear(self):
    """ Remove all restrictions """
    self.restrictions = []

  def __str__(self):
    return self.__class__.__name__+"("+str(map(str, self.restrictions))+")"

class NodeGenerator:
  "Interface for node generation"
  def __init__(self, sorted_r, rstr_list):
    """Constructor. Takes a bandwidth-sorted list of Routers 'sorted_r'
    and a NodeRestrictionList 'rstr_list'"""
    self.rstr_list = rstr_list
    self.rebuild(sorted_r)
    self.rewind()

  def reset_restriction(self, rstr_list):
    "Reset the restriction list to a new list"
    self.rstr_list = rstr_list
    self.rebuild()

  def rewind(self):
    "Rewind the generator to the 'beginning'"
    self.routers = copy.copy(self.rstr_routers)
    if not self.routers:
      plog("NOTICE", "No routers left after restrictions applied: "+str(self.rstr_list))
      raise NoNodesRemain(str(self.rstr_list))

  def rebuild(self, sorted_r=None):
    """ Extra step to be performed when new routers are added or when
    the restrictions change. """
    if sorted_r != None:
      self.sorted_r = sorted_r
    self.rstr_routers = filter(lambda r: self.rstr_list.r_is_ok(r), self.sorted_r)

    if not self.rstr_routers:
      plog("NOTICE", "No routers left after restrictions applied: "+str(self.rstr_list))
      raise NoNodesRemain(str(self.rstr_list))

  def mark_chosen(self, r):
    """Mark a router as chosen: remove it from the list of routers
     that can be returned in the future"""
    self.routers.remove(r)

  def all_chosen(self):
    "Return true if all the routers have been marked as chosen"
    return not self.routers

  def generate(self):
    "Return a python generator that yields routers according to the policy"
    raise NotImplemented()

class UniformGenerator(NodeGenerator):
  """NodeGenerator that produces nodes in the uniform distribution"""
  def generate(self):
    # XXX: hrmm.. this is not really the right thing to check
    while not self.all_chosen():
      yield random.choice(self.routers)

class BwWeightedGenerator(NodeGenerator):
  POSITION_GUARD = 'g'
  POSITION_MIDDLE = 'm'
  POSITION_EXIT = 'e'

  def flag_to_weight(self, node):
    if 'Guard' in node.flags and "Exit" in node.flags:
      return self.bw_weights[u'W'+self.position+'d']/self.WEIGHT_SCALE

    if 'Exit' in node.flags:
      return self.bw_weights[u'W'+self.position+'e']/self.WEIGHT_SCALE

    if "Guard" in node.flags:
      return self.bw_weights[u'W'+self.position+'g']/self.WEIGHT_SCALE

    return self.bw_weights[u'Wmm']/self.WEIGHT_SCALE

  def rebuild(self, sorted_r=None):
    NodeGenerator.rebuild(self, sorted_r)
    NodeGenerator.rewind(self)
    # XXX: Use consensus param
    self.WEIGHT_SCALE = 10000.0

    print self.bw_weights
    self.node_weights = []
    for r in self.rstr_routers:
      assert(not r.is_unmeasured)
      self.node_weights.append(r.bandwidth*self.flag_to_weight(r))

    self.weight_total = sum(self.node_weights)

  def __init__(self, sorted_r, rstr_list, bw_weights, position):
    self.position = position
    self.bw_weights = bw_weights
    self.node_weights = []
    NodeGenerator.__init__(self, sorted_r, rstr_list)

  def generate(self):
    # XXX: hrmm.. different termination condition?
    while True:
      choice_val = random.uniform(0, self.weight_total)
      choose_total = 0
      choice_idx = 0
      while choose_total < choice_val:
        choose_total += self.node_weights[choice_idx]
        choice_idx += 1
      yield self.rstr_routers[choice_idx-1]


def get_rlist_and_rdict(controller):
  sorted_r = list(controller.get_network_statuses())
  dict_r = {}
  sorted_r.sort(lambda x, y: cmp(y.measured, x.measured))

  for i in xrange(len(sorted_r)): sorted_r[i].list_rank = i

  for r in sorted_r: dict_r[r.fingerprint] = r

  return (sorted_r, dict_r)

def connect():
  try:
    controller = Controller.from_port()
  except stem.SocketError as exc:
    print("Unable to connect to tor on port 9051: %s" % exc)
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

  parser.add_argument("--state_file", dest="state_file", default="vanguards",
                    help="File to store vanguard state (default: DataDirectory/vanguards)")

  options = parser.parse_args()

  (LAYER1_LIFETIME, MIN_LAYER2_LIFETIME, MAX_LAYER2_LIFETIME,
   MIN_LAYER3_LIFETIME, MAX_LAYER3_LIFETIME, NUM_LAYER1_GUARDS,
   NUM_LAYER2_GUARDS, NUM_LAYER3_GUARDS) = (options.guard_lifetime,
   options.mid_lifetime_min, options.mid_lifetime_max,
   options.end_lifetime_min, options.end_lifetime_max,
   options.num_layer1, options.num_layer2, options.num_layer3)

  return options

class GuardNode:
  def __init__(self, idhex, chosen_at, expires_at, priority):
    self.idhex = idhex
    self.chosen_at = chosen_at
    self.expires_at = expires_at
    self.priority_index = priority

class VanguardState:
  def __init__(self):
    self.layer2 = []
    self.layer2_down = []
    self.layer3 = []
    self.layer3_down = []

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
  def add_new_layer2(self, generator, priority):
    guard = generator.next()
    now = time.time()
    expires = now + min(random.uniform(MIN_LAYER2_LIFETIME*SEC_PER_HOUR,
                                       MAX_LAYER2_LIFETIME*SEC_PER_HOUR),
                        random.uniform(MIN_LAYER2_LIFETIME*SEC_PER_HOUR,
                                       MAX_LAYER2_LIFETIME*SEC_PER_HOUR))
    self.layer2.append(GuardNode(guard.fingerprint, now, expires, priority))

  def add_new_layer3(self, generator, priority):
    guard = generator.next()
    now = time.time()
    expires = now + max(random.uniform(MIN_LAYER3_LIFETIME*SEC_PER_HOUR,
                                       MAX_LAYER3_LIFETIME*SEC_PER_HOUR),
                        random.uniform(MIN_LAYER3_LIFETIME*SEC_PER_HOUR,
                                       MAX_LAYER3_LIFETIME*SEC_PER_HOUR))
    self.layer3.append(GuardNode(guard.fingerprint, now, expires, priority))

  def _remove_expired(self, remove_from, now):
    for g in list(remove_from):
      if g.expires_at < now:
        remove_from.remove(g)

  def replace_expired(self, generator):
    now = time.time()

    self._remove_expired(self.layer2, now)
    self.layer2 = self.layer2[:NUM_LAYER2_GUARDS]
    self._remove_expired(self.layer3, now)
    self.layer3 = self.layer3[:NUM_LAYER2_GUARDS]
    self._remove_expired(self.layer2_down, now)
    self._remove_expired(self.layer3_down, now)

    while len(self.layer2) < NUM_LAYER2_GUARDS:
      self.add_new_layer2(generator, 0)

    while len(self.layer3) < NUM_LAYER3_GUARDS:
      self.add_new_layer3(generator, 0)

  def _remove_down(self, remove_from, dict_r):
    removed = []
    for g in list(remove_from):
      if not g.idhex in dict_r:
        remove_from.remove(g)
        removed.append(g)
    return removed

  def consensus_update(self, dict_r, generator):
    # If any guards are down, move them from current to down
    self.layer2_down.extend(self._remove_down(self.layer2, dict_r))
    self.layer3_down.extend(self._remove_down(self.layer3, dict_r))

    # If we drop below our target, first check for re-upped guards,
    # then if none, add more with lower priority
    # (Yeah, this is suboptimal, but it is not critical)
    while len(self.layer2) < NUM_LAYER2_GUARDS:
      min_up = None
      for g in self.layer2_down:
        if g.idhex in dict_r:
          if not min_up or min_up.priority_index > g.priority_index:
            min_up = g

      # XXX: +1 over current highest priority?
      if not min_up: self.add_new_layer2(generator, 1)
      else:
        self.layer2.append(min_up)
        self.layer2_down.remove(min_up)

    while len(self.layer3) < NUM_LAYER3_GUARDS:
      min_up = None
      for g in self.layer3_down:
        if g.idhex in dict_r:
          if not min_up or min_up.priority_index > g.priority_index:
            min_up = g

      # XXX: +1 over current highest priority?
      if not min_up: self.add_new_layer3(generator, 1)
      else:
        self.layer3.append(min_up)
        self.layer3_down.remove(min_up)

def configure_tor(controller, vanguard_state):
  if NUM_LAYER1_GUARDS:
    controller.set_conf("NumEntryGuards", NUM_LAYER1_GUARDS)

  if LAYER1_LIFETIME:
    controller.set_conf("GuardLifetime", str(LAYER1_LIFETIME)+" days")

  controller.set_conf("HSLayer2Guards", vanguard_state.layer2_guardset())
  controller.set_conf("HSLayer3Guards", vanguard_state.layer3_guardset())

  controller.save_conf()

# TODO: This might be inefficient, because we just 
# parsed the consensus for the event, and now we're parsing it
# again, twice.. Oh well. Prototype, and not critical path either.
def new_consensus_event(controller, state, options, event):
  (sorted_r, dict_r) = get_rlist_and_rdict(controller)
  weights = get_consensus_weights(controller)

  ng = BwWeightedGenerator(sorted_r,
                     NodeRestrictionList([FlagsRestriction(["Fast", "Stable", "Guard"],
                                                           [])]),
                           weights, BwWeightedGenerator.POSITION_MIDDLE)
  gen = ng.generate()
  state.consensus_update(dict_r, gen)
  state.replace_expired(gen)

  configure_tor(controller, state)

  state.write_to_file(open(options.state_file, "w"))

def new_circuit_event(event):
  print event.raw_content()

def cbt_event(event):
  print event.raw_content()

def main():
  options = setup_options()
  try:
    f = open(options.state_file)
    state = VanguardState.read_from_file(f)
  except:
    state = VanguardState()

  controller = connect()
  new_consensus_event(controller, state, options, None)

  # This would be thread-unsafe, but we're done with these objects now
  new_consensus_handler = functools.partial(new_consensus_event,
                                            controller, state, options)
  controller.add_event_listener(new_consensus_handler,
                                stem.control.EventType.NEWCONSENSUS)

  controller.add_event_listener(new_circuit_event,
                                stem.control.EventType.CIRC)
  controller.add_event_listener(new_circuit_event,
                                stem.control.EventType.CIRC_MINOR)
  controller.add_event_listener(cbt_event,
                                stem.control.EventType.BUILDTIMEOUT_SET)


  # Blah...
  while controller.is_alive():
    time.sleep(1)

if __name__ == '__main__':
  main()
