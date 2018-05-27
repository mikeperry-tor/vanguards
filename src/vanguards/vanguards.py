#!/usr/bin/env python

import random
import os
import time
import pickle
import sys

import stem

from .NodeSelection import BwWeightedGenerator, NodeRestrictionList
from .NodeSelection import FlagsRestriction
from .logger import plog

from . import control
from . import rendguard

################### Vanguard options ##################
#
NUM_LAYER1_GUARDS = 2 # 0 is Tor default
NUM_LAYER2_GUARDS = 3
NUM_LAYER3_GUARDS = 8

# In days:
LAYER1_LIFETIME_DAYS = 0 # Use tor default

# In hours
MIN_LAYER2_LIFETIME_HOURS = 24*1
MAX_LAYER2_LIFETIME_HOURS = 24*45

# In hours
MIN_LAYER3_LIFETIME_HOURS = 1
MAX_LAYER3_LIFETIME_HOURS = 48

_SEC_PER_HOUR = (60*60)

class GuardNode:
  def __init__(self, idhex, chosen_at, expires_at):
    self.idhex = idhex
    self.chosen_at = chosen_at
    self.expires_at = expires_at

class VanguardState:
  def __init__(self, state_file):
    self.layer2 = []
    self.layer3 = []
    self.state_file = state_file
    self.rendguard = rendguard.RendGuard()
    self.pickle_revision = 1

  def set_state_file(self, state_file):
    self.state_file = state_file

  def sort_and_index_routers(self, routers):
    sorted_r = list(routers)
    dict_r = {}

    for r in sorted_r:
      if r.measured == None:
        # FIXME: Hrmm...
        r.measured = r.bandwidth
    sorted_r.sort(key = lambda x: x.measured, reverse = True)
    for r in sorted_r: dict_r[r.fingerprint] = r
    return (sorted_r, dict_r)

  def consensus_update(self, routers, weights):
    (sorted_r, dict_r) = self.sort_and_index_routers(routers)
    ng = BwWeightedGenerator(sorted_r,
                       NodeRestrictionList([FlagsRestriction(["Fast", "Stable", "Valid"],
                                                             ["Authority"])]),
                             weights, BwWeightedGenerator.POSITION_MIDDLE)
    gen = ng.generate()
    self.replace_down_guards(dict_r, gen)

    # FIXME: Need to check this more often
    self.replace_expired(gen)
    self.rendguard.xfer_use_counts(ng)

  def new_consensus_event(self, controller, event):
    routers = controller.get_network_statuses()

    data_dir = controller.get_conf("DataDirectory")
    if data_dir == None:
      plog("ERROR",
           "You must set a DataDirectory location option in your torrc.")
      sys.exit(1)

    consensus_file = os.path.join(controller.get_conf("DataDirectory"),
                             "cached-microdesc-consensus")

    try:
      weights = control.get_consensus_weights(consensus_file)
    except IOError as e:
      plog("ERROR", "Cannot read "+consensus_file+": "+str(e))
      sys.exit(1)

    self.consensus_update(routers, weights)

    self.configure_tor(controller)
    try:
      self.write_to_file(open(self.state_file, "wb"))
    except IOError as e:
      plog("ERROR", "Cannot write state to "+self.state_file+": "+str(e))
      sys.exit(1)


  def configure_tor(self, controller):
    if NUM_LAYER1_GUARDS:
      controller.set_conf("NumEntryGuards", str(NUM_LAYER1_GUARDS))
      try:
        controller.set_conf("NumPrimaryGuards", str(NUM_LAYER1_GUARDS))
      except stem.InvalidArguments: # pre-0.3.4 tor
        pass

    if LAYER1_LIFETIME_DAYS > 0:
      controller.set_conf("GuardLifetime", str(LAYER1_LIFETIME_DAYS)+" days")

    try:
      controller.set_conf("HSLayer2Nodes", self.layer2_guardset())

      if NUM_LAYER3_GUARDS:
        controller.set_conf("HSLayer3Nodes", self.layer3_guardset())
    except stem.InvalidArguments:
      plog("ERROR",
           "Vanguards requires Tor 0.3.3.x (and ideally 0.3.4.x or newer).")
      sys.exit(1)

    # This is not a fatal error. Things like onionperf use stdin for conf
    # files. Maybe other stuff too. But let the user know.
    try:
      controller.save_conf()
    except stem.OperationFailed as e:
      plog("NOTICE", "Tor can't save its own config file: "+str(e))

  def write_to_file(self, outfile):
    return pickle.dump(self, outfile)

  @staticmethod
  def read_from_file(infile):
    ret = pickle.load(open(infile, "rb"))
    ret.set_state_file(infile)
    return ret

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
    expires = now + max(random.uniform(MIN_LAYER2_LIFETIME_HOURS*_SEC_PER_HOUR,
                                       MAX_LAYER2_LIFETIME_HOURS*_SEC_PER_HOUR),
                        random.uniform(MIN_LAYER2_LIFETIME_HOURS*_SEC_PER_HOUR,
                                       MAX_LAYER2_LIFETIME_HOURS*_SEC_PER_HOUR))
    self.layer2.append(GuardNode(guard.fingerprint, now, expires))
    plog("INFO", "New layer2 guard: "+guard.fingerprint)

  def add_new_layer3(self, generator):
    guard = next(generator)
    while guard.fingerprint in map(lambda g: g.idhex, self.layer3):
      guard = next(generator)

    now = time.time()
    expires = now + max(random.uniform(MIN_LAYER3_LIFETIME_HOURS*_SEC_PER_HOUR,
                                       MAX_LAYER3_LIFETIME_HOURS*_SEC_PER_HOUR),
                        random.uniform(MIN_LAYER3_LIFETIME_HOURS*_SEC_PER_HOUR,
                                       MAX_LAYER3_LIFETIME_HOURS*_SEC_PER_HOUR))
    self.layer3.append(GuardNode(guard.fingerprint, now, expires))
    plog("INFO", "New layer3 guard: "+guard.fingerprint)

  def _remove_expired(self, remove_from, now):
    for g in list(remove_from):
      if g.expires_at < now:
        remove_from.remove(g)
        plog("INFO", "Removing expired guard "+g.idhex)

  def replace_expired(self, generator):
    now = time.time()

    self._remove_expired(self.layer2, now)
    self.layer2 = self.layer2[:NUM_LAYER2_GUARDS]
    self._remove_expired(self.layer3, now)
    self.layer3 = self.layer3[:NUM_LAYER3_GUARDS]

    while len(self.layer2) < NUM_LAYER2_GUARDS:
      self.add_new_layer2(generator)

    while len(self.layer3) < NUM_LAYER3_GUARDS:
      self.add_new_layer3(generator)

  def _remove_down(self, remove_from, dict_r):
    removed = []
    for g in list(remove_from):
      if not g.idhex in dict_r:
        remove_from.remove(g)
        removed.append(g)
        plog("INFO", "Removing down guard "+g.idhex)
    return removed

  def replace_down_guards(self, dict_r, generator):
    # If any guards are down, remove them from current
    self._remove_down(self.layer2, dict_r)
    self._remove_down(self.layer3, dict_r)

    while len(self.layer2) < NUM_LAYER2_GUARDS:
      self.add_new_layer2(generator)

    while len(self.layer3) < NUM_LAYER3_GUARDS:
      self.add_new_layer3(generator)
