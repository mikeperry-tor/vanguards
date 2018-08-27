import stem
import time
from math import floor, ceil

from vanguards.bandguards import BandwidthStats

from vanguards.bandguards import CIRC_MAX_HSDESC_KILOBYTES
from vanguards.bandguards import CIRC_MAX_MEGABYTES
from vanguards.bandguards import CIRC_MAX_AGE_HOURS
from vanguards.bandguards import CIRC_MAX_DROPPED_CELLS
from vanguards.bandguards import CIRC_MAX_DISCONNECTED_SECS
from vanguards.bandguards import CONN_MAX_DISCONNECTED_SECS

from vanguards.bandguards import _CELL_PAYLOAD_SIZE
from vanguards.bandguards import _CELL_DATA_RATE
from vanguards.bandguards import _SECS_PER_HOUR
from vanguards.bandguards import _BYTES_PER_KB
from vanguards.bandguards import _BYTES_PER_MB
from vanguards.bandguards import _MIN_BYTES_UNTIL_DROPS
from vanguards.bandguards import _MAX_PATH_BIAS_CELLS_CLIENT
from vanguards.bandguards import _MAX_PATH_BIAS_CELLS_SERVICE

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
    raise stem.InvalidRequest("Coverage")

  def get_info(self, key):
    if key == "orconn-status":
      return "$3E53D3979DB07EFD736661C934A1DED14127B684~Unnamed CONNECTED\n"+\
             "$3E53D3979DB07EFD736661C934A1DED14127B684~Unnamed LAUNCHED\n"+\
             "$3E53D3979DB07EFD736661C934A1DED14127B684~Unnamed CONNECTED"
    if key == "network-liveness":
      return "down"

class MockEvent:
  def __init__(self, arrived_at):
    self.arrived_at = arrived_at

def network_liveness_event(status):
  s= "650 NETWORK_LIVENESS "+status+"\r\n"
  return ControlMessage.from_str(s, "EVENT")

def orconn_event(conn_id, guard, status):
  s= "650 ORCONN "+guard+" "+status+" ID="+str(conn_id)+"\r\n"
  return ControlMessage.from_str(s, "EVENT")

def built_circ(circ_id, purpose, guard="$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed"):
  s = "650 CIRC "+str(circ_id)+" BUILT "+guard+",$1F9544C0A80F1C5D8A5117FBFFB50694469CC7F4~as44194l10501,$DBD67767640197FF96EC6A87684464FC48F611B6~nocabal,$387B065A38E4DAA16D9D41C2964ECBC4B31D30FF~redjohn1 BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE="+purpose+" TIME_CREATED=2018-05-04T06:09:32.751920\r\n"
  return ControlMessage.from_str(s, "EVENT")

def extended_circ(circ_id, purpose, guard="$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed"):
  s = "650 CIRC "+str(circ_id)+" EXTENDED "+guard+",$1F9544C0A80F1C5D8A5117FBFFB50694469CC7F4~as44194l10501,$DBD67767640197FF96EC6A87684464FC48F611B6~nocabal BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE="+purpose+" TIME_CREATED=2018-05-04T06:09:32.751920\r\n"
  return ControlMessage.from_str(s, "EVENT")

def purpose_changed_circ(circ_id, old_purpose, new_purpose,
                         guard="$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed"):
  s = "650 CIRC_MINOR "+str(circ_id)+" PURPOSE_CHANGED "+guard+",$1F9544C0A80F1C5D8A5117FBFFB50694469CC7F4~as44194l10501,$DBD67767640197FF96EC6A87684464FC48F611B6~nocabal,$387B065A38E4DAA16D9D41C2964ECBC4B31D30FF~redjohn1 BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE="+new_purpose+" OLD_PURPOSE="+old_purpose+" TIME_CREATED=2018-05-04T06:09:32.751920\r\n"
  return ControlMessage.from_str(s, "EVENT")

