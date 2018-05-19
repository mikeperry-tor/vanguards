import stem
import time
from math import floor, ceil

from vanguards.bandguards import BandwidthStats

from vanguards.bandguards import CIRC_MAX_HSDESC_KILOBYTES
from vanguards.bandguards import CIRC_MAX_MEGABYTES
from vanguards.bandguards import CIRC_MAX_AGE_HOURS
from vanguards.bandguards import CIRC_MAX_DROPPED_BYTES_PERCENT

from vanguards.bandguards import _CELL_PAYLOAD_SIZE
from vanguards.bandguards import _CELL_DATA_RATE
from vanguards.bandguards import _SECS_PER_HOUR
from vanguards.bandguards import _BYTES_PER_KB
from vanguards.bandguards import _BYTES_PER_MB

import vanguards.logger

vanguards.logger.loglevel = "WARN"

import stem.util.log
stem.util.log.LOGGER.setLevel("WARN")

from stem.response import ControlMessage

try:
  xrange
except NameError:
  xrange = range

class MockController:
  def __init__(self):
    self.closed_circ = None
    self.bwstats = None

  def close_circuit(self, circ_id):
    self.closed_circ = circ_id
    self.bwstats.circ_event(closed_circ(circ_id))

def built_circ(circ_id):
  s = "650 CIRC "+str(circ_id)+" BUILT $5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed,$1F9544C0A80F1C5D8A5117FBFFB50694469CC7F4~as44194l10501,$DBD67767640197FF96EC6A87684464FC48F611B6~nocabal,$387B065A38E4DAA16D9D41C2964ECBC4B31D30FF~redjohn1 BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE=HS_VANGUARDS TIME_CREATED=2018-05-04T06:09:32.751920\r\n"
  return ControlMessage.from_str(s, "EVENT")

def built_hsdir_circ(circ_id):
  s = "650 CIRC "+str(circ_id)+" BUILT $5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed,$1F9544C0A80F1C5D8A5117FBFFB50694469CC7F4~as44194l10501,$CFBBA0D858F02E40B1432A65F6D13C9BDFE7A46B~0x3d001,$81A59766272894D27FE8375C4F83A6BA453671EF~chutney BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY PURPOSE=HS_SERVICE_HSDIR HS_STATE=HSSI_CONNECTING TIME_CREATED=2018-05-04T06:08:59.886885\r\n"
  return ControlMessage.from_str(s, "EVENT")

def built_general_circ(circ_id):
  s = "650 CIRC "+str(circ_id)+"BUILT $5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed,$8101421BEFCCF4C271D5483C5AABCAAD245BBB9D~rofltor1,$FDAC8BA3ABFCC107D1B1EAC953F195BEEBA7FF54~Viking,$705DB1E61846652FC447E7EC2DDAE0F7D5407D9E~Unnamed BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY PURPOSE=GENERAL TIME_CREATED=2018-05-04T08:24:07.078225\r\n"
  return ControlMessage.from_str(s, "EVENT")

def failed_circ(circ_id):
  s =  "650 CIRC "+str(circ_id)+" FAILED $66CA5474346F35E375C4D4514C51A540545347EE~ToolspireRelay BUILD_FLAGS=IS_INTERNAL,NEED_UPTIME PURPOSE=HS_SERVICE_INTRO HS_STATE=HSSI_CONNECTING REND_QUERY=54dqclf77mj4qkzqjs372aozfykjcvkfrmzmzjkwyyiechicg2ssyfqd TIME_CREATED=2018-05-04T06:08:53.883058 REASON=FINISHED\r\n"
  return ControlMessage.from_str(s, "EVENT")

def closed_circ(circ_id):
  s =  "650 CIRC "+str(circ_id)+" CLOSED $5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed,$855BC2DABE24C861CD887DB9B2E950424B49FC34~Logforme,$E8B3796C809853D9C8AF6B8EDE9080B6F2AE8005~BensTorRelay,$EAB114DAF0488F1223FF30778468E272E00EDC32~trnyc3 BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE=HS_CLIENT_REND HS_STATE=HSCR_JOINED REND_QUERY=4u56zw2g4uvyyq7i TIME_CREATED=2018-05-04T05:50:41.751938 REASON=FINISHED\r\n"
  return ControlMessage.from_str(s, "EVENT")

def circ_bw(circ_id, read, sent, delivered_read, delivered_sent,
            overhead_read, overhead_sent):
  s = "650 CIRC_BW ID="+str(circ_id)+" READ="+str(int(read))+" WRITTEN="+str(int(sent))+" TIME=2018-05-04T06:08:55.751726 DELIVERED_READ="+str(int(delivered_read))+" OVERHEAD_READ="+str(int(overhead_read))+" DELIVERED_WRITTEN="+str(int(delivered_sent))+" OVERHEAD_WRITTEN="+str(int(overhead_sent))+"\r\n"
  return ControlMessage.from_str(s, "EVENT")

