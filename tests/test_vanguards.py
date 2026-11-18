import stem
import time
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from stem.response import ControlMessage

from vanguards.control import get_consensus_weights

import vanguards.vanguards
from vanguards.vanguards import VanguardState
from vanguards.vanguards import ExcludeNodes
from vanguards.vanguards import _SEC_PER_HOUR

from vanguards.vanguards import NUM_LAYER3_GUARDS
from vanguards.vanguards import NUM_LAYER2_GUARDS
from vanguards.vanguards import MIN_LAYER3_LIFETIME_HOURS
from vanguards.vanguards import MAX_LAYER3_LIFETIME_HOURS
from vanguards.vanguards import MIN_LAYER2_LIFETIME_HOURS
from vanguards.vanguards import MAX_LAYER2_LIFETIME_HOURS

try:
  xrange
except NameError:
  xrange = range

def replacement_checks(state, routers, weights):
  remove2_idhex = state.layer2[0].idhex
  remove3_idhex = state.layer3[0].idhex

  # - Remove a layer2 guard from it
  # - Remove a layer3 guard from it
  routers = list(filter(lambda x: x.fingerprint != remove2_idhex \
                         and x.fingerprint != remove3_idhex,
                   routers))

  assert remove2_idhex in map(lambda x: x.idhex, state.layer2)
  assert remove3_idhex in map(lambda x: x.idhex, state.layer3)
  keep2 = map(lambda x: x.idhex,
              filter(lambda x: x.idhex != remove2_idhex \
                               and x.idhex != remove3_idhex,
                     state.layer2))
  keep3 = map(lambda x: x.idhex,
              filter(lambda x: x.idhex != remove2_idhex \
                               and x.idhex != remove3_idhex,
                     state.layer3))
  state.consensus_update(routers, weights, ExcludeNodes(MockController()))
  sanity_check(state)
  assert not remove2_idhex in map(lambda x: x.idhex, state.layer2)
  assert not remove3_idhex in map(lambda x: x.idhex, state.layer3)
  for k in keep2: assert k in map(lambda x: x.idhex, state.layer2)
  for k in keep3: assert k in map(lambda x: x.idhex, state.layer3)

  remove2_idhex = state.layer2[1].idhex
  remove3_idhex = state.layer3[1].idhex

  # - Mark a layer2 guard way in the past
  # - Mark a layer3 guard way in the past
  state.layer2[1].expires_at = time.time() - 10
  state.layer3[1].expires_at = time.time() - 10

  assert remove2_idhex in map(lambda x: x.idhex, state.layer2)
  assert remove3_idhex in map(lambda x: x.idhex, state.layer3)
  keep2 = map(lambda x: x.idhex,
              filter(lambda x: x.idhex != remove2_idhex,
                     state.layer2))
  keep3 = map(lambda x: x.idhex,
              filter(lambda x: x.idhex != remove3_idhex,
                     state.layer3))
  state.consensus_update(routers, weights, ExcludeNodes(MockController()))
  sanity_check(state)
  assert not remove2_idhex in map(lambda x: x.idhex, state.layer2)
  assert not remove3_idhex in map(lambda x: x.idhex, state.layer3)
  for k in keep2: assert k in map(lambda x: x.idhex, state.layer2)
  for k in keep3: assert k in map(lambda x: x.idhex, state.layer3)

  # - Mark all guards way in the past
  for g in state.layer2:
    g.expires_at = time.time() - 10
  for g in state.layer3:
    g.expires_at = time.time() - 10

  state.consensus_update(routers, weights, ExcludeNodes(MockController()))
  sanity_check(state)

  # Remove a node by idhex a few different ways
  controller = MockController()
  controller.exclude_nodes = \
    str(state.layer2[0].idhex)+","+str("$"+state.layer3[0].idhex)+","+\
    str(state.layer2[1].idhex+"~lol")+","+\
    str("$"+state.layer3[1].idhex+"~lol")+","+\
    str(state.layer2[2].idhex+"=lol")+","+\
    str("$"+state.layer3[2].idhex+"=lol")

  removed2 = \
    [state.layer2[0].idhex, state.layer2[1].idhex, state.layer2[2].idhex]
  removed3 = \
    [state.layer3[0].idhex, state.layer3[1].idhex, state.layer3[2].idhex]

  for r in removed2:
    assert r in map(lambda x: x.idhex, state.layer2)
  for r in removed3:
    assert r in map(lambda x: x.idhex, state.layer3)

  keep3 = state.layer3[3].idhex
  state.consensus_update(routers, weights, ExcludeNodes(controller))
  for r in removed2:
    assert not r in map(lambda x: x.idhex, state.layer2)
  for r in removed3:
    assert not r in map(lambda x: x.idhex, state.layer3)
  assert keep3 in map(lambda x: x.idhex, state.layer3)