def cannibalized_circ(circ_id, to_purpose):
  s = "650 CIRC_MINOR "+str(circ_id)+" CANNIBALIZED $FA255D3F828FBBA47FF4848343A92BAEE21B92E7~TorWay1,$6FF440DFB1D0697B942357D747900CC308DD57CC~atlantis,$C86C538EF0A24E010342F30DBCACC2A7EB7CA833~eowyn,$7964E5822260C5129AFDF291853F56D83283A448~lol BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE="+to_purpose+" HS_STATE=HSSI_CONNECTING TIME_CREATED=2018-05-08T17:02:36.905840 OLD_PURPOSE=HS_VANGUARDS OLD_TIME_CREATED=2018-05-08T17:02:37.943660\r\n"
  return ControlMessage.from_str(s, "EVENT")

def built_hsdir_circ(circ_id):
  s = "650 CIRC "+str(circ_id)+" BUILT $5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed,$1F9544C0A80F1C5D8A5117FBFFB50694469CC7F4~as44194l10501,$CFBBA0D858F02E40B1432A65F6D13C9BDFE7A46B~0x3d001,$81A59766272894D27FE8375C4F83A6BA453671EF~chutney BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY PURPOSE=HS_SERVICE_HSDIR HS_STATE=HSSI_CONNECTING TIME_CREATED=2018-05-04T06:08:59.886885\r\n"
  return ControlMessage.from_str(s, "EVENT")

def built_general_circ(circ_id, guard="$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed"):
  s = "650 CIRC "+str(circ_id)+" BUILT "+guard+",$8101421BEFCCF4C271D5483C5AABCAAD245BBB9D~rofltor1,$FDAC8BA3ABFCC107D1B1EAC953F195BEEBA7FF54~Viking,$705DB1E61846652FC447E7EC2DDAE0F7D5407D9E~Unnamed BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY PURPOSE=GENERAL TIME_CREATED=2018-05-04T08:24:07.078225\r\n"
  return ControlMessage.from_str(s, "EVENT")

def failed_circ(circ_id):
  s =  "650 CIRC "+str(circ_id)+" FAILED $66CA5474346F35E375C4D4514C51A540545347EE~ToolspireRelay BUILD_FLAGS=IS_INTERNAL,NEED_UPTIME PURPOSE=HS_SERVICE_INTRO HS_STATE=HSSI_CONNECTING REND_QUERY=54dqclf77mj4qkzqjs372aozfykjcvkfrmzmzjkwyyiechicg2ssyfqd TIME_CREATED=2018-05-04T06:08:53.883058 REASON=FINISHED\r\n"
  return ControlMessage.from_str(s, "EVENT")

def closed_circ(circ_id):
  s =  "650 CIRC "+str(circ_id)+" CLOSED $5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed,$855BC2DABE24C861CD887DB9B2E950424B49FC34~Logforme,$E8B3796C809853D9C8AF6B8EDE9080B6F2AE8005~BensTorRelay,$EAB114DAF0488F1223FF30778468E272E00EDC32~trnyc3 BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE=HS_CLIENT_REND HS_STATE=HSCR_JOINED REND_QUERY=4u56zw2g4uvyyq7i TIME_CREATED=2018-05-04T05:50:41.751938 REASON=FINISHED\r\n"
  return ControlMessage.from_str(s, "EVENT")

def destroyed_circ(circ_id, guard):
  s =  "650 CIRC "+str(circ_id)+" CLOSED "+guard+",$855BC2DABE24C861CD887DB9B2E950424B49FC34~Logforme,$E8B3796C809853D9C8AF6B8EDE9080B6F2AE8005~BensTorRelay,$EAB114DAF0488F1223FF30778468E272E00EDC32~trnyc3 BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE=HS_CLIENT_REND HS_STATE=HSCR_JOINED REND_QUERY=4u56zw2g4uvyyq7i TIME_CREATED=2018-05-04T05:50:41.751938 REASON=DESTROYED REMOTE_REASON=CHANNEL_CLOSED\r\n"
  return ControlMessage.from_str(s, "EVENT")