# Test plan:
def test_bwstats():
  global CIRC_MAX_DROPPED_BYTES_PERCENT
  controller = MockController()
  state = BandwidthStats(controller)
  controller.bwstats = state
  circ_id = 1

  # - BUILT -> FAILED,CLOSED removed from map
  # - BUILT -> CLOSED removed from map
  state.circ_event(built_circ(circ_id))
  assert str(circ_id) in state.circs
  state.circ_event(failed_circ(circ_id))
  assert str(circ_id) not in state.circs
  state.circ_event(closed_circ(circ_id))
  assert str(circ_id) not in state.circs

  circ_id += 1
  state.circ_event(built_circ(circ_id))
  assert str(circ_id) in state.circs
  state.circ_event(closed_circ(circ_id))
  assert str(circ_id) not in state.circs

  # - HSDIR size cap exceeded
  circ_id += 1
  controller.closed_circ = None
  state.circ_event(built_hsdir_circ(circ_id))

  read = 0
  while read < CIRC_MAX_HSDESC_KILOBYTES*_BYTES_PER_KB:
    state.circbw_event(circ_bw(circ_id, _CELL_PAYLOAD_SIZE, 0,
                               _CELL_DATA_RATE*_CELL_PAYLOAD_SIZE, 0, 0, 0))
    read += _CELL_PAYLOAD_SIZE
    assert controller.closed_circ == None

  state.circbw_event(circ_bw(circ_id, _CELL_PAYLOAD_SIZE, 0,
                             _CELL_DATA_RATE*_CELL_PAYLOAD_SIZE, 0, 0, 0))
  assert controller.closed_circ == str(circ_id)

  # - Max bytes exceed (read, write)
  circ_id += 1
  controller.closed_circ = None
  state.circ_event(built_circ(circ_id))

  read = 0
  while read+2000*_CELL_DATA_RATE*_CELL_PAYLOAD_SIZE < \
        CIRC_MAX_MEGABYTES*_BYTES_PER_MB:
    state.circbw_event(circ_bw(circ_id, 1000*_CELL_PAYLOAD_SIZE,
                               1000*_CELL_PAYLOAD_SIZE,
                               1000*_CELL_DATA_RATE*_CELL_PAYLOAD_SIZE, 0, 0, 0))
    read += 2000*_CELL_DATA_RATE*_CELL_PAYLOAD_SIZE
    assert controller.closed_circ == None

  state.circbw_event(circ_bw(circ_id, 2000*_CELL_PAYLOAD_SIZE, 0,
                             2000*_CELL_DATA_RATE*_CELL_PAYLOAD_SIZE, 0, 0, 0))
  assert controller.closed_circ == str(circ_id)

  # - Frob circ.created_at to close circ (bw event)
  circ_id += 1
  controller.closed_circ = None
  state.circ_event(built_circ(circ_id))
  state.bw_event(None)
  assert controller.closed_circ == None
  state.circs[str(circ_id)].created_at = time.time() - \
    (1+CIRC_MAX_AGE_HOURS*_SECS_PER_HOUR)
  state.bw_event(None)
  assert controller.closed_circ == str(circ_id)

  # - Read ratio exceeded (but writes are ignored)
  CIRC_MAX_DROPPED_BYTES_PERCENT /= 100.0
  circ_id += 1
  controller.closed_circ = None
  state.circ_event(built_circ(circ_id))

  # First read for a while (using the max as a token value) at a drop rate 50%
  # below our limit
  read = 0
  valid_bytes = 500*_CELL_DATA_RATE*(_CELL_PAYLOAD_SIZE*(1.0-CIRC_MAX_DROPPED_BYTES_PERCENT*0.5))/2
  while read < CIRC_MAX_MEGABYTES*1000:
    state.circbw_event(circ_bw(circ_id,
                               500*_CELL_PAYLOAD_SIZE, 500*_CELL_PAYLOAD_SIZE,
                               floor(valid_bytes), 0,
                               ceil(valid_bytes), 0))
    read += 500*_CELL_PAYLOAD_SIZE
    assert controller.closed_circ == None

  # Now read for a while (using the max as a token value) at a drop rate 50%
  # above our limit. This should bring us right up to our limit.
  read = 0
  valid_bytes = 500*_CELL_DATA_RATE*(_CELL_PAYLOAD_SIZE*(1.0-CIRC_MAX_DROPPED_BYTES_PERCENT*1.5))/2
  while read < CIRC_MAX_MEGABYTES*1000:
    state.circbw_event(circ_bw(circ_id, 500*_CELL_PAYLOAD_SIZE, 500*_CELL_PAYLOAD_SIZE,
                               floor(valid_bytes), 0,
                               ceil(valid_bytes), 0))
    read += 500*_CELL_PAYLOAD_SIZE
    assert controller.closed_circ == None

  state.circbw_event(circ_bw(circ_id, 500*_CELL_PAYLOAD_SIZE, 0,
                             floor(valid_bytes), 0,
                             ceil(valid_bytes), 0))

  assert controller.closed_circ == str(circ_id)

  # - Non-HS circs ignored:
  circ_id += 1
  state.circ_event(built_general_circ(circ_id))
  assert str(circ_id) not in state.circs
