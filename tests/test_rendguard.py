import stem
import time

from stem.response import ControlMessage

import vanguards.rendguard
from vanguards.rendguard import REND_USE_GLOBAL_START_COUNT
from vanguards.rendguard import REND_USE_RELAY_START_COUNT
from vanguards.rendguard import REND_USE_SCALE_AT_COUNT
from vanguards.rendguard import REND_USE_MAX_USE_TO_BW_RATIO
from vanguards.rendguard import REND_USE_MAX_CONSENSUS_WEIGHT_CHURN
from vanguards.rendguard import RendGuard
from vanguards.vanguards import VanguardState
from vanguards.rendguard import _NOT_IN_CONSENSUS_ID

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

  def get_info(self, key, default=None):
    return default

  def set_conf(self, key, val):
    pass

  def save_conf(self):
    pass

def rend_circ(circ_id):
  ev_str = "650 CIRC "+str(circ_id)+" BUILT $5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed,$BBD9BAE1130F9F33F2F8449A2ED67F9A36853863~NovelThunder,$87C08DDFD32C62F3C56D371F9774D27BFDBB807B~Unnamed,$8C730EAF14903803BA1055202BE65C54105E5C4F~Unnamed,$7791CA6B67303ACE46C2B6F5211206B765948147~v01d BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE=HS_SERVICE_REND HS_STATE=HSSR_CONNECTING REND_QUERY=icqercdaxolm2ykx TIME_CREATED=2018-05-06T18:27:52.754441\r\n"
  return ControlMessage.from_str(ev_str, "EVENT")

def rend_circ2(circ_id):
  ev_str = "650 CIRC "+str(circ_id)+" BUILT $5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed,$BBD9BAE1130F9F33F2F8449A2ED67F9A36853863~NovelThunder,$7791CA6B67303ACE46C2B6F5211206B765948147~v01d,$87C08DDFD32C62F3C56D371F9774D27BFDBB807B~Unnamed,$BC630CBBB518BE7E9F4E09712AB0269E9DC7D626~Unnamed BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE=HS_SERVICE_REND HS_STATE=HSSR_CONNECTING REND_QUERY=icqercdaxolm2ykx TIME_CREATED=2018-05-06T18:27:52.754441\r\n"
  return ControlMessage.from_str(ev_str, "EVENT")

def rend_circ3(circ_id):
  ev_str = "650 CIRC "+str(circ_id)+" BUILT $5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed,$BBD9BAE1130F9F33F2F8449A2ED67F9A36853863~NovelThunder,$7791CA6B67303ACE46C2B6F5211206B765948147~v01d,$87C08DDFD32C62F3C56D371F9774D27BFDBB807B~Unnamed,$8C730EAF14903803BA1055202BE65C54105E5C4E~Unnamed BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE=HS_SERVICE_REND HS_STATE=HSSR_CONNECTING REND_QUERY=icqercdaxolm2ykx TIME_CREATED=2018-05-06T18:27:52.754441\r\n"
  return ControlMessage.from_str(ev_str, "EVENT")


# Test plan:
def test_usecounts():
  rg = RendGuard()
  c = MockController()

  # First test not in consensus
  i = 1
  while i < REND_USE_GLOBAL_START_COUNT:
    rg.circ_event(c, rend_circ(i))
    assert c.closed_circ == None
    # Verify we're getting the right rend node
    assert rg.use_counts[_NOT_IN_CONSENSUS_ID].used == i
    i += 1

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

  # Test use limit with an in-consensus relay
  state = VanguardState("tests/junk")
  state.rendguard = rg
  state.new_consensus_event(c, None)
  r = 1
  while r < REND_USE_RELAY_START_COUNT:
    rg.circ_event(c, rend_circ2(i))
    assert c.closed_circ == None
    i += 1
    r += 1

  # Test closing in-consensus relay
  while rg.use_counts["BC630CBBB518BE7E9F4E09712AB0269E9DC7D626"].used < \
          rg.use_counts["BC630CBBB518BE7E9F4E09712AB0269E9DC7D626"].weight \
           * rg.total_use_counts * REND_USE_MAX_USE_TO_BW_RATIO:
    assert c.closed_circ == None
    rg.circ_event(c, rend_circ2(i))
    r += 1
    i += 1

  assert c.closed_circ == str(i-1)

  # Test almost-scaling with an in-consensus relay
  while i < REND_USE_SCALE_AT_COUNT-1:
    rg.circ_event(c, rend_circ2(i))
    i += 1
    r += 1

  state.new_consensus_event(c, None)
  assert rg.total_use_counts == REND_USE_SCALE_AT_COUNT-1
  assert rg.use_counts[_NOT_IN_CONSENSUS_ID].used + \
         rg.use_counts["BC630CBBB518BE7E9F4E09712AB0269E9DC7D626"].used \
            == rg.total_use_counts

  # Test scaling with in-consensus relay
  rg.circ_event(c, rend_circ2(i))
  state.new_consensus_event(c, None)
  assert rg.total_use_counts == REND_USE_SCALE_AT_COUNT/2
  assert rg.use_counts[_NOT_IN_CONSENSUS_ID].used + \
         rg.use_counts["BC630CBBB518BE7E9F4E09712AB0269E9DC7D626"].used \
            == rg.total_use_counts
