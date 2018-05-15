import stem
import time

from vanguards.vanguards import VanguardState, get_consensus_weights
from vanguards.vanguards import SEC_PER_HOUR

from vanguards.config import NUM_LAYER3_GUARDS
from vanguards.config import NUM_LAYER2_GUARDS
from vanguards.config import MIN_LAYER3_LIFETIME
from vanguards.config import MAX_LAYER3_LIFETIME
from vanguards.config import MIN_LAYER2_LIFETIME
from vanguards.config import MAX_LAYER2_LIFETIME
from vanguards.config import USE_COUNT_TOTAL_MIN

from stem.response import ControlMessage

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
    assert g.expires_at - g.chosen_at < MAX_LAYER2_LIFETIME*SEC_PER_HOUR
    assert g.expires_at - g.chosen_at >= MIN_LAYER2_LIFETIME*SEC_PER_HOUR

  for g in state.layer3:
    assert g.expires_at - g.chosen_at < MAX_LAYER3_LIFETIME*SEC_PER_HOUR
    assert g.expires_at - g.chosen_at >= MIN_LAYER3_LIFETIME*SEC_PER_HOUR

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
    pass

  def save_conf(self):
    pass

def test_new_vanguards():
  state = VanguardState()

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
  state = VanguardState.read_from_file(open("tests/state.mock", "rb"))
  sanity_check(state)

  state.new_consensus_event(controller, None)
  sanity_check(state)

# Test plan:
def test_usecounts():
  state = VanguardState.read_from_file(open("tests/state.mock", "rb"))
  sanity_check(state)

  i = 0
  while i < USE_COUNT_TOTAL_MIN:
    ev_str = "650 CIRC "+str(i)+" BUILT $5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed,$BBD9BAE1130F9F33F2F8449A2ED67F9A36853863~NovelThunder,$7791CA6B67303ACE46C2B6F5211206B765948147~v01d,$87C08DDFD32C62F3C56D371F9774D27BFDBB807B~Unnamed,$8C730EAF14903803BA1055202BE65C54105E5C4F~Unnamed BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE=HS_SERVICE_REND HS_STATE=HSSR_CONNECTING REND_QUERY=icqercdaxolm2ykx TIME_CREATED=2018-05-06T18:27:52.754441\r\n"
    ev = ControlMessage.from_str(ev_str, "EVENT")
    assert state.rendwatcher.valid_rend_use(ev.purpose, ev.path)
    i += 1

  ev = ControlMessage.from_str(ev_str, "EVENT")
  assert not state.rendwatcher.valid_rend_use(ev.purpose, ev.path)

  # TODO: test scaling..
  assert True
