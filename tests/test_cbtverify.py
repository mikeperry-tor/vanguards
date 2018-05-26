from stem.response import ControlMessage

from vanguards.cbtverify import TimeoutStats

def launched_general_circ(circ_id):
  s = "650 CIRC "+str(circ_id)+" LAUNCHED BUILD_FLAGS=ONEHOP_TUNNEL,IS_INTERNAL,NEED_CAPACITY PURPOSE=GENERAL TIME_CREATED=2018-05-13T00:05:18.651833\r\n"
  return ControlMessage.from_str(s, "EVENT")

def launched_hs_circ(circ_id):
  s = "650 CIRC "+str(circ_id)+" LAUNCHED BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE=HS_VANGUARDS TIME_CREATED=2018-05-08T17:03:14.906877\r\n"
  return ControlMessage.from_str(s, "EVENT")

def built_circ(circ_id):
  s = "650 CIRC "+str(circ_id)+" BUILT $5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed,$1F9544C0A80F1C5D8A5117FBFFB50694469CC7F4~as44194l10501,$DBD67767640197FF96EC6A87684464FC48F611B6~nocabal,$387B065A38E4DAA16D9D41C2964ECBC4B31D30FF~redjohn1 BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE=HS_VANGUARDS TIME_CREATED=2018-05-04T06:09:32.751920\r\n"
  return ControlMessage.from_str(s, "EVENT")

def failed_circ(circ_id):
  s =  "650 CIRC "+str(circ_id)+" FAILED $66CA5474346F35E375C4D4514C51A540545347EE~ToolspireRelay BUILD_FLAGS=IS_INTERNAL,NEED_UPTIME PURPOSE=HS_SERVICE_INTRO HS_STATE=HSSI_CONNECTING REND_QUERY=54dqclf77mj4qkzqjs372aozfykjcvkfrmzmzjkwyyiechicg2ssyfqd TIME_CREATED=2018-05-04T06:08:53.883058 REASON=FINISHED\r\n"
  return ControlMessage.from_str(s, "EVENT")

def closed_circ(circ_id):
  s = "650 CIRC "+str(circ_id)+" CLOSED $5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed,$855BC2DABE24C861CD887DB9B2E950424B49FC34~Logforme,$E8B3796C809853D9C8AF6B8EDE9080B6F2AE8005~BensTorRelay,$EAB114DAF0488F1223FF30778468E272E00EDC32~trnyc3 BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE=HS_CLIENT_REND HS_STATE=HSCR_JOINED REND_QUERY=4u56zw2g4uvyyq7i TIME_CREATED=2018-05-04T05:50:41.751938 REASON=FINISHED\r\n"
  return ControlMessage.from_str(s, "EVENT")

def timeout_circ(circ_id):
  s = "650 CIRC "+str(circ_id)+" FAILED $3E53D3979DB07EFD736661C934A1DED14127B684~Unnamed,$BBD9BAE1130F9F33F2F8449A2ED67F9A36853863~NovelThunder,$E3F98C86C9E01138DD8EA06B1E660A0CDB4B2782~Finisterre BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE=HS_VANGUARDS TIME_CREATED=2018-05-08T16:14:45.612809 REASON=TIMEOUT\r\n"
  return ControlMessage.from_str(s, "EVENT")

def expired_circ(circ_id):
  s = "650 CIRC "+str(circ_id)+" FAILED $3E53D3979DB07EFD736661C934A1DED14127B684~Unnamed,$BBD9BAE1130F9F33F2F8449A2ED67F9A36853863~NovelThunder,$E3F98C86C9E01138DD8EA06B1E660A0CDB4B2782~Finisterre BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE=MEASURE_TIMEOUT TIME_CREATED=2018-05-08T16:14:45.612809 REASON=MEASUREMENT_EXPIRED\r\n"
  return ControlMessage.from_str(s, "EVENT")

def cbt():
  s = "650 BUILDTIMEOUT_SET COMPUTED TOTAL_TIMES=1000 TIMEOUT_MS=2320 XM=1885 ALPHA=7.740810 CUTOFF_QUANTILE=0.800000 TIMEOUT_RATE=0.059891 CLOSE_MS=60000 CLOSE_RATE=0.030248\r\n"
  return ControlMessage.from_str(s, "EVENT")

# Test plan:
#  - Make 10 hs circs, 2 timeouts + 1 expired, verify 80%
#  - Make 10 circuits, 1 timeouts, verify 85%; verify no change to hs
#  - Verify failed circuits don't impact rates
#  - Make builttimeout event
def test_cbt():
  ts = TimeoutStats()
  assert ts.timeout_rate_hs() == 0.0
  assert ts.timeout_rate_all() == 0.0

  i = 0
  while i < 8:
    i += 1
    ts.circ_event(launched_hs_circ(i))
    ts.circ_event(built_circ(i))

  i += 1
  ts.circ_event(launched_hs_circ(i))
  ts.circ_event(timeout_circ(i))
  ts.circ_event(expired_circ(i))
  i += 1
  ts.circ_event(launched_hs_circ(i))
  ts.circ_event(timeout_circ(i))
  assert ts.timeout_rate_hs() == 0.2
  assert ts.timeout_rate_all() == 0.2
  assert i == 10

  while i < 19:
    i += 1
    ts.circ_event(launched_general_circ(i))
    ts.circ_event(built_circ(i))

  i += 1
  ts.circ_event(launched_general_circ(i))
  ts.circ_event(timeout_circ(i))
  assert ts.timeout_rate_hs() == 0.2
  assert ts.timeout_rate_all() == 0.15
  assert i == 20

  i+=1
  ts.circ_event(launched_general_circ(i))
  ts.circ_event(failed_circ(i))
  i+=1
  ts.circ_event(launched_hs_circ(i))
  ts.circ_event(failed_circ(i))
  assert ts.timeout_rate_hs() == 0.2
  assert ts.timeout_rate_all() == 0.15

  i+=1
  ts.circ_event(launched_general_circ(i))
  ts.circ_event(closed_circ(i))
  i+=1
  ts.circ_event(launched_hs_circ(i))
  ts.circ_event(closed_circ(i))
  assert ts.timeout_rate_hs() == 0.2
  assert ts.timeout_rate_all() == 0.15

  ts.cbt_event(cbt())

  # Cover double-launch:
  i+=1
  ts.circ_event(launched_hs_circ(i))
  ts.circ_event(launched_hs_circ(i))
