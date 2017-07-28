#!/usr/bin/env python

import getpass
import sys
import logging
import copy
import random

import stem
import stem.connection
from stem.control import Controller

# MVP Plan:
# 1. Get consensus
# 2. Pass router list through Vanguard node filter/generator
# 3. Choose N,M Vanguards by bandwidth * Wmm
# 4. SETCONF torrc

# Later:
# 0. Provide client and server options
# 1. Log circuit construction and use
# 2. Verify it follows our vanguard settings
# 3. Subscribe to consensus events & follow prop271 for down nodes..

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

def build_sorted_rlist(controller):
  sorted_r = list(controller.get_network_statuses())
  sorted_r.sort(lambda x, y: cmp(y.measured, x.measured))

  for i in xrange(len(sorted_r)): sorted_r[i].list_rank = i

  return sorted_r

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

def main():
  controller = connect()
  sorted_r = build_sorted_rlist(controller)

  ng = UniformGenerator(sorted_r,
                     NodeRestrictionList([FlagsRestriction(["Fast", "Stable", "Guard"],
                                                           [])]))
  for r in ng.generate():
    print r

if __name__ == '__main__':
  main()
