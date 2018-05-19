""" Simple checks against bandwidth side channels """
import time
import stem

from .logger import plog

############ BandGuard Options #################

# Kill a circuit if this much received bandwidth is not application related.
# This prevents an adversary from inserting cells that are silently dropped
# into a circuit, to use as a timing side channel.
CIRC_MAX_DROPPED_BYTES_PERCENT = 2.5

# Kill a circuit if this many read+write bytes have been exceeded.
# Very loud application circuits could be used to introduce timing
# side channels.
# Warning: if your application has large resources that cannot be
# split up over multipe requests (such as large HTTP posts for eg:
# securedrop), you must set this higher.
CIRC_MAX_MEGABYTES = 100

# Kill circuits older than this many seconds.
# Really old circuits will continue to use old guards after the TLS connection
# has rotated, which means they will be alone on old TLS links. This lack
# of multiplexing may allow an adversary to use netflow records to determine
# the path through the Tor network to a hidden service.
CIRC_MAX_AGE_HOURS = 24 # 1 day

# Maximum size for an hsdesc fetch (including setup+get+dropped cells)
CIRC_MAX_HSDESC_KILOBYTES = 30

############ Constants ###############
_CELL_PAYLOAD_SIZE = 509
_RELAY_HEADER_SIZE = 11
_CELL_DATA_RATE = (float(_CELL_PAYLOAD_SIZE-_RELAY_HEADER_SIZE)/_CELL_PAYLOAD_SIZE)
# Every circuit takes about this much non-app data to set up. Subtract it from
# the dropped bytes total (this should just be stream SENDMEs at this point).
_CIRC_SETUP_BYTES = _CELL_PAYLOAD_SIZE*2

_SECS_PER_HOUR = 60*60
_BYTES_PER_KB = 1024
_BYTES_PER_MB = 1024*_BYTES_PER_KB

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

  def dropped_read_bytes(self):
    return self.read_bytes - \
           (self.delivered_read_bytes+self.overhead_read_bytes)

  def dropped_read_bytes_extra(self):
    return max(_CIRC_SETUP_BYTES,self.dropped_read_bytes())-_CIRC_SETUP_BYTES

  def dropped_read_rate(self):
    return self.dropped_read_bytes_extra()/self.read_bytes

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

      if delivered_read + overhead_read > event.read*_CELL_DATA_RATE:
        plog("ERROR",
             "Application read data exceeds cell data:"+event.raw_content());
      if delivered_written + overhead_written > event.written*_CELL_DATA_RATE:
        plog("ERROR",
             "Application written data exceeds cell data:"+event.raw_content());

      self.circs[event.id].read_bytes += event.read*_CELL_DATA_RATE
      self.circs[event.id].sent_bytes += event.written*_CELL_DATA_RATE

      self.circs[event.id].delivered_read_bytes += delivered_read
      self.circs[event.id].delivered_sent_bytes += delivered_written

      self.circs[event.id].overhead_read_bytes += overhead_read
      self.circs[event.id].overhead_sent_bytes += overhead_written

      self.check_circuit_limits(self.circs[event.id])

  def bw_event(self, event):
    if CIRC_MAX_AGE_HOURS <= 0:
      return

    now = time.time()
    # Unused except to expire circuits -- 1x/sec
    # FIXME: This is has needless copying on python 2..
    kill_circs = list(filter(
                        lambda c: now - c.created_at > \
                                  CIRC_MAX_AGE_HOURS*_SECS_PER_HOUR,
                        self.circs.values()))
    for circ in kill_circs:
      self.limit_exceeded("NOTICE", "CIRC_MAX_AGE_HOURS",
                          circ.circ_id,
                          now - circ.created_at,
                          CIRC_MAX_AGE_HOURS)
      self.try_close_circuit(circ.circ_id)

  def try_close_circuit(self, circ_id):
    try:
      self.controller.close_circuit(circ_id)
      plog("NOTICE", "We force-closed circuit "+str(circ_id))
    except stem.InvalidRequest as e:
      plog("INFO", "Failed to close circuit "+str(circ_id)+": "+str(e.message))

  def check_circuit_limits(self, circ):
    if not circ.is_hs: return
    if circ.read_bytes > _CIRC_SETUP_BYTES \
       and circ.dropped_read_rate() > CIRC_MAX_DROPPED_BYTES_PERCENT/100.0:
      self.limit_exceeded("WARN", "CIRC_MAX_DROPPED_PERCENT",
                          circ.circ_id,
                          circ.dropped_read_rate(),
                          CIRC_MAX_DROPPED_BYTES_PERCENT,
                          "Total: "+str(circ.read_bytes)+\
                          ", dropped: "+str(circ.dropped_read_bytes()))
      self.try_close_circuit(circ.circ_id)
    if CIRC_MAX_MEGABYTES > 0 and \
       circ.total_bytes() > CIRC_MAX_MEGABYTES*_BYTES_PER_MB:
      self.limit_exceeded("NOTICE", "CIRC_MAX_MEGABYTES",
                          circ.circ_id,
                          circ.total_bytes(),
                          CIRC_MAX_MEGABYTES*_BYTES_PER_MB)
      self.try_close_circuit(circ.circ_id)
    if CIRC_MAX_HSDESC_KILOBYTES > 0 and \
       circ.is_hsdir and circ.total_bytes() > \
       CIRC_MAX_HSDESC_KILOBYTES*_BYTES_PER_KB:
      self.limit_exceeded("WARN", "CIRC_MAX_HSDESC_KILOBYTES",
                          circ.circ_id,
                          circ.total_bytes(),
                          CIRC_MAX_HSDESC_KILOBYTES*_BYTES_PER_KB)
      self.try_close_circuit(circ.circ_id)

  def limit_exceeded(self, level, str_name, circ_id, cur_val, max_val, extra=""):
    # XXX: Rate limit this log
    plog(level, "Circ "+str(circ_id)+" exceeded "+str_name+": "+str(cur_val)+
                  " > "+str(max_val)+". "+extra)
