""" Simple checks against bandwidth side channels """
import time
import stem

from . import control

from .logger import plog

############ BandGuard Options #################

# Kill a circuit if this much received bandwidth is not application related.
# This prevents an adversary from inserting cells that are silently dropped
# into a circuit, to use as a timing side channel.
CIRC_MAX_DROPPED_BYTES_PERCENT = 0.0

# Kill a circuit if this many read+write bytes have been exceeded.
# Very loud application circuits could be used to introduce timing
# side channels.
# Warning: if your application has large resources that cannot be
# split up over multipe requests (such as large HTTP posts for eg:
# securedrop, or sharing large files via onionshare), you must set
# this high enough for those uploads not to get truncated!
CIRC_MAX_MEGABYTES = 0

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
# This is the number of SENDME cells that can be in flight at a given time.
# If one end hangs up on a stream right after sending its data, then there
# can be up to 10 SENDME cells in flight on the stream, plus an END cell.
# They will arrive on an unknown stream-id at the other end, after the hangup.
_CIRC_SETUP_BYTES = _CELL_PAYLOAD_SIZE*11

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

  def circ_event(self, event):
    # Sometimes circuits get multiple FAILED+CLOSED events,
    # so we must check that first...
    if (event.status == stem.CircStatus.FAILED or \
       event.status == stem.CircStatus.CLOSED):
      if event.id in self.circs:
        plog("DEBUG", "Closed hs circ for "+event.raw_content())
        del self.circs[event.id]
    elif event.id not in self.circs:
      if event.hs_state or event.purpose[0:2] == "HS":
        self.circs[event.id] = BwCircuitStat(event.id, 1)

        # Handle direct build purpose settings
        if event.purpose[0:9] == "HS_CLIENT":
          self.circs[event.id].is_service = 0
        elif event.purpose[0:10] == "HS_SERVICE":
          self.circs[event.id].is_service = 1
        if event.purpose == "HS_CLIENT_HSDIR" or \
           event.purpose == "HS_SERVICE_HSDIR":
          self.circs[event.id].is_hsdir = 1
        plog("DEBUG", "Added hs circ for "+event.raw_content())


  # We need CIRC_MINOR to determine client from service as well
  # as recognize cannibalized HSDIR circs
  def circ_minor_event(self, event):
    if event.id not in self.circs:
      return

    if event.purpose[0:9] == "HS_CLIENT":
      self.circs[event.id].is_service = 0
    elif event.purpose[0:10] == "HS_SERVICE":
      self.circs[event.id].is_service = 1
    if event.purpose == "HS_CLIENT_HSDIR" or \
       event.purpose == "HS_SERVICE_HSDIR":
      self.circs[event.id].is_hsdir = 1

    plog("DEBUG", event.raw_content())

  def circbw_event(self, event):
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
      control.try_close_circuit(self.controller, circ.circ_id)

  def check_circuit_limits(self, circ):
    if not circ.is_hs: return
    if circ.read_bytes > _CIRC_SETUP_BYTES \
       and circ.dropped_read_rate() > CIRC_MAX_DROPPED_BYTES_PERCENT/100.0:
      # When clients hang up on streams before they close, this can result in
      # dropped data from those now-invalid/unknown stream IDs. Servers should
      # not do this. Hence warn for service case, notice for clients.
      if circ.is_service: loglevel = "WARN"
      else: loglevel = "NOTICE"
      self.limit_exceeded(loglevel, "CIRC_MAX_DROPPED_BYTES_PERCENT",
                          circ.circ_id,
                          circ.dropped_read_rate()*100.0,
                          CIRC_MAX_DROPPED_BYTES_PERCENT,
                          "Total: "+str(circ.read_bytes)+\
                          ", dropped: "+str(circ.dropped_read_bytes()))
      control.try_close_circuit(self.controller, circ.circ_id)
    if CIRC_MAX_MEGABYTES > 0 and \
       circ.total_bytes() > CIRC_MAX_MEGABYTES*_BYTES_PER_MB:
      self.limit_exceeded("NOTICE", "CIRC_MAX_MEGABYTES",
                          circ.circ_id,
                          circ.total_bytes(),
                          CIRC_MAX_MEGABYTES*_BYTES_PER_MB)
      control.try_close_circuit(self.controller, circ.circ_id)
    if CIRC_MAX_HSDESC_KILOBYTES > 0 and \
       circ.is_hsdir and circ.total_bytes() > \
       CIRC_MAX_HSDESC_KILOBYTES*_BYTES_PER_KB:
      self.limit_exceeded("WARN", "CIRC_MAX_HSDESC_KILOBYTES",
                          circ.circ_id,
                          circ.total_bytes(),
                          CIRC_MAX_HSDESC_KILOBYTES*_BYTES_PER_KB)
      control.try_close_circuit(self.controller, circ.circ_id)

  def limit_exceeded(self, level, str_name, circ_id, cur_val, max_val, extra=""):
    plog(level, "Circ "+str(circ_id)+" exceeded "+str_name+": "+str(cur_val)+
                  " > "+str(max_val)+". "+extra)