def circ_bw(circ_id, read, sent, delivered_read, delivered_sent,
            overhead_read, overhead_sent):
  s = "650 CIRC_BW ID="+str(circ_id)+" READ="+str(int(read))+" WRITTEN="+str(int(sent))+" TIME=2018-05-04T06:08:55.751726 DELIVERED_READ="+str(int(delivered_read))+" OVERHEAD_READ="+str(int(overhead_read))+" DELIVERED_WRITTEN="+str(int(delivered_sent))+" OVERHEAD_WRITTEN="+str(int(overhead_sent))+"\r\n"
  return ControlMessage.from_str(s, "EVENT")

def check_hsdir(state, controller, circ_id):
  read = _CELL_PAYLOAD_SIZE
  while read < CIRC_MAX_HSDESC_KILOBYTES*_BYTES_PER_KB:
    state.circbw_event(circ_bw(circ_id, _CELL_PAYLOAD_SIZE, 0,
                               _CELL_DATA_RATE*_CELL_PAYLOAD_SIZE, 0, 0, 0))
    read += _CELL_PAYLOAD_SIZE
    assert controller.closed_circ == None

  state.circbw_event(circ_bw(circ_id, _CELL_PAYLOAD_SIZE, 0,
                             _CELL_DATA_RATE*_CELL_PAYLOAD_SIZE, 0, 0, 0))

def check_maxbytes(state, controller, circ_id):
  read = 0
  while read+2000*_CELL_PAYLOAD_SIZE < \
        CIRC_MAX_MEGABYTES*_BYTES_PER_MB:
    state.circbw_event(circ_bw(circ_id, 1000*_CELL_PAYLOAD_SIZE,
                               1000*_CELL_PAYLOAD_SIZE,
                               1000*_CELL_DATA_RATE*_CELL_PAYLOAD_SIZE, 0, 0, 0))
    read += 2000*_CELL_PAYLOAD_SIZE
    assert controller.closed_circ == None

  state.circbw_event(circ_bw(circ_id, 2000*_CELL_PAYLOAD_SIZE, 0,
                             2000*_CELL_DATA_RATE*_CELL_PAYLOAD_SIZE, 0, 0, 0))

def check_dropped_bytes(state, controller, circ_id,
                        delivered_cells, dropped_cells):
  # First read for a while with no dropped bytes
  read = 0
  valid_bytes = _CELL_DATA_RATE*_CELL_PAYLOAD_SIZE/2
  while read < delivered_cells:
    state.circbw_event(circ_bw(circ_id,
                               _CELL_PAYLOAD_SIZE, _CELL_PAYLOAD_SIZE,
                               floor(valid_bytes), 0,
                               ceil(valid_bytes), 0))
    read += 1
    assert controller.closed_circ == None

  # Now get some dropped cells
  read = 0
  while read < dropped_cells:
    assert controller.closed_circ == None
    state.circbw_event(circ_bw(circ_id, _CELL_PAYLOAD_SIZE,
                               _CELL_PAYLOAD_SIZE,
                               0, 0, 0, 0))
    read += 1

