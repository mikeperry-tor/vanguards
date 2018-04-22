""" Simple checks against bandwidth side channels """
import time
import stem
from logger import plog

# Constants
CELL_PAYLOAD_SIZE = 509
RELAY_HEADER_SIZE = 11
CELL_DATA_RATE = (float(CELL_PAYLOAD_SIZE-RELAY_HEADER_SIZE)/CELL_PAYLOAD_SIZE)


###### Global limits ###########

# Enforce global ratios after this many bytes
BW_ENFORCE_RATIOS_AFTER = 10*1024*1024 # Ten megabytes

# Emit a warn if this ratio of read/total bytes is exceeded.
# Clients (web-like) should not write more than 20% of their bytes
# Servers (web-like) should not read more than 20% of their bytes
BW_MAX_CLIENT_WRITE_RATIO = 0.30
BW_MAX_SERVICE_READ_RATIO = 0.30

# Emit a warn if this much bandwidth is not stream related.
# (This should be roughly 1.0 minus Tor's "packed cell rate" log messages
BW_MAX_CLIENT_NONSTREAM_READ_RATIO = 0.30
BW_MAX_SERVICE_NONSTREAM_SENT_RATIO = 0.30
BW_MAX_SERVICE_NONSTREAM_READ_RATIO = 0.90
BW_MAX_CLIENT_NONSTREAM_SENT_RATIO = 0.90

###### Per-circuit limits #########

# Enforce per-circuit ratios after this many bytes
BW_CIRC_ENFORCE_RATIOS_AFTER = 100*1024 # 100k

# Kill a circuit if this ratio of read/total bytes is exceeded
BW_CIRC_MAX_CLIENT_WRITE_RATIO = 0.30
BW_CIRC_MAX_SERVICE_READ_RATIO = 0.30

# Kill a circuit if this much bandwidth is not stream related
BW_CIRC_MAX_CLIENT_NONSTREAM_READ_RATIO = 0.30
BW_CIRC_MAX_SERVICE_NONSTREAM_SENT_RATIO = 0.30
BW_CIRC_MAX_SERVICE_NONSTREAM_READ_RATIO = 0.90
BW_CIRC_MAX_CLIENT_NONSTREAM_SENT_RATIO = 0.90

# Kill a circuit if this many read or write bytes have been exceeded
BW_CIRC_MAX_CLIENT_READ_BYTES = 20*1024*1024 # 20 megabytes
BW_CIRC_MAX_CLIENT_SENT_BYTES = 25*1024 # 25k
BW_CIRC_MAX_SERVICE_READ_BYTES = 25*1024 # 25k
BW_CIRC_MAX_SERVICE_SENT_BYTES = 20*1024*1024 # 20 megabytes

# Kill circuits older than this many seconds
BW_CIRC_MAX_AGE = 60*60 # 1 hour

# TODO: Max bytes for hsdesc posts or fetches

class BwCircuitStat:
  def __init__(self, circ_id, is_hs):
    self.circ_id = circ_id
    self.is_hs = is_hs
    self.is_service = 1
    self.created_at = time.time()
    self.read_bytes = 0
    self.sent_bytes = 0
    self.stream_read_bytes = 0
    self.stream_sent_bytes = 0

  def byte_count(self):
    return self.read_bytes+self.sent_bytes

  def read_ratio(self):
    return float(self.read_bytes)/self.byte_count()

  def sent_ratio(self):
    return float(self.sent_bytes)/self.byte_count()

  def nonstream_read_ratio(self):
    return float(self.read_bytes - self.stream_read_bytes)/self.read_bytes

  def nonstream_sent_ratio(self):
    return float(self.sent_bytes - self.stream_sent_bytes)/self.sent_bytes


