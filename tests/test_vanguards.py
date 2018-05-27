import stem
import time

from stem.response import ControlMessage

from vanguards.control import get_consensus_weights

import vanguards.vanguards
from vanguards.vanguards import VanguardState
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
  layer2_idhex = state.layer2[0].idhex
  layer3_idhex = state.layer3[0].idhex

  # - Remove a layer2 guard from it
  # - Remove a layer3 guard from it
  routers = list(filter(lambda x: x.fingerprint != layer2_idhex \
                         and x.fingerprint != layer3_idhex,
                   routers))

  state.consensus_update(routers, weights)
  sanity_check(state)
  assert state.layer2[0].idhex != layer2_idhex
  assert state.layer3[0].idhex != layer3_idhex

  layer2_idhex = state.layer2[1].idhex
  layer3_idhex = state.layer3[1].idhex

  # - Mark a layer2 guard way in the past
  # - Mark a layer3 guard way in the past
  state.layer2[1].expires_at = time.time() - 10
  state.layer3[1].expires_at = time.time() - 10

  state.consensus_update(routers, weights)
  sanity_check(state)
  assert state.layer2[0].idhex != layer2_idhex
  assert state.layer3[0].idhex != layer3_idhex

  # - Mark all guards way in the past
  for g in state.layer2:
    g.expires_at = time.time() - 10
  for g in state.layer3:
    g.expires_at = time.time() - 10

  state.consensus_update(routers, weights)
  sanity_check(state)

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
    pass

  # FIXME: os.path.join
  def get_network_statuses(self):
    return list(stem.descriptor.parse_file("tests/cached-microdesc-consensus",
                   document_handler =
                      stem.descriptor.DocumentHandler.ENTRIES))

  def get_conf(self, key):
    if key == "DataDirectory":
      return "tests"

  def set_conf(self, key, val):
    if key == "NumPrimaryGuards":
      raise stem.InvalidArguments()

  def save_conf(self):
    raise stem.OperationFailed("Bad")

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

  state.consensus_update(routers, weights)
  sanity_check(state)

  replacement_checks(state, routers, weights)

def test_update_vanguards():
  controller = MockController()
  vanguards.vanguards.LAYER1_LIFETIME_DAYS = 30
  state = VanguardState.read_from_file("tests/state.mock")
  sanity_check(state)

  state.new_consensus_event(controller, None)
  sanity_check(state)
