#!/usr/bin/env python

import random
import os
import time
import pickle
import sys
import string

from ipaddress import ip_network as net

import stem

from .NodeSelection import BwWeightedGenerator, NodeRestrictionList
from .NodeSelection import FlagsRestriction, NoNodesRemain, UnusableWeight
from .logger import plog

from . import control
from . import rendguard

# Unicode, damnit
try:
  _UNICODE_DAMNIT = bool(type(unicode))
except NameError:
  unicode = str

################### Vanguard options ##################
#
NUM_LAYER1_GUARDS = 2 # 0 is Tor default
NUM_LAYER2_GUARDS = 4
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

class ExcludeNodes:
  def __init__(self, controller):
    self.networks = []
    self.idhexes = set()
    self.nicks = set()
    self.countries = set()
    self.controller = controller
    self.exclude_unknowns = controller.get_conf("GeoIPExcludeUnknown")
    self._parse_line(controller.get_conf("ExcludeNodes"))

  def _parse_line(self, conf_line):
    # We assume Tor has validated the line already. So this parsing
    # is very dumb+simple (except for semantics of valid data).
    # See routerset_parse() in tor for parser semantic ordering.
    if self.exclude_unknowns == "1":
      self.countries.add("??")
      self.countries.add("a1")

    if conf_line == None:
      return

    parts = conf_line.split(",")
    for p in parts:
      if p[0] == "$":
        p = p[1:]
      if "~" in p:
        p = p.split("~")[0]
      if "=" in p:
        p = p.split("=")[0]

      if len(p) == 40 and all(c in string.hexdigits for c in p):
        self.idhexes.add(p)
      elif p[0] == "{" and p[-1] == "}":
        self.countries.add(p[1:-1].lower())
      elif ":" in p or "." in p:
        self.networks.append(net(unicode(p), strict=False))
      else:
        self.nicks.add(p)
    plog("INFO", "Honoring ExcludeNodes line: "+conf_line)
    if len(self.networks):
      plog("INFO", "Excluding networks "+str(self.networks))
    if len(self.idhexes):
      plog("INFO", "Excluding idhexes "+str(self.idhexes))
    if len(self.nicks):
      plog("INFO", "Excluding nicks "+str(self.nicks))
    if len(self.countries):
      if self.exclude_unknowns == "auto":
        self.countries.add("??")
        self.countries.add("a1")

      if self.controller.get_info("ip-to-country/ipv4-available", "0") == "0":
        plog("WARN", "ExcludeNodes contains countries, but Tor has no GeoIP file! "+
             "Tor is not excluding countries!")
      else:
        plog("INFO", "Excluding countries "+str(self.countries))

  def router_is_excluded(self, r):
    if r.fingerprint in self.idhexes:
      return True
    if r.nickname in self.nicks:
      return True
    if "or_addresses" in r.__dict__: # Stem 1.7.0 only
      addresses = r.or_addresses
    else:
      addresses = [(r.address, 9001, False)]
    for addr in addresses:
      is_ipv6 = addr[2]
      if len(self.countries):
        country = None
        if is_ipv6 and \
          self.controller.get_info("ip-to-country/ipv6-available", "0") == "1":
          country = self.controller.get_info("ip-to-country/"+addr[0])
        if not is_ipv6 and \
          self.controller.get_info("ip-to-country/ipv4-available", "0") == "1":
          country = self.controller.get_info("ip-to-country/"+addr[0])

        if country != None and country.lower() in self.countries:
          return True

      for network in self.networks:
        if is_ipv6:
          if network.version == 6 and net(addr[0]+"/128").overlaps(network):
            return True
        else:
          if network.version == 4 and net(addr[0]+"/32").overlaps(network):
            return True
    return False