# Test plan:
def test_bwstats():
  global CIRC_MAX_DROPPED_CELLS
  global CIRC_MAX_MEGABYTES
  controller = MockController()
  state = BandwidthStats(controller)
  controller.bwstats = state
  circ_id = 1

  # - BUILT -> FAILED,CLOSED removed from map
  # - BUILT -> CLOSED removed from map
  state.circ_event(built_circ(circ_id, "HS_VANGUARDS"))
  assert str(circ_id) in state.circs
  state.circ_event(failed_circ(circ_id))
  assert str(circ_id) not in state.circs
  state.circ_event(closed_circ(circ_id))
  assert str(circ_id) not in state.circs

  circ_id += 1
  state.circ_event(built_circ(circ_id, "HS_VANGUARDS"))
  assert str(circ_id) in state.circs
  state.circ_event(closed_circ(circ_id))
  assert str(circ_id) not in state.circs

  # - HSDIR size cap exceeded for direct service circ
  circ_id += 1
  controller.closed_circ = None
  state.circ_event(built_hsdir_circ(circ_id))
  assert state.circs[str(circ_id)].is_hsdir == True
  assert state.circs[str(circ_id)].is_service == True
  check_hsdir(state, controller, circ_id)
  assert controller.closed_circ == str(circ_id)

  # - HSDIR size cap exceeded for cannibalized circ
  circ_id += 1
  controller.closed_circ = None
  state.circ_event(built_circ(circ_id, "HS_VANGUARDS"))
  assert state.circs[str(circ_id)].is_hsdir == False
  state.circ_minor_event(cannibalized_circ(circ_id, "HS_CLIENT_HSDIR"))
  assert state.circs[str(circ_id)].is_hsdir == True
  assert state.circs[str(circ_id)].is_service == False
  check_hsdir(state, controller, circ_id)
  assert controller.closed_circ == str(circ_id)

  # - HSDIR size cap disabled
  circ_id += 1
  controller.closed_circ = None
  state.circ_event(built_hsdir_circ(circ_id))
  vanguards.bandguards.CIRC_MAX_HSDESC_KILOBYTES = 0
  assert vanguards.bandguards.CIRC_MAX_HSDESC_KILOBYTES != CIRC_MAX_HSDESC_KILOBYTES
  assert state.circs[str(circ_id)].is_hsdir == True
  assert state.circs[str(circ_id)].is_service == True
  check_hsdir(state, controller, circ_id)
  assert controller.closed_circ == None
  vanguards.bandguards.CIRC_MAX_HSDESC_KILOBYTES = CIRC_MAX_HSDESC_KILOBYTES

  # - Max bytes exceed (read, write)
  circ_id += 1
  controller.closed_circ = None
  vanguards.bandguards.CIRC_MAX_MEGABYTES = 100
  CIRC_MAX_MEGABYTES = 100
  state.circ_event(built_circ(circ_id, "HS_VANGUARDS"))
  check_maxbytes(state, controller, circ_id)
  assert controller.closed_circ == str(circ_id)

  # - Max bytes disabled
  circ_id += 1
  controller.closed_circ = None
  state.circ_event(built_circ(circ_id, "HS_SERVICE_REND"))
  vanguards.bandguards.CIRC_MAX_MEGABYTES = 0
  assert vanguards.bandguards.CIRC_MAX_MEGABYTES != CIRC_MAX_MEGABYTES
  check_maxbytes(state, controller, circ_id)
  assert controller.closed_circ == None
  vanguards.bandguards.CIRC_MAX_MEGABYTES = CIRC_MAX_MEGABYTES

  # - Frob circ.created_at to close circ (bw event)
  circ_id += 1
  controller.closed_circ = None
  state.circ_event(built_circ(circ_id, "HS_CLIENT_REND"))
  state.bw_event(MockEvent(time.time()))
  assert controller.closed_circ == None
  state.circs[str(circ_id)].created_at = time.time() - \
    (1+CIRC_MAX_AGE_HOURS*_SECS_PER_HOUR)
  state.bw_event(MockEvent(time.time()))
  assert controller.closed_circ == str(circ_id)

  # - Test disabled circ lifetime
  circ_id += 1
  controller.closed_circ = None
  state.circ_event(built_circ(circ_id, "HS_CLIENT_REND"))
  state.bw_event(MockEvent(time.time()))
  assert controller.closed_circ == None
  vanguards.bandguards.CIRC_MAX_AGE_HOURS = 0
  assert vanguards.bandguards.CIRC_MAX_AGE_HOURS != CIRC_MAX_AGE_HOURS
  state.circs[str(circ_id)].created_at = time.time() - \
    (1+CIRC_MAX_AGE_HOURS*_SECS_PER_HOUR)
  state.bw_event(MockEvent(time.time()))
  assert controller.closed_circ == None

  # Test that regular reading is ok
  circ_id += 1
  controller.closed_circ = None
  state.circ_event(built_circ(circ_id, "HS_VANGUARDS"))
  check_dropped_bytes(state, controller, circ_id, 100, 0)
  assert controller.closed_circ == None

  # Test that no dropped cells are allowed before app data
  circ_id += 1
  controller.closed_circ = None
  state.circ_event(built_circ(circ_id, "HS_VANGUARDS"))
  check_dropped_bytes(state, controller, circ_id, 0, 1)
  assert controller.closed_circ == str(circ_id)

  # Test that 1 dropped cell is allowed on pathbias
  circ_id += 1
  controller.closed_circ = None
  state.circ_event(built_circ(circ_id, "HS_SERVICE_REND"))
  state.circ_minor_event(purpose_changed_circ(circ_id,
                                             "HS_SERVICE_REND",
                                             "PATH_BIAS_TESTING"))
  path_bias_cells = 0
  while path_bias_cells < _MAX_PATH_BIAS_CELLS_SERVICE:
    check_dropped_bytes(state, controller, circ_id, 0, 1)
    assert controller.closed_circ == None
    path_bias_cells += 1
  check_dropped_bytes(state, controller, circ_id, 0, 1)
  assert controller.closed_circ == str(circ_id)

  # Test that 1 dropped cell is allowed on pathbias
  circ_id += 1
  controller.closed_circ = None
  state.circ_event(built_circ(circ_id, "HS_CLIENT_REND"))
  state.circ_minor_event(purpose_changed_circ(circ_id,
                                             "HS_CLIENT_REND",
                                             "PATH_BIAS_TESTING"))
  path_bias_cells = 0
  while path_bias_cells < _MAX_PATH_BIAS_CELLS_CLIENT:
    check_dropped_bytes(state, controller, circ_id, 0, 1)
    assert controller.closed_circ == None
    path_bias_cells += 1
  check_dropped_bytes(state, controller, circ_id, 0, 1)
  assert controller.closed_circ == str(circ_id)

  # Test that no dropped cells are allowed on not-built circ.
  circ_id += 1
  controller.closed_circ = None
  state.circ_event(extended_circ(circ_id, "HS_VANGUARDS"))
  check_dropped_bytes(state, controller, circ_id, 0, 1)
  assert controller.closed_circ == str(circ_id)

  # Test that after app data, up to CIRC_MAX_DROPPED_CELLS
  # allowed, and then we close.
  circ_id += 1
  controller.closed_circ = None
  state.circ_event(built_circ(circ_id, "HS_VANGUARDS"))
  check_dropped_bytes(state, controller, circ_id,
                      1000, CIRC_MAX_DROPPED_CELLS+1)
  assert controller.closed_circ == str(circ_id)

  # - Non-HS circs ignored:
  circ_id += 1
  state.circ_event(built_general_circ(circ_id))
  assert str(circ_id) not in state.circs

