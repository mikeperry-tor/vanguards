""" Simple checks against bandwidth side channels """
import time
import stem
from logger import plog

############ Constants ###############
# Every circuit takes about this much non-app data to set up. Subtract it from
# the dropped bytes total (includes construction, sendme's, introduce, etc)
CIRC_SETUP_BYTES = 10000
CELL_PAYLOAD_SIZE = 509
RELAY_HEADER_SIZE = 11
CELL_DATA_RATE = (float(CELL_PAYLOAD_SIZE-RELAY_HEADER_SIZE)/CELL_PAYLOAD_SIZE)

############ Options #################

##### Per-circuit limits #########

# Kill a circuit if this much bandwidth is not application related.
# This prevents an adversary from inserting cells that are silently dropped
# into a circuit, to use as a timing side channel.
BW_CIRC_MAX_DROPPED_READ_RATIO = 0.05
BW_CIRC_ENFORCE_RATIO_AFTER = CIRC_SETUP_BYTES

# Kill a circuit if this many read+write bytes have been exceeded.
# Very loud application circuits could be used to introduce timing
# side channels.
# Warning: if your application has large resources that cannot be
# split up over multipe requests (such as large HTTP posts for eg:
# securedrop), you must set this higher.
BW_CIRC_MAX_BYTES = 100*1024*1024 # 100M

# Kill circuits older than this many seconds.
# Really old circuits will continue to use old guards after the TLS connection
# has rotated, which means they will be alone on old TLS links. This lack
# of multiplexing may allow an adversary to use netflow records to determine
# the path through the Tor network to a hidden service.
BW_CIRC_MAX_AGE = 24*60*60 # 1 day

# Maximum size for an hsdesc fetch (including setup+get+dropped cells)
BW_CIRC_MAX_HSDESC_BYTES = 30*1024 # 30k

class BwCircuitStat:
  def __init__(self, circ_id, is_hs):
    self.circ_id = circ_id
    self.is_hs = is_hs
    self.is_service = 1
    self.is_hsdir = 0
    self.created_at = time.time()
    self.read_bytes = 0
    self.sent_bytes = 0
    self.delivered_read_bytes = 0
    self.delivered_sent_bytes = 0
    self.overhead_read_bytes = 0
    self.overhead_sent_bytes = 0

  def total_bytes(self):
    return self.read_bytes + self.sent_bytes

  def app_bytes(self):
    return self.delivered_read_bytes + self.delivered_sent_bytes

  def overhead_bytes(self):
    return self.overhead_read_bytes + self.overhead_sent_bytes

  def dropped_bytes(self):
    return self.total_bytes() - (self.app_bytes()+self.overhead_bytes())

  def dropped_bytes_extra(self):
    return max(CIRC_SETUP_BYTES,self.dropped_bytes())-CIRC_SETUP_BYTES

  def dropped_ratio(self):
    return self.dropped_bytes_extra()/self.total_bytes()

class BandwidthStats:
  def __init__(self, controller):
    self.controller = controller
    self.circs = {}
    self.has_control_support = True

  def circ_event(self, event):
    if not self.has_control_support: return
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
        if event.purpose == "HS_CLIENT_HSDIR" or \
           event.purpose == "HS_SERVICE_HSDIR":
          self.circs[event.id].is_hsdir = 1

  def circbw_event(self, event):
    if not self.has_control_support: return
    if not "DELIVERED_READ" in event.keyword_args:
      plog("NOTICE", "In order for bandwidth-based protections to be "+
                     "enabled, you must use Tor 0.3.4.0-alpha or newer.")
      self.has_control_support = False

    if event.id in self.circs:
      plog("DEBUG", event.raw_content())
      delivered_read = int(event.keyword_args["DELIVERED_READ"])
      delivered_written = int(event.keyword_args["DELIVERED_WRITTEN"])
      overhead_read = int(event.keyword_args["OVERHEAD_READ"])
      overhead_written = int(event.keyword_args["OVERHEAD_WRITTEN"])

      if delivered_read + overhead_read > event.read*CELL_DATA_RATE:
        plog("ERROR",
             "Application read data exceeds cell data:"+event.raw_content());
      if delivered_written + overhead_written > event.written*CELL_DATA_RATE:
        plog("ERROR",
             "Application written data exceeds cell data:"+event.raw_content());

      self.circs[event.id].read_bytes += event.read*CELL_DATA_RATE
      self.circs[event.id].sent_bytes += event.written*CELL_DATA_RATE

      self.circs[event.id].delivered_read_bytes += delivered_read
      self.circs[event.id].delivered_sent_bytes += delivered_written

      self.circs[event.id].overhead_read_bytes += overhead_read
      self.circs[event.id].overhead_sent_bytes += overhead_written

      self.check_circuit_limits(self.circs[event.id])

  def bw_event(self, event):
    now = time.time()
    # Unused except to expire circuits -- 1x/sec
    for circ in self.circs.values():
      if now - circ.created_at > BW_CIRC_MAX_AGE:
        self.limit_exceeded("NOTICE", "BW_CIRC_MAX_AGE",
                            circ.circ_id,
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
    if circ.total_bytes() > BW_CIRC_ENFORCE_RATIO_AFTER \
       and circ.dropped_ratio() > BW_CIRC_MAX_DROPPED_READ_RATIO:
      self.limit_exceeded("WARN", "BW_CIRC_MAX_DROPPED_READ_RATIO",
                          circ.circ_id,
                          circ.dropped_ratio(),
                          BW_CIRC_MAX_DROPPED_READ_RATIO,
                          "Total: "+str(circ.total_bytes())+\
                          ", dropped: "+str(circ.dropped_bytes()))
      self.try_close_circuit(circ.circ_id)
    if circ.total_bytes() > BW_CIRC_MAX_BYTES:
      self.limit_exceeded("NOTICE", "BW_CIRC_MAX_BYTES",
                          circ.circ_id,
                          circ.total_bytes(),
                          BW_CIRC_MAX_BYTES)
      self.try_close_circuit(circ.circ_id)
    if circ.is_hsdir and circ.total_bytes() > BW_CIRC_MAX_HSDESC_BYTES:
      self.limit_exceeded("WARN", "BW_CIRC_MAX_HSDESC_BYTES",
                          circ.circ_id,
                          circ.total_bytes(),
                          BW_CIRC_MAX_HSDESC_BYTES)
      self.try_close_circuit(circ.circ_id)

  def limit_exceeded(self, level, str_name, circ_id, cur_val, max_val, extra=""):
    # XXX: Rate limit this log
    plog(level, "Circ "+str(circ_id)+" exceeded "+str_name+": "+str(cur_val)+
                  " > "+str(max_val)+". "+extra)