class VanguardState:
  def __init__(self, state_file):
    self.layer2 = []
    self.layer3 = []
    self.state_file = state_file
    self.rendguard = rendguard.RendGuard()
    self.pickle_revision = 1
    self.enable_vanguards = True # Set from main, irrelevant to pickle

  def set_state_file(self, state_file):
    self.state_file = state_file

  def sort_and_index_routers(self, routers):
    sorted_r = list(routers)
    dict_r = {}

    for r in sorted_r:
      if r.measured == None:
        if r.bandwidth is None:
          raise stem.DescriptorUnavailable("Consensus contains a relay without bandwidth")
        # FIXME: Hrmm...
        r.measured = r.bandwidth
    sorted_r.sort(key = lambda x: x.measured, reverse = True)
    for r in sorted_r: dict_r[r.fingerprint] = r
    return (sorted_r, dict_r)

  def consensus_update(self, routers, weights, exclude, *, update_guards=True, require_guards=True):
    (sorted_r, dict_r) = self.sort_and_index_routers(routers)

    rend_nodes = BwWeightedGenerator(sorted_r,
                       NodeRestrictionList(
                             [FlagsRestriction(["Fast", "Valid"],
                                               ["Authority", "MiddleOnly"])]),
                             weights, BwWeightedGenerator.POSITION_MIDDLE)
    # Cannibalized circuits can use Exit relays as rendezvous points.
    rend_nodes.repair_exits()
    for router in rend_nodes.rstr_routers:
      total = rend_nodes.exit_total if "Exit" in router.flags else rend_nodes.weight_total
      if total <= 0:
        raise stem.DescriptorUnavailable("Consensus has zero rendezvous weight")

    guards_updated = self.enable_vanguards and update_guards
    if guards_updated:
      try:
        self._update_guard_layers(sorted_r, dict_r, weights, exclude)
      except (stem.DescriptorUnavailable, NoNodesRemain, UnusableWeight) as exc:
        if require_guards:
          raise
        plog("WARN", "Skipping guard update: %s", str(exc))
        guards_updated = False

    # Transfer and scale RP use counts to this consensus
    self.rendguard.xfer_use_counts(rend_nodes)
    return guards_updated

  def _update_guard_layers(self, sorted_r, dict_r, weights, exclude):
    guard_nodes = BwWeightedGenerator(sorted_r,
                     NodeRestrictionList(
                           [FlagsRestriction(["Fast", "Stable", "Valid"],
                                             ["Authority"])]),
                           weights, BwWeightedGenerator.POSITION_MIDDLE)
    if guard_nodes.weight_total <= 0:
      raise stem.DescriptorUnavailable("Consensus has zero guard selection weight")

    layer2 = self.update_guard_layer(self.layer2, 2, NUM_LAYER2_GUARDS, dict_r,
                                     exclude, guard_nodes.generate(),
                                     MIN_LAYER2_LIFETIME_HOURS, MAX_LAYER2_LIFETIME_HOURS)
    layer3 = self.update_guard_layer(self.layer3, 3, NUM_LAYER3_GUARDS, dict_r,
                                     exclude, guard_nodes.generate(),
                                     MIN_LAYER3_LIFETIME_HOURS, MAX_LAYER3_LIFETIME_HOURS)

    for number, old, updated in ((2, self.layer2, layer2), (3, self.layer3, layer3)):
      for guard in old:
        if guard not in updated:
          plog("INFO", "Removing layer%d guard: %s", number, guard.idhex)
      for guard in updated:
        if guard not in old:
          plog("INFO", "New layer%d guard: %s", number, guard.idhex)
    self.layer2, self.layer3 = layer2, layer3

  def new_consensus_event(self, controller, event, *, require_guards=False):
    try:
      self._update_from_consensus(controller, require_guards)
      return True
    except stem.DescriptorUnavailable as exc:
      if event is None:
        raise
      plog("WARN", "Skipping consensus update: %s", str(exc))
      return False

  def _read_tor_consensus(self, controller):
    try:
      cache_dir = controller.get_conf("CacheDirectory")
    except stem.InvalidArguments:
      cache_dir = None
    if not cache_dir:
      cache_dir = controller.get_conf("DataDirectory")
    if cache_dir is None:
      raise stem.DescriptorUnavailable(
          "Set an absolute CacheDirectory or DataDirectory in torrc that the addon can read")

    microdesc = controller.get_conf("UseMicrodescriptors") != "0"
    cache_name = "cached-microdesc-consensus" if microdesc else "cached-consensus"
    consensus_file = os.path.join(cache_dir, cache_name)

    try:
      consensus = control.read_consensus(consensus_file)
      key = "dir/status-vote/current/consensus"
      if microdesc:
        key += "-microdesc"
      tor_consensus = controller.get_info(key, None, get_bytes=True)
      if tor_consensus is None:
        raise stem.DescriptorUnavailable("Tor cannot provide the consensus document over the control port")
      # Stem removes the final line break from a multiline control reply.
      if tor_consensus.rstrip(b"\n") != consensus.get_bytes().rstrip(b"\n"):
        raise stem.DescriptorUnavailable("Cached consensus differs from the connected Tor's consensus document")
    except IOError as e:
      raise stem.DescriptorUnavailable("Cannot read "+consensus_file+": "+str(e))
    except (StopIteration, TypeError, ValueError):
      raise stem.DescriptorUnavailable("Cannot parse consensus at " + consensus_file)

    if consensus.is_microdescriptor != microdesc:
      raise stem.DescriptorUnavailable("Unexpected consensus flavor in " + consensus_file)
    active = controller.get_info("consensus/valid-after", "")
    if not active or active != str(consensus.valid_after):
      raise stem.DescriptorUnavailable("Cached consensus does not match Tor's active consensus")
    # Tor's control response includes Valid for every relay in method 24+
    # consensuses, even if the cached router row omits the flag.
    implies_valid = (consensus.consensus_method or 0) >= 24
    for router in consensus.routers.values():
      if not router.fingerprint or not router.address:
        raise stem.DescriptorUnavailable("Consensus contains an invalid relay identity or address")
      if implies_valid and "Valid" not in router.flags:
        router.flags.append("Valid")
    return consensus

  def _check_vanguards_lite(self, controller, consensus=None):
    try:
      enabled = controller.get_conf("VanguardsLiteEnabled")
    except stem.InvalidArguments:
      return  # Tor releases before Vanguards Lite still honor explicit layers.
    if enabled == "auto":
      if consensus is None:
        consensus = self._read_tor_consensus(controller)
      # Stem 1.8 sorts parameter names, while Tor sorts full key=value tokens.
      # Read this key directly from the already matched consensus document.
      params = consensus.get_bytes().partition(b"\nparams ")[2].split(b"\n", 1)[0]
      key = b"vanguards-lite-enabled="
      for param in params.split():
        if param.startswith(key):
          try:
            enabled = "1" if int(param[len(key):]) > 0 else "0"
          except ValueError:
            raise stem.DescriptorUnavailable("Invalid vanguards-lite-enabled consensus parameter")
          break
    if enabled == "0":
      raise stem.DescriptorUnavailable(
          "Tor will ignore explicit guard layers. Set VanguardsLiteEnabled 1 in torrc")

  def _update_from_consensus(self, controller, require_guards=False):
    consensus = self._read_tor_consensus(controller)
    update_guards = self.enable_vanguards
    if self.enable_vanguards:
      try:
        self._check_vanguards_lite(controller, consensus)
      except stem.DescriptorUnavailable as exc:
        if require_guards:
          raise
        plog("WARN", "Skipping guard update: %s", str(exc))
        update_guards = False
    exclude_nodes = ExcludeNodes(controller)

    try:
      guards_updated = self.consensus_update(consensus.routers.values(), consensus.bandwidth_weights,
                                             exclude_nodes, update_guards=update_guards,
                                             require_guards=require_guards)
    except NoNodesRemain:
      raise stem.DescriptorUnavailable("No eligible relays in the consensus")
    except UnusableWeight as exc:
      raise stem.DescriptorUnavailable("Missing or invalid consensus weight: " + str(exc))

    if guards_updated:
      self.configure_tor(controller)
      self._guards_deferred = False
    elif self.enable_vanguards and not update_guards:
      self._guards_deferred = True

    try:
      self.write_to_file(open(self.state_file, "wb"))
    except IOError as e:
      plog("ERROR", "Cannot write state to "+self.state_file+": "+str(e))
      sys.exit(1)

  def signal_event(self, controller, event):
    if event.signal == "RELOAD":
      try:
        if (getattr(self, "_guards_deferred", False)
            or (NUM_LAYER2_GUARDS and not self.layer2)
            or (NUM_LAYER3_GUARDS and not self.layer3)):
          self._update_from_consensus(controller, require_guards=True)
        else:
          self._check_vanguards_lite(controller)
          self.configure_tor(controller)
      except stem.DescriptorUnavailable as exc:
        self._guards_deferred = True
        plog("WARN", "Skipping guard reapplication: %s", str(exc))
        return
      plog("NOTICE", "Tor got SIGHUP. Reapplying vanguards.")

  def configure_tor(self, controller):
    if NUM_LAYER1_GUARDS:
      controller.set_conf("NumEntryGuards", str(NUM_LAYER1_GUARDS))
      controller.set_conf("NumDirectoryGuards", str(NUM_LAYER1_GUARDS))

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

  def update_guard_layer(self, layer, number, size, routers, excluded,
                         candidates, min_hours, max_hours):
    now = time.time()
    updated = [guard for guard in layer if guard.idhex in routers
               and guard.expires_at >= now
               and not excluded.router_is_excluded(routers[guard.idhex])][:size]
    if len(updated) >= size:
      return updated

    used = {guard.idhex for guard in updated}
    for router in candidates:
      if router.fingerprint in used or excluded.router_is_excluded(router):
        continue
      expires = now + _SEC_PER_HOUR * max(random.uniform(min_hours, max_hours),
                                          random.uniform(min_hours, max_hours))
      updated.append(GuardNode(router.fingerprint, now, expires))
      used.add(router.fingerprint)
      if len(updated) == size:
        return updated

    raise stem.DescriptorUnavailable("Too few eligible relays to fill guard layer %d" % number)