def sanity_check(state):
  assert len(state.layer2) == NUM_LAYER2_GUARDS
  assert len(state.layer3) == NUM_LAYER3_GUARDS

  for g in state.layer2:
    assert g.expires_at - g.chosen_at < MAX_LAYER2_LIFETIME_HOURS*_SEC_PER_HOUR
    assert g.expires_at - g.chosen_at >= MIN_LAYER2_LIFETIME_HOURS*_SEC_PER_HOUR

  for g in state.layer3:
    assert g.expires_at - g.chosen_at < MAX_LAYER3_LIFETIME_HOURS*_SEC_PER_HOUR
    assert g.expires_at - g.chosen_at >= MIN_LAYER3_LIFETIME_HOURS*_SEC_PER_HOUR

class MockController:
  def __init__(self):
    self.data_dir = "tests"
    self.cache_dir = None
    self.exclude_nodes = None
    self.exclude_unknown = "1"
    self.got_set_conf = False
    self.got_save_conf = False
    self.get_info_vals = {}
    self._logguard = None

  def signal(self, sig):
    pass

  # FIXME: os.path.join
  def get_network_statuses(self):
    return list(stem.descriptor.parse_file("tests/cached-microdesc-consensus",
                   document_handler =
                      stem.descriptor.DocumentHandler.ENTRIES))

  def get_conf(self, key, default=None):
    if key == "DataDirectory":
      return self.data_dir
    if key == "CacheDirectory":
      return self.cache_dir
    if key == "ExcludeNodes":
      return self.exclude_nodes
    if key == "GeoIPExcludeUnknown":
      return self.exclude_unknown
    return default

  def set_conf(self, key, val):
    self.got_set_conf = True
    if key == "NumPrimaryGuards":
      raise stem.InvalidArguments()

  def save_conf(self):
    self.got_save_conf = True
    raise stem.OperationFailed("Bad")

  def get_info(self, key, default=None):
    if key in self.get_info_vals:
      return self.get_info_vals[key]
    else:
      return default

@pytest.mark.parametrize("missing", ["file", None, "Wme", "Wed", "zero-exits", "no-relays", "unknown-type"])
def test_unusable_consensus_preserves_state_and_recovers(tmp_path, missing):
  filename = "cached-microdesc-consensus"
  valid = (Path("tests") / filename).read_text()
  cache = tmp_path / filename
  cache.write_text(valid)
  state_file = tmp_path / "vanguards.state"
  controller = MockController()
  controller.data_dir = str(tmp_path)
  state = VanguardState(str(state_file))
  state.new_consensus_event(controller, None)
  previous_state = state_file.read_bytes()
  previous_counts = state.rendguard.use_counts
  layers = (state.layer2_guardset(), state.layer3_guardset())
  get_routers = controller.get_network_statuses

  if missing == "file":
    cache.unlink()
  elif missing == "unknown-type":
    cache.write_text("@type unsupported 1.0\n")
  elif missing == "no-relays":
    controller.get_network_statuses = lambda: []
  else:
    lines = []
    for line in valid.splitlines():
      if line.startswith("bandwidth-weights "):
        if missing is None:
          continue
        words = line.split()
        if missing == "zero-exits":
          words = [word.split("=", 1)[0] + "=0" if word.startswith(("Wee=", "Wed="))
                   else word for word in words]
        else:
          words = [word for word in words if not word.startswith(missing + "=")]
        line = " ".join(words)
      lines.append(line)
    cache.write_text("\n".join(lines) + "\n")
  controller.got_set_conf = False
  with pytest.raises(stem.DescriptorUnavailable):
    state.new_consensus_event(controller, None)
  state.new_consensus_event(controller, object())
  assert not controller.got_set_conf
  assert state_file.read_bytes() == previous_state
  assert state.rendguard.use_counts is previous_counts
  assert (state.layer2_guardset(), state.layer3_guardset()) == layers

  cache.write_text(valid)
  controller.get_network_statuses = get_routers
  state.new_consensus_event(controller, object())
  assert controller.got_set_conf
  assert state.rendguard.use_counts is not previous_counts

def test_consensus_uses_tor_cache_directory(tmp_path):
  shutil.copy("tests/cached-microdesc-consensus", tmp_path)
  controller = MockController()
  controller.data_dir = str(tmp_path / "unused")
  controller.cache_dir = str(tmp_path)
  state = VanguardState(str(tmp_path / "state"))
  state.new_consensus_event(controller, None)
  assert state.layer2 and controller.got_set_conf

def test_consensus_only_requires_weights_for_relays_in_pool():
  state = VanguardState("unused")
  state.enable_vanguards = False
  relay = SimpleNamespace(fingerprint="middle", flags=["Fast", "Valid"], measured=100)
  state.consensus_update([relay], {"Wmm": 10000}, None)
  assert state.rendguard.use_counts[relay.fingerprint].weight == 1