def test_connguard():
  controller = MockController()
  state = BandwidthStats(controller)
  controller.bwstats = state
  circ_id = 1

  # Check orconn-status
  assert len(state.live_guard_conns) == 2
  assert state.max_fake_id == 2
  assert state.live_guard_conns["0"].to_guard == "3E53D3979DB07EFD736661C934A1DED14127B684"
  assert "1" not in state.live_guard_conns
  assert state.live_guard_conns["2"].to_guard == "3E53D3979DB07EFD736661C934A1DED14127B684"

  # Test HS_INTRO close with an extra circ on it.
  assert state.circs_destroyed_total == 0
  state.orconn_event(
         orconn_event(11,"$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed",
                      "CONNECTED"))
  state.circ_event(built_circ(23, "HS_SERVICE_INTRO",
                              "$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed"))
  state.circ_event(built_circ(24, "HS_SERVICE_INTRO",
                              "$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed"))
  state.orconn_event(
         orconn_event(11,"$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed",
                      "CLOSED"))
  state.circ_event(destroyed_circ(24,
                    "$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed"))
  state.circ_event(destroyed_circ(23,
                   "$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed"))
  assert state.guards["5416F3E8F80101A133B1970495B04FDBD1C7446B"].killed_conns == 1
  assert state.circs_destroyed_total == 2

  # Test cannibalized close
  assert state.circs_destroyed_total == 2
  state.orconn_event(
         orconn_event(12,"$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed",
                      "CONNECTED"))
  state.circ_event(built_circ(24, "HS_VANGUARDS",
                              "$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed"))
  state.circ_minor_event(purpose_changed_circ(24, "HS_VANGUARDS", "HS_SERVICE_REND",
                              "$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed"))
  state.orconn_event(
         orconn_event(12,"$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed",
                      "CLOSED"))
  state.circ_event(destroyed_circ(24,
                    "$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed"))
  assert state.guards["5416F3E8F80101A133B1970495B04FDBD1C7446B"].killed_conns == 2
  assert state.circs_destroyed_total == 3

  # Test cannibalized close on pre-existing conn
  assert state.circs_destroyed_total == 3
  state.circ_event(built_circ(2323, "HS_VANGUARDS",
                              "$3E53D3979DB07EFD736661C934A1DED14127B684~Unnamed"))
  state.circ_minor_event(purpose_changed_circ(2323, "HS_VANGUARDS", "HS_SERVICE_REND",
                              "$3E53D3979DB07EFD736661C934A1DED14127B684~Unnamed"))
  assert not state.circs["2323"].possibly_destroyed_at
  assert state.circs["2323"].in_use
  state.orconn_event(
         orconn_event(5,"$3E53D3979DB07EFD736661C934A1DED14127B684~Unnamed",
                      "CLOSED"))
  assert state.circs["2323"].possibly_destroyed_at
  state.circ_event(destroyed_circ(2323,
                    "$3E53D3979DB07EFD736661C934A1DED14127B684~Unnamed"))
  assert state.guards["5416F3E8F80101A133B1970495B04FDBD1C7446B"].killed_conns == 2
  assert state.guards["3E53D3979DB07EFD736661C934A1DED14127B684"].killed_conns == 1
  assert state.circs_destroyed_total == 4

  # Tests that should not trigger logs:
  #  * Test HS_VANGUARDS
  assert state.circs_destroyed_total == 4
  state.orconn_event(
         orconn_event(13,"$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed",
                      "CONNECTED"))
  state.circ_event(built_circ(25, "HS_VANGUARDS",
                              "$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed"))
  state.orconn_event(
         orconn_event(13,"$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed",
                      "CLOSED"))
  state.circ_event(destroyed_circ(25,
                    "$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed"))
  assert state.guards["5416F3E8F80101A133B1970495B04FDBD1C7446B"].killed_conns == 2
  assert state.circs_destroyed_total == 4

  #  * Test general close
  assert state.circs_destroyed_total == 4
  state.orconn_event(
         orconn_event(14,"$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed",
                      "CONNECTED"))
  state.circ_event(built_general_circ(26,
                              "$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed"))
  state.orconn_event(
         orconn_event(14,"$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed",
                      "CLOSED"))
  state.circ_event(destroyed_circ(26,
                    "$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed"))
  assert state.guards["5416F3E8F80101A133B1970495B04FDBD1C7446B"].killed_conns == 2
  assert state.circs_destroyed_total == 4

  #  * Test late close of hs_intro
  assert state.circs_destroyed_total == 4
  state.orconn_event(
         orconn_event(15,"$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed",
                      "CONNECTED"))
  state.circ_event(built_circ(27, "HS_SERVICE_INTRO",
                              "$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed"))
  state.orconn_event(
         orconn_event(15,"$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed",
                      "CLOSED"))
  ev = destroyed_circ(27,
                    "$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed")
  ev.arrived_at = time.time()+5
  state.circ_event(ev)
  assert state.guards["5416F3E8F80101A133B1970495B04FDBD1C7446B"].killed_conns == 2
  assert state.circs_destroyed_total == 4

  #  * Different guard for hs_intro
  assert state.circs_destroyed_total == 4
  state.orconn_event(
         orconn_event(16,"$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed",
                      "CONNECTED"))
  state.circ_event(built_circ(28, "HS_SERVICE_INTRO",
                              "$6416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed"))
  state.orconn_event(
         orconn_event(16,"$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed",
                      "CLOSED"))
  state.circ_event(destroyed_circ(28,
                    "$6416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed"))
  assert state.guards["5416F3E8F80101A133B1970495B04FDBD1C7446B"].killed_conns == 2
  assert state.circs_destroyed_total == 4

  # Test orconn-status fake_id clearing, esp with launched
  assert len(state.live_guard_conns) == 1
  assert not state.no_conns_since
  ev = orconn_event(6,
                      "$3E53D3979DB07EFD736661C934A1DED14127B684~Unnamed",
                      "CLOSED")
  last_conn = int(time.time())
  ev.arrived_at = last_conn
  state.orconn_event(ev)
  assert state.no_conns_since == last_conn
  assert len(state.live_guard_conns) == 0

  # Test no orconns for 5, 10 seconds
  ev = MockEvent(last_conn)
  state.bw_event(ev)
  assert state.disconnected_conns == False
  ev = MockEvent(last_conn+CONN_MAX_DISCONNECTED_SECS*2)
  state.bw_event(ev)
  assert state.disconnected_conns

  # Test come back to life.
  state.orconn_event(
         orconn_event(15,"$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed",
                      "CONNECTED"))
  last_conn = int(time.time())
  ev = MockEvent(last_conn)
  state.bw_event(ev)
  assert state.disconnected_conns == False

  # Test disabled
  vanguards.bandguards.CONN_MAX_DISCONNECTED_SECS = 0
  assert CONN_MAX_DISCONNECTED_SECS # Didn't change local val
  ev = MockEvent(last_conn+CONN_MAX_DISCONNECTED_SECS*2)
  state.bw_event(ev)
  assert state.disconnected_conns == False
  vanguards.bandguards.CONN_MAX_DISCONNECTED_SECS = CONN_MAX_DISCONNECTED_SECS

  # Test no circuits for 5, 10 seconds
  state.orconn_event(
         orconn_event(9001,"$5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed",
                      "CONNECTED"))
  ev = MockEvent(last_conn+20)
  state.bw_event(ev)

  ev = built_general_circ(29)
  ev.arrived_at = last_conn
  state.circ_event(ev)
  assert state.no_circs_since == None
  state.bw_event(ev)
  assert state.disconnected_circs == False
  assert state.disconnected_conns == False

  # Quiet doesn't mean no network
  ev.arrived_at = last_conn+CIRC_MAX_DISCONNECTED_SECS*2
  state.bw_event(ev)
  assert state.no_circs_since == None
  assert state.disconnected_circs == False

  # Failure then quiet doesn't, when no circs:
  ev = failed_circ(31)
  ev.arrived_at = last_conn
  state.circ_event(ev)
  assert state.no_circs_since == None
  assert state.disconnected_circs == False
  ev.arrived_at = last_conn+CIRC_MAX_DISCONNECTED_SECS*2
  state.bw_event(ev)
  assert state.disconnected_circs == False

  # Failure then quiet does, when no circs:
  ev = extended_circ(333, "HS_VANGUARDS")
  ev.arrived_at = last_conn
  state.circ_event(ev)
  ev.arrived_at = last_conn+CIRC_MAX_DISCONNECTED_SECS*2
  state.bw_event(ev)
  assert state.no_circs_since == None
  assert state.disconnected_circs == False
  ev = failed_circ(31)
  ev.arrived_at = last_conn
  state.circ_event(ev)
  ev = network_liveness_event("DOWN")
  ev.arrived_at = last_conn
  state.network_liveness_event(ev)
  assert state.no_circs_since
  assert state.network_down_since
  ev.arrived_at = last_conn+CIRC_MAX_DISCONNECTED_SECS*2
  state.bw_event(ev)
  assert state.disconnected_circs == True

  # Success clears it
  ev = built_general_circ(32)
  ev.arrived_at = last_conn
  state.circ_event(ev)
  ev = network_liveness_event("UP")
  ev.arrived_at = last_conn
  state.network_liveness_event(ev)
  assert state.no_circs_since == None
  assert state.network_down_since == None
  state.bw_event(ev)
  assert state.disconnected_circs == False

  # Failure then success is also ok
  ev = failed_circ(34)
  ev.arrived_at = last_conn
  state.circ_event(ev)
  assert state.no_circs_since
  assert state.disconnected_circs == False
  ev.arrived_at = last_conn+CIRC_MAX_DISCONNECTED_SECS*2
  state.bw_event(ev)
  assert state.disconnected_circs == True
  ev = extended_circ(35, "GENERAL")
  ev.arrived_at = last_conn
  state.circ_event(ev)
  assert state.no_circs_since == None
  ev.arrived_at = last_conn+CIRC_MAX_DISCONNECTED_SECS*2
  state.bw_event(ev)
  assert state.disconnected_circs == False

  # Failure then circbw is also ok
  ev = failed_circ(34)
  ev.arrived_at = last_conn
  state.circ_event(ev)
  assert state.no_circs_since
  assert state.disconnected_circs == False
  ev.arrived_at = last_conn+CIRC_MAX_DISCONNECTED_SECS*2
  state.bw_event(ev)
  assert state.disconnected_circs == True
  check_dropped_bytes(state, controller, 23, 1, 0)
  assert state.no_circs_since == None
  ev.arrived_at = last_conn+CIRC_MAX_DISCONNECTED_SECS*2
  state.bw_event(ev)
  assert state.disconnected_circs == False

  # Test disabled
  vanguards.bandguards.CIRC_MAX_DISCONNECTED_SECS = 0
  assert CIRC_MAX_DISCONNECTED_SECS # Didn't change local val
  ev = failed_circ(313)
  ev.arrived_at = last_conn
  state.circ_event(ev)
  assert state.no_circs_since
  assert state.disconnected_circs == False
  ev.arrived_at = last_conn+CIRC_MAX_DISCONNECTED_SECS*2
  state.bw_event(ev)
  assert state.disconnected_circs == False
  vanguards.bandguards.CIRC_MAX_DISCONNECTED_SECS = CIRC_MAX_DISCONNECTED_SECS



# Collection of tests that mostly just ensure coverage
def test_coverage():
  controller = MockController()
  state = BandwidthStats(controller)
  controller.bwstats = state
  circ_id = 1

  # Stray circ_minor event
  state.circ_minor_event(cannibalized_circ(circ_id, "HS_SERVICE_REND"))
  assert str(circ_id) not in state.circs

  # Insane bw values
  circ_id += 1
  controller.closed_circ = None
  state.circ_event(built_circ(circ_id, "HS_VANGUARDS"))
  state.circbw_event(circ_bw(circ_id, _CELL_PAYLOAD_SIZE, _CELL_PAYLOAD_SIZE,
                             _CELL_PAYLOAD_SIZE, _CELL_PAYLOAD_SIZE, 0, 0))

