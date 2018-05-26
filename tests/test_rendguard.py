import stem
import time

from stem.response import ControlMessage

import vanguards.rendguard
from vanguards.rendguard import REND_USE_GLOBAL_START_COUNT
from vanguards.rendguard import REND_USE_SCALE_AT_COUNT
from vanguards.rendguard import RendGuard
from vanguards.vanguards import VanguardState

try:
  xrange
except NameError:
  xrange = range

class MockController:
  def __init__(self):
    self.closed_circ = None

  def close_circuit(self, circ_id):
    self.closed_circ = circ_id

  # FIXME: os.path.join
  def get_network_statuses(self):
    return list(stem.descriptor.parse_file("tests/cached-microdesc-consensus",
                   document_handler =
                      stem.descriptor.DocumentHandler.ENTRIES))

  def get_conf(self, key):
    if key == "DataDirectory":
      return "tests"

  # XXX: Test throw stem.InvalidArguments on NumPrimaryGuards
  def set_conf(self, key, val):
    pass

  def save_conf(self):
    pass

def rend_circ(circ_id):
  ev_str = "650 CIRC "+str(circ_id)+" BUILT $5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed,$BBD9BAE1130F9F33F2F8449A2ED67F9A36853863~NovelThunder,$87C08DDFD32C62F3C56D371F9774D27BFDBB807B~Unnamed,$8C730EAF14903803BA1055202BE65C54105E5C4F~Unnamed,$7791CA6B67303ACE46C2B6F5211206B765948147~v01d BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE=HS_SERVICE_REND HS_STATE=HSSR_CONNECTING REND_QUERY=icqercdaxolm2ykx TIME_CREATED=2018-05-06T18:27:52.754441\r\n"
  return ControlMessage.from_str(ev_str, "EVENT")

def rend_circ2(circ_id):
  ev_str = "650 CIRC "+str(circ_id)+" BUILT $5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed,$BBD9BAE1130F9F33F2F8449A2ED67F9A36853863~NovelThunder,$7791CA6B67303ACE46C2B6F5211206B765948147~v01d,$87C08DDFD32C62F3C56D371F9774D27BFDBB807B~Unnamed,$8C730EAF14903803BA1055202BE65C54105E5C4F~Unnamed BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE=HS_SERVICE_REND HS_STATE=HSSR_CONNECTING REND_QUERY=icqercdaxolm2ykx TIME_CREATED=2018-05-06T18:27:52.754441\r\n"
  return ControlMessage.from_str(ev_str, "EVENT")

def rend_circ3(circ_id):
  ev_str = "650 CIRC "+str(circ_id)+" BUILT $5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed,$BBD9BAE1130F9F33F2F8449A2ED67F9A36853863~NovelThunder,$7791CA6B67303ACE46C2B6F5211206B765948147~v01d,$87C08DDFD32C62F3C56D371F9774D27BFDBB807B~Unnamed,$8C730EAF14903803BA1055202BE65C54105E5C4E~Unnamed BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE=HS_SERVICE_REND HS_STATE=HSSR_CONNECTING REND_QUERY=icqercdaxolm2ykx TIME_CREATED=2018-05-06T18:27:52.754441\r\n"
  return ControlMessage.from_str(ev_str, "EVENT")


# Test plan:
def test_usecounts():
  rg = RendGuard()
  c = MockController()

  i = 0
  while i < REND_USE_GLOBAL_START_COUNT:
    rg.circ_event(c, rend_circ(i))
    assert c.closed_circ == None
    i += 1
    # Verify we're getting the right rend node
    assert rg.use_counts["7791CA6B67303ACE46C2B6F5211206B765948147"].used == i

  # Test circuit closing functionality
  c.closed_circ = None
  rg.circ_event(c, rend_circ(i))
  assert c.closed_circ == str(i)

  i += 1
  vanguards.rendguard.REND_USE_CLOSE_CIRCUITS_ON_OVERUSE = False
  c.closed_circ = None
  rg.circ_event(c, rend_circ(i))
  assert c.closed_circ == None
  vanguards.rendguard.REND_USE_CLOSE_CIRCUITS_ON_OVERUSE = True

  # Test scaling
  state = VanguardState("tests/junk")
  state.rendguard = rg
  i += 1
  while i < REND_USE_SCALE_AT_COUNT*1.5:
    rg.circ_event(c, rend_circ2(i))
    i += 1

  assert rg.total_use_counts == REND_USE_SCALE_AT_COUNT*1.5
  assert rg.use_counts["7791CA6B67303ACE46C2B6F5211206B765948147"].used == REND_USE_GLOBAL_START_COUNT+2

  state.new_consensus_event(c, None)
  assert rg.total_use_counts == REND_USE_SCALE_AT_COUNT*1.5/2
  assert rg.use_counts["7791CA6B67303ACE46C2B6F5211206B765948147"].used == (REND_USE_GLOBAL_START_COUNT+2)/2

  # Test leaving the consensus
  state = VanguardState("tests/junk")
  state.rendguard = rg
  i = 0
  while i < REND_USE_SCALE_AT_COUNT/10:
    rg.circ_event(c, rend_circ3(i))
    i += 1

  assert rg.total_use_counts == REND_USE_SCALE_AT_COUNT*1.5/2 + REND_USE_SCALE_AT_COUNT/10
  assert rg.use_counts["7791CA6B67303ACE46C2B6F5211206B765948147"].used == (REND_USE_GLOBAL_START_COUNT+2)/2

  state.new_consensus_event(c, None)

  assert rg.total_use_counts == REND_USE_SCALE_AT_COUNT*1.5/2
  assert rg.use_counts["7791CA6B67303ACE46C2B6F5211206B765948147"].used == (REND_USE_GLOBAL_START_COUNT+2)/2
