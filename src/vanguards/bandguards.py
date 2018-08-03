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
# split up over multiple requests (such as large HTTP posts for eg:
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

# Warn if Tor can't build or use circuits for this many seconds
CIRC_MAX_DISCONNECTED_SECS = 20

# Warn if Tor has no connections for this many seconds
CONN_MAX_DISCONNECTED_SECS = 15

############ Constants ###############
_CELL_PAYLOAD_SIZE = 509
_RELAY_HEADER_SIZE = 11
_CELL_DATA_RATE = (float(_CELL_PAYLOAD_SIZE-_RELAY_HEADER_SIZE)/_CELL_PAYLOAD_SIZE)

# Constants from connection_edge_consider_sending_sendme(). These govern the
# max SENDMEs can be expected to be in-flight.
_STREAM_SENDME_INCREMENT = 50
_STREAM_SENDME_WINDOW = 500

_SECS_PER_HOUR = 60*60
_BYTES_PER_KB = 1024
_BYTES_PER_MB = 1024*_BYTES_PER_KB

# Because we have to map circuits to guard destroy events, we need.
# The event really should arrive in the same second, but let's
# give it until the next couple in case there is a scheduled events hiccup
_MAX_CIRC_DESTROY_LAG_SECS = 2

class BwCircuitStat:
  def __init__(self, circ_id, is_hs):
    self.circ_id = circ_id
    self.is_hs = is_hs
    self.is_service = 1
    self.is_hsdir = 0
    self.in_use = 0
    self.created_at = time.time()
    self.read_bytes = 0
    self.sent_bytes = 0
    self.delivered_read_bytes = 0
    self.delivered_sent_bytes = 0
    self.overhead_read_bytes = 0
    self.overhead_sent_bytes = 0
    self.guard_fp = None
    self.possibly_destroyed_at = None

  def total_bytes(self):
    return self.read_bytes + self.sent_bytes

  def dropped_read_bytes(self):
    return self.read_bytes - \
           (self.delivered_read_bytes+self.overhead_read_bytes)

  # The allowed dropped bytes is the number of expected SENDMEs we may have
  # pending based on the stream window, because one end can close the stream
  # before they arrive (causing them to get dropped). One SENDME is sent every
  # 50 cells, up to 500. This means a max of 10 should be in-flight, plus 1
  # if the other side decides to send an END as well once it gets all data.
  def allowed_dropped_bytes(self):
    cells_sent = (self.sent_bytes/(_CELL_PAYLOAD_SIZE*_CELL_DATA_RATE))
    sendme_count = cells_sent/_STREAM_SENDME_INCREMENT
    max_sendmes = 1+int(min(sendme_count,
                            _STREAM_SENDME_WINDOW/_STREAM_SENDME_INCREMENT))
    return max_sendmes*_CELL_PAYLOAD_SIZE

  def dropped_read_bytes_extra(self):
    return max(self.allowed_dropped_bytes(),
               self.dropped_read_bytes())-self.allowed_dropped_bytes()

  def dropped_read_rate(self):
    return self.dropped_read_bytes_extra()/self.read_bytes

class BwGuardStat:
  def __init__(self, guard_fp):
    self.to_guard = guard_fp
    self.killed_conns = 0
    self.killed_conn_pending = False
    self.conns_made = 0
    self.close_reasons = {} # key=reason val=count

