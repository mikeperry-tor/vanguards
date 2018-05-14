#!/usr/bin/env python

import copy
import random

from logger import plog

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

# XXX: FlagsRestriction: Uptime, capacity (NodeRestriction: always want)
# XXX: Subnet16Restriction: Set restriction: at least one be different
# XXX: FamilyRestriction: Set restriction: at least one must be different