class BandwidthStats:
  def __init__(self, controller):
    self.controller = controller
    self.circs = {}
    self.circs_for_stream = {}
    self.client_circ_read = 0
    self.client_circ_sent = 0
    self.client_stream_read = 0
    self.client_stream_sent = 0
    self.service_circ_read = 0
    self.service_circ_sent = 0
    self.service_stream_read = 0
    self.service_stream_sent = 0

  def circ_event(self, event):
    if event.status == stem.CircStatus.FAILED or \
       event.status == stem.CircStatus.CLOSED:
      if event.id in self.circs:
        plog("DEBUG", "Closed hs circ for "+event.raw_content())
        del self.circs[event.id]
    else:
      if event.hs_state or event.purpose[0:2] == "HS":
        if event.id not in self.circs:
          self.circs[event.id] = BwCircuitStat(event.id, 1)
          plog("DEBUG", "Added hs circ for "+event.raw_content())
        if event.purpose[0:9] == "HS_CLIENT":
          self.circs[event.id].is_service = 0
        elif event.purpose[0:10] == "HS_SERVICE":
          self.circs[event.id].is_service = 1

  def circbw_event(self, event):
    if event.id in self.circs:
      plog("DEBUG", event.raw_content())
      self.circs[event.id].read_bytes += event.read*CELL_DATA_RATE
      self.circs[event.id].sent_bytes += event.written*CELL_DATA_RATE

      if self.circs[event.id].is_service:
        self.service_circ_read += event.read*CELL_DATA_RATE
        self.service_circ_sent += event.written*CELL_DATA_RATE
      else:
        self.client_circ_read += event.read*CELL_DATA_RATE
        self.client_circ_sent += event.written*CELL_DATA_RATE

      self.check_circuit_limits(self.circs[event.id])
      self.check_global_limits()

  def stream_event(self, event):
    if event.status == stem.StreamStatus.FAILED or \
       event.status == stem.StreamStatus.DETACHED or \
       event.status == stem.StreamStatus.CLOSED:
      if event.id in self.circs_for_stream:
        del self.circs_for_stream[event.id]
        plog("DEBUG", "Forgetting circ for stream: "+event.raw_content())
    elif event.circ_id and event.id not in self.circs_for_stream and \
         event.circ_id in self.circs:
      self.circs_for_stream[event.id] = self.circs[event.circ_id]
      plog("DEBUG", "Mapping circ for stream: "+event.raw_content())

  def streambw_event(self, event):
    if event.id in self.circs_for_stream:
      plog("DEBUG", event.raw_content())

      self.circs_for_stream[event.id].stream_read_bytes += event.read
      self.circs_for_stream[event.id].stream_sent_bytes += event.written

      if self.circs_for_stream[event.id].is_service:
        self.service_stream_read += event.read
        self.service_stream_sent += event.written
      else:
        self.client_stream_read += event.read
        self.client_stream_sent += event.written

      self.check_circuit_limits(self.circs_for_stream[event.id])
      self.check_global_limits()

  def bw_event(self, event):
    now = time.time()
    # Unused except to expire circuits -- 1x/sec
    for circ in self.circs.values():
      if now - circ.created_at > BW_CIRC_MAX_AGE:
        self.limit_exceeded("NOTICE", "BW_CIRC_MAX_AGE",
                            now - circ.created_at,
                            BW_CIRC_MAX_AGE)
        self.try_close_circuit(circ.circ_id)

  def try_close_circuit(self, circ_id):
    try:
      self.controller.close_circuit(circ_id)
      plog("NOTICE", "We force-closed circuit "+str(circ_id))
    except stem.InvalidRequest as e:
      plog("INFO", "Failed to close circuit "+str(circ_id)+": "+str(e.message))

  def check_circuit_limits(self, circ):
    if not circ.is_hs: return
    if circ.byte_count() > BW_CIRC_ENFORCE_RATIOS_AFTER:
      if circ.is_service:
        if circ.nonstream_read_ratio() > BW_CIRC_MAX_SERVICE_NONSTREAM_READ_RATIO:
          self.limit_exceeded("WARN", "BW_CIRC_MAX_SERVICE_NONSTREAM_READ_RATIO",
                              circ.nonstream_read_ratio(),
                              BW_CIRC_MAX_SERVICE_NONSTREAM_READ_RATIO)
          self.try_close_circuit(circ.circ_id)
        if circ.nonstream_sent_ratio() > BW_CIRC_MAX_SERVICE_NONSTREAM_SENT_RATIO:
          self.limit_exceeded("WARN", "BW_CIRC_MAX_SERVICE_NONSTREAM_SENT_RATIO",
                              circ.nonstream_sent_ratio(),
                              BW_CIRC_MAX_SERVICE_NONSTREAM_SENT_RATIO)
          self.try_close_circuit(circ.circ_id)
        if circ.read_ratio() > BW_CIRC_MAX_SERVICE_READ_RATIO:
          self.limit_exceeded("WARN", "BW_CIRC_MAX_SERVICE_READ_RATIO",
                              circ.read_ratio(),
                              BW_CIRC_MAX_SERVICE_READ_RATIO)
          self.try_close_circuit(circ.circ_id)
        if circ.read_bytes > BW_CIRC_MAX_SERVICE_READ_BYTES:
          self.limit_exceeded("NOTICE", "BW_CIRC_MAX_SERVICE_READ_BYTES",
                              circ.read_bytes,
                              BW_CIRC_MAX_SERVICE_READ_BYTES)
          self.try_close_circuit(circ.circ_id)
        if circ.sent_bytes > BW_CIRC_MAX_SERVICE_SENT_BYTES:
          self.limit_exceeded("NOTICE", "BW_CIRC_MAX_SERVICE_SENT_BYTES",
                              circ.sent_bytes,
                              BW_CIRC_MAX_SERVICE_SENT_BYTES)
          self.try_close_circuit(circ.circ_id)
      else:
        if circ.nonstream_read_ratio() > BW_CIRC_MAX_CLIENT_NONSTREAM_READ_RATIO:
          self.limit_exceeded("WARN", "BW_CIRC_MAX_CLIENT_NONSTREAM_READ_RATIO",
                              circ.nonstream_read_ratio(),
                              BW_CIRC_MAX_CLIENT_NONSTREAM_READ_RATIO)
          self.try_close_circuit(circ.circ_id)
        if circ.nonstream_sent_ratio() > BW_CIRC_MAX_CLIENT_NONSTREAM_SENT_RATIO:
          self.limit_exceeded("WARN", "BW_CIRC_MAX_CLIENT_NONSTREAM_SENT_RATIO",
                              circ.nonstream_sent_ratio(),
                              BW_CIRC_MAX_CLIENT_NONSTREAM_SENT_RATIO)
          self.try_close_circuit(circ.circ_id)
        if circ.sent_ratio() > BW_CIRC_MAX_CLIENT_WRITE_RATIO:
          self.limit_exceeded("WARN", "BW_CIRC_MAX_CLIENT_WRITE_RATIO",
                              circ.sent_ratio(),
                              BW_CIRC_MAX_CLIENT_WRITE_RATIO)
          self.try_close_circuit(circ.circ_id)
        if circ.read_bytes > BW_CIRC_MAX_CLIENT_READ_BYTES:
          self.limit_exceeded("NOTICE", "BW_CIRC_MAX_CLIENT_READ_BYTES",
                              circ.read_bytes,
                              BW_CIRC_MAX_CLIENT_READ_BYTES)
          self.try_close_circuit(circ.circ_id)
        if circ.sent_bytes > BW_CIRC_MAX_CLIENT_SENT_BYTES:
          self.limit_exceeded("NOTICE", "BW_CIRC_MAX_CLIENT_SENT_BYTES",
                              circ.sent_bytes,
                              BW_CIRC_MAX_CLIENT_SENT_BYTES)
          self.try_close_circuit(circ.circ_id)

  def client_byte_count(self):
    return (self.client_circ_read+self.client_circ_sent)

  def service_byte_count(self):
    return (self.service_circ_read+self.service_circ_sent)

  def total_byte_count(self):
    return self.client_byte_count()+self.service_byte_count()

  def total_stream_sent(self):
    return self.client_stream_sent+self.service_stream_sent

  def total_stream_read(self):
    return self.client_stream_read+self.service_stream_read

  def total_circ_read(self):
    return self.client_circ_read+self.service_circ_read

  def total_circ_sent(self):
    return self.client_circ_sent+self.service_circ_sent

  def client_write_ratio(self):
    return float(self.client_circ_sent)/self.client_byte_count()

  def service_read_ratio(self):
    return float(self.service_circ_read)/self.service_byte_count()

  def service_nonstream_read_ratio(self):
    return float(self.service_circ_read-self.service_stream_read) / \
                 self.service_circ_read

  def client_nonstream_read_ratio(self):
    return float(self.client_circ_read-self.client_stream_read) / \
                 self.client_circ_read

  def service_nonstream_sent_ratio(self):
    return float(self.service_circ_sent-self.service_stream_sent) / \
           self.service_circ_sent

  def client_nonstream_sent_ratio(self):
    return float(self.client_circ_sent-self.client_stream_sent) / \
           self.client_circ_sent

  def limit_exceeded(self, level, str_name, cur_val, max_val):
    # XXX: Rate limit this log
    plog(level, "The "+str_name+" was exceeded: "+str(cur_val)+
                  " > "+str(max_val))

  def check_global_limits(self):
    if self.total_byte_count() >= BW_ENFORCE_RATIOS_AFTER:
      if self.client_write_ratio() > BW_MAX_CLIENT_WRITE_RATIO:
        self.limit_exceeded("WARN", "BW_MAX_CLIENT_WRITE_RATIO",
                                 self.client_write_ratio(),
                                 BW_MAX_CLIENT_WRITE_RATIO)
      if self.service_read_ratio() > BW_MAX_SERVICE_READ_RATIO:
        self.limit_exceeded("WARN", "BW_MAX_SERVICE_READ_RATIO",
                                 self.service_read_ratio(),
                                 BW_MAX_SERVICE_READ_RATIO)
      if self.client_nonstream_read_ratio() > BW_MAX_CLIENT_NONSTREAM_READ_RATIO:
        self.limit_exceeded("WARN", "BW_MAX_CLIENT_NONSTREAM_READ_RATIO",
                                  self.client_nonstream_read_ratio(),
                                  BW_MAX_CLIENT_NONSTREAM_READ_RATIO)
      if self.service_nonstream_read_ratio() > BW_MAX_SERVICE_NONSTREAM_READ_RATIO:
        self.limit_exceeded("WARN", "BW_MAX_SERVICE_NONSTREAM_READ_RATIO",
                                  self.service_nonstream_read_ratio(),
                                  BW_MAX_SERVICE_NONSTREAM_READ_RATIO)
      if self.client_nonstream_sent_ratio() > BW_MAX_CLIENT_NONSTREAM_SENT_RATIO:
        self.limit_exceeded("WARN", "BW_MAX_CLIENT_NONSTREAM_SENT_RATIO",
                                  self.client_nonstream_sent_ratio(),
                                  BW_MAX_CLIENT_NONSTREAM_SENT_RATIO)
      if self.service_nonstream_sent_ratio() > BW_MAX_SERVICE_NONSTREAM_SENT_RATIO:
        self.limit_exceeded("WARN", "BW_MAX_SERVICE_NONSTREAM_SENT_RATIO",
                                  self.service_nonstream_sent_ratio(),
                                  BW_MAX_SERVICE_NONSTREAM_SENT_RATIO)
