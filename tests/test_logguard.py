from stem.response import ControlMessage

from vanguards import logguard

import vanguards.logger
import time

vanguards.logger.loglevel = "INFO"

import stem.control
import stem.util.log
stem.util.log.LOGGER.setLevel("INFO")

from stem.response import ControlMessage

def log_event(level, message):
  s= "650 "+level+" "+message+"\r\n"
  return ControlMessage.from_str(s, "EVENT")

def closed_circ(circ_id):
  s = "650 CIRC "+str(circ_id)+" CLOSED $5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed,$855BC2DABE24C861CD887DB9B2E950424B49FC34~Logforme,$E8B3796C809853D9C8AF6B8EDE9080B6F2AE8005~BensTorRelay,$EAB114DAF0488F1223FF30778468E272E00EDC32~trnyc3 BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE=HS_CLIENT_REND HS_STATE=HSCR_JOINED REND_QUERY=4u56zw2g4uvyyq7i TIME_CREATED=2018-05-04T05:50:41.751938 REASON=FINISHED\r\n"
  return ControlMessage.from_str(s, "EVENT")

def failed_circ(circ_id):
  s = "650 CIRC "+str(circ_id)+" FAILED $5416F3E8F80101A133B1970495B04FDBD1C7446B~Unnamed,$855BC2DABE24C861CD887DB9B2E950424B49FC34~Logforme,$E8B3796C809853D9C8AF6B8EDE9080B6F2AE8005~BensTorRelay,$EAB114DAF0488F1223FF30778468E272E00EDC32~trnyc3 BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE=HS_CLIENT_REND HS_STATE=HSCR_JOINED REND_QUERY=4u56zw2g4uvyyq7i TIME_CREATED=2018-05-04T05:50:41.751938 REASON=REQUESTED\r\n"
  return ControlMessage.from_str(s, "EVENT")

class MockController:
  def __init__(self):
    self.closed_circ = None
    self.bwstats = None
    self.layer1 = []
    self.layer2 = []
    self.layer3 = []
    self._logguard = None

  def signal(self, sig):
    pass

  def close_circuit(self, circ_id):
    self.closed_circ = circ_id
    self.bwstats.circ_event(closed_circ(circ_id))
    raise stem.InvalidRequest("Coverage")

  def set_conf(self, key, val):
    pass

  def get_conf(self, key, default):
    if key == "HSLayer2Nodes":
      return ",".join(self.layer2)
    if key == "HSLayer3Nodes":
      return ",".join(self.layer3)

  def get_info(self, key):
    if key == "orconn-status":
      ret = ""
      for l in self.layer1:
        ret += "$"+l+"~Unnamed CONNECTED\n"
      return ret

  def add_event_listener(self, f, ev):
    pass

class MockEvent:
  def __init__(self, arrived_at):
    self.arrived_at = arrived_at

  def raw_content(self):
    return "nah"

def test_logguard():
  controller = MockController()

  #
  # Test init
  # 

  logguard.LOG_DUMP_LEVEL = "DEBUG"
  lg = logguard.LogGuard(controller)
  assert len(lg.log_buffer) == 0

  #
  # Test log events
  #

  lg.log_warn_event(log_event("WARN", "whatever"))
  assert len(lg.log_buffer) == 0

  lg.log_all_event(log_event("WARN", "whatever"))
  assert len(lg.log_buffer) == 1

  # Test closing circuit results in empty log
  lg.circ_event(failed_circ(2))
  assert len(lg.log_buffer) == 0

  # WARN should be logged by default
  lg.log_all_event(log_event("WARN", "whatever"))
  assert len(lg.log_buffer) == 1

  # Test closing circuit with empty log
  lg.circ_event(failed_circ(3))
  assert len(lg.log_buffer) == 0

  # Test over-filling logbuffer. Should never exceed limit
  for i in range(1, 2*logguard.LOG_DUMP_LIMIT):
    lg.log_all_event(log_event("WARN", "whatever"))

  assert len(lg.log_buffer) == logguard.LOG_DUMP_LIMIT

  # Test closing circuit with empty log
  lg.circ_event(failed_circ(3))
  assert len(lg.log_buffer) == 0