def test_rendguard_excludes_middle_only_relays_from_rendezvous_weights():
  state = VanguardState("unused")
  state.enable_vanguards = False
  eligible = SimpleNamespace(fingerprint="eligible", flags=["Fast", "Valid"], measured=100)
  middle_only = SimpleNamespace(fingerprint="middle_only",
                                flags=["Fast", "Valid", "MiddleOnly"], measured=100)
  state.consensus_update([eligible, middle_only], {"Wmm": 10000}, None)
  assert state.rendguard.use_counts[eligible.fingerprint].weight == 1
  assert state.rendguard.use_counts[middle_only.fingerprint].weight == 0

def test_new_vanguards():
  state = VanguardState("tests/state.mock2")

  # - Load a routerlist using stem
  routers = list(stem.descriptor.parse_file("tests/cached-microdesc-consensus",
                 document_handler =
                    stem.descriptor.DocumentHandler.ENTRIES))
  weights = get_consensus_weights("tests/cached-microdesc-consensus")

  # - Perform basic rank checks from sort_and_index
  (sorted_r, dict_r) = state.sort_and_index_routers(routers)
  for i in xrange(len(sorted_r)-1):
    assert sorted_r[i].measured >= sorted_r[i+1].measured

  state.consensus_update(routers, weights, ExcludeNodes(MockController()))
  sanity_check(state)

  replacement_checks(state, routers, weights)

def test_update_vanguards():
  controller = MockController()
  vanguards.vanguards.LAYER1_LIFETIME_DAYS = 30
  shutil.copy("tests/state.mock", "tests/state.mock.test")
  state = VanguardState.read_from_file("tests/state.mock.test")
  state.enable_vanguards = True
  sanity_check(state)

  state.new_consensus_event(controller, None)
  sanity_check(state)
  os.remove("tests/state.mock.test")

  # test signal HUP
  state.signal_event(controller,
                     ControlMessage.from_str("650 SIGNAL RELOAD\r\n",
                                             "EVENT"))
  sanity_check(state)

def test_excludenodes():
  controller = MockController()
  state = VanguardState("tests/state.mock2")

  # - Load a routerlist using stem
  routers = list(stem.descriptor.parse_file("tests/cached-microdesc-consensus",
                 document_handler =
                    stem.descriptor.DocumentHandler.ENTRIES))
  weights = get_consensus_weights("tests/cached-microdesc-consensus")
  (sorted_r, dict_r) = state.sort_and_index_routers(routers)

  state.consensus_update(routers, weights, ExcludeNodes(controller))
  sanity_check(state)

  #   * IP, CIDR, quad-mask
  controller.exclude_nodes = \
       str(dict_r[state.layer2[0].idhex].address)+","+\
       str(dict_r[state.layer2[1].idhex].address)+"/24,"+\
       str(dict_r[state.layer2[2].idhex].address)+"/255.255.255.0"
  removed2 = [state.layer2[0].idhex, state.layer2[1].idhex,
              state.layer2[2].idhex]

  for r in removed2:
    assert r in map(lambda x: x.idhex, state.layer2)
  state.consensus_update(routers, weights, ExcludeNodes(controller))
  sanity_check(state)
  for r in removed2:
    assert not r in map(lambda x: x.idhex, state.layer2)

  #   * GeoIP case mismatch
  controller.exclude_nodes = "{Us}"
  controller.exclude_unknown = "auto"
  controller.get_info_vals["ip-to-country/"+dict_r[state.layer2[1].idhex].address] = "us"
  controller.get_info_vals["ip-to-country/ipv4-available"] = "1"
  removed2 = state.layer2[1].idhex
  keep2 = state.layer2[0].idhex
  state.consensus_update(routers, weights, ExcludeNodes(controller))

  sanity_check(state)
  assert keep2 in map(lambda x: x.idhex, state.layer2)
  assert not removed2 in map(lambda x: x.idhex, state.layer2)

  #   * Nicks
  controller.exclude_nodes = \
       str(dict_r[state.layer2[0].idhex].nickname)

  removed2 = state.layer2[0].idhex
  keep2 = state.layer2[1].idhex
  state.consensus_update(routers, weights, ExcludeNodes(controller))
  sanity_check(state)
  assert not removed2 in map(lambda x: x.idhex, state.layer2)
  assert keep2 in map(lambda x: x.idhex, state.layer2)

  # FIXME: IPv6. Stem before 1.7.0 does not support IPv6 relays..

def test_disable():
  controller = MockController()
  vanguards.vanguards.LAYER1_LIFETIME_DAYS = 30
  shutil.copy("tests/state.mock", "tests/state.mock.test")
  state = VanguardState.read_from_file("tests/state.mock.test")
  state.enable_vanguards = False
  sanity_check(state)

  state.new_consensus_event(controller, None)
  sanity_check(state)
  assert controller.got_set_conf == False
  assert controller.got_save_conf == False
  os.remove("tests/state.mock.test")

