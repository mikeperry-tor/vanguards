import stem
import time

from stem.response import ControlMessage

from vanguards.rendguard import REND_USE_COUNT_START
from vanguards.rendguard import RendGuard

try:
  xrange
except NameError:
  xrange = range

class MockController:
  def __init__(self):
    self.closed_circ = None

  def close_circuit(self, circ_id):
    self.closed_circ = circ_id

def rend_circ(circ_id):
  ev_str = "650 CIRC "+str(circ_id)+" BUILT $5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed,$BBD9BAE1130F9F33F2F8449A2ED67F9A36853863~NovelThunder,$7791CA6B67303ACE46C2B6F5211206B765948147~v01d,$87C08DDFD32C62F3C56D371F9774D27BFDBB807B~Unnamed,$8C730EAF14903803BA1055202BE65C54105E5C4F~Unnamed BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE=HS_SERVICE_REND HS_STATE=HSSR_CONNECTING REND_QUERY=icqercdaxolm2ykx TIME_CREATED=2018-05-06T18:27:52.754441\r\n"
  return ControlMessage.from_str(ev_str, "EVENT")

# Test plan:
def test_usecounts():
  rg = RendGuard()
  c = MockController()

  i = 0
  while i < REND_USE_COUNT_START:
    rg.circ_event(c, rend_circ(i))
    assert c.closed_circ == None
    i += 1

  rg.circ_event(c, rend_circ(i))
  assert c.closed_circ == str(i)

  # XXX: Verify we're getting the right rend node

  # TODO: test scaling..
  assert True