class BandwidthStats:
  def __init__(self, controller):
    self.controller = controller
    self.circs = {} # key=circid val=BwCircStat
    self.live_guard_conns = {} # key=connid val=BwGuardStat
    self.guards = {} # key=guardfp val=BwGuardStat
    self.circs_destroyed_total = 0
    self.no_conns_since = time.time()
    self.no_circs_since = None
    self.max_fake_id = -1
    self.disconnected_circs = False
    self.disconnected_conns = False
    self._orconn_init(controller)

  # Load in our current orconns. orconn-status does not
  # tell us IDs, so we have to fake it and keep track of fakes :/
  def _orconn_init(self, controller):
    fake_id = 0
    for l in controller.get_info("orconn-status").split("\n"):
      if len(l):
        self.orconn_event(
         stem.response.ControlMessage.from_str(
           "650 ORCONN "+l+" ID="+str(fake_id)+"\r\n", "EVENT"))
        fake_id += 1
    self.max_fake_id = fake_id - 1

  # We need to scan for our fake_id conns here and fixup
  # the event.id accordingly...
  def _fixup_orconn_event(self, event):
    guard_fp = event.endpoint_fingerprint
    fake_id = self.max_fake_id
    while fake_id >= 0:
      if str(fake_id) in self.live_guard_conns and \
         self.live_guard_conns[str(fake_id)].to_guard == guard_fp:
        event.id = str(fake_id)
      fake_id -= 1

  # We watch orconn events so that when one closes, we can mark
  # the circuits that might have been alive on it and watch for
  # their close messages later. We have to do this dance because
  # the CIRC event doesn't tell us which hop killed the circuit.
  #
  # We also keep additional stats on the number of connections, to
  # monitor overall guard use for debugging.
  def orconn_event(self, event):
    guard_fp = event.endpoint_fingerprint
    if not event.endpoint_fingerprint in self.guards:
      self.guards[guard_fp] = BwGuardStat(guard_fp)

    if event.status == "CONNECTED":
      self.live_guard_conns[event.id] = self.guards[guard_fp]
      self.guards[guard_fp].conns_made += 1
      self.no_conns_since = 0
      self.disconnected_conns = False
    elif event.status == "CLOSED" or event.status == "FAILED":
      if event.id not in self.live_guard_conns:
        self._fixup_orconn_event(event)

      if event.id in self.live_guard_conns:
        # Scan the circuit list for any circuits that might
        # be using this guard and that are in use. This is to
        # watch for their close later.
        for c in self.circs.values():
          if c.in_use and c.guard_fp == guard_fp:
            c.possibly_destroyed_at = event.arrived_at
            self.live_guard_conns[event.id].killed_conn_at = event.arrived_at
            plog("INFO", "Marking possibly destroyed circ %d at %d",
                 c.circ_id, event.arrived_at)

        del self.live_guard_conns[event.id]
        if len(self.live_guard_conns) == 0:
          self.no_conns_since = event.arrived_at
      # Keep stats on CLOSED reasons. We don't do anything with these atm
      if event.status == "CLOSED":
        if not event.reason in self.guards[guard_fp].close_reasons:
          self.guards[guard_fp].close_reasons[event.reason] = 0
        self.guards[guard_fp].close_reasons[event.reason] += 1
    plog("INFO", event.raw_content())

  def circuit_destroyed(self, event):
    self.circs_destroyed_total += 1
    guardfp = event.path[0][0]
    if event.arrived_at - self.guards[guardfp].killed_conn_at \
        <= _MAX_CIRC_DESTROY_LAG_SECS:
      self.guards[guardfp].killed_conn_at = None
      self.guards[guardfp].killed_conns += 1
      # FIXME: Limit to warn after?
      plog("NOTICE", "The connection to guard "+guardfp+" was closed with "+\
           "a live circuit.")

    plog("INFO", "The connection to guard "+guardfp+" was closed with "+\
         "circuit "+event.id+" on it.")

  def circ_event(self, event):
    # Failed circuits mean the network could be down:
    if event.status == stem.CircStatus.FAILED:
      self.no_circs_since = event.arrived_at

    # Sometimes circuits get multiple FAILED+CLOSED events,
    # so we must check that first...
    if (event.status == stem.CircStatus.FAILED or \
       event.status == stem.CircStatus.CLOSED):
      if event.id in self.circs:
        # If the circuit was in use, and possibly closed due to a guard
        # connection closure recently, and this event says it died due to
        # a channel closure, then record that.
        if self.circs[event.id].in_use and \
           self.circs[event.id].possibly_destroyed_at:
          if event.arrived_at - self.circs[event.id].possibly_destroyed_at \
                <= _MAX_CIRC_DESTROY_LAG_SECS and \
             event.remote_reason == "CHANNEL_CLOSED":
            self.circuit_destroyed(event)
          else:
            plog("INFO",
                 "Circuit %s possibly destroyed, but outside of the time window (%d - %d)",
                 event.id, event.arrived_at, self.circs[event.id].possibly_destroyed_at)
        plog("DEBUG", "Closed hs circ for "+event.raw_content())
        del self.circs[event.id]
      return
    if event.id not in self.circs:
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

    # Consider all BUILT circs that have a specific HS purpose
    # to be "in_use".
    if event.status == stem.CircStatus.BUILT or \
       event.status == "GUARD_WAIT":
      self.no_circs_since = None
      self.disconnected_circs = False
      if event.purpose[0:9] == "HS_CLIENT" or \
         event.purpose[0:10] == "HS_SERVICE":
        self.circs[event.id].in_use = 1
        self.circs[event.id].guard_fp = event.path[0][0]

    # Extending a circuit means the network is OK
    elif event.status == "EXTENDED":
      self.no_circs_since = None
      self.disconnected_circs = False

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

    # PURPOSE_CHANGED from HS_VANGUARDS -> in_use
    if event.event == stem.CircEvent.PURPOSE_CHANGED:
      if event.old_purpose == "HS_VANGUARDS":
        self.circs[event.id].in_use = 1
        self.circs[event.id].guard_fp = event.path[0][0]

    plog("DEBUG", event.raw_content())

  def circbw_event(self, event):
    # Circuit bandwidth means circuits are working
    self.no_circs_since = None
    self.disconnected_circs = False

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

  def check_connectivity(self, now):
    if self.no_conns_since:
      disconnected_secs = int(now - self.no_conns_since)

      if disconnected_secs >= CONN_MAX_DISCONNECTED_SECS:
        if not self.disconnected_conns or \
          disconnected_secs % CONN_MAX_DISCONNECTED_SECS == 0:
          plog("WARN", "We've been disconnected from the Tor network for %d seconds!"
               % disconnected_secs)
        self.disconnected_conns = True
    elif self.no_circs_since:
      disconnected_secs = int(now - self.no_circs_since)

      if disconnected_secs >= CIRC_MAX_DISCONNECTED_SECS:
        if not self.disconnected_circs or \
          disconnected_secs % CIRC_MAX_DISCONNECTED_SECS == 0:
          plog("WARN", "Tor has been failing all circuits for %d seconds!"
               % disconnected_secs)
        self.disconnected_circs = True

  def check_circ_ages(self, now):
    if CIRC_MAX_AGE_HOURS <= 0:
      return

    # Unused except to expire circuits -- 1x/sec
    # FIXME: This is needless copying on python 2..
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

  # Used for 1x/sec heartbeat only
  def bw_event(self, event):
    now = time.time()
    self.check_connectivity(event.arrived_at)
    self.check_circ_ages(now)

  def check_circuit_limits(self, circ):
    if not circ.is_hs: return
    if circ.read_bytes > 0 and \
       circ.dropped_read_rate() > CIRC_MAX_DROPPED_BYTES_PERCENT/100.0:
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
