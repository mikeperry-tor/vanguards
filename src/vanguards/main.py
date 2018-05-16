import functools
import stem
import time

from . import config
from . import control
from .vanguards import VanguardState
from .bandguards import BandwidthStats
from .cbtverify import TimeoutStats
from .rendwatcher import RendWatcher

def main():
  config.setup_options()
  try:
    # TODO: Use tor's data directory.. or our own
    f = open(config.STATE_FILE, "rb")
    state = VanguardState.read_from_file(f)
  except:
    state = VanguardState()

  stem.response.events.PARSE_NEWCONSENSUS_EVENTS = False
  controller = control.connect()
  state.new_consensus_event(controller, None)
  timeouts = TimeoutStats()
  bandwidths = BandwidthStats(controller)

  # Thread-safety: state, timeouts, and bandwidths are effectively
  # transferred to the event thread here. They must not be used in
  # our thread anymore.
  # XXX: Make rendwatcher optional by config (on by default)

  controller.add_event_listener(
               functools.partial(RendWatcher.circ_event, state.rendwatcher,
                                 controller),
                                stem.control.EventType.CIRC)

  # XXX: Make bandgaurds optional by config (on by default)
  controller.add_event_listener(
               functools.partial(BandwidthStats.circ_event, bandwidths),
                                stem.control.EventType.CIRC)
  controller.add_event_listener(
               functools.partial(BandwidthStats.bw_event, bandwidths),
                                stem.control.EventType.BW)
  controller.add_event_listener(
               functools.partial(BandwidthStats.circbw_event, bandwidths),
                                stem.control.EventType.CIRC_BW)

  # XXX: Make circ_timeouts by config (off by default)
  controller.add_event_listener(
               functools.partial(TimeoutStats.circ_event, timeouts),
                                stem.control.EventType.CIRC)
  controller.add_event_listener(
               functools.partial(TimeoutStats.cbt_event, timeouts),
                                stem.control.EventType.BUILDTIMEOUT_SET)

  # Thread-safety: We're effectively transferring controller to the event
  # thread here.
  controller.add_event_listener(
               functools.partial(VanguardState.new_consensus_event,
                                 state, controller),
                                stem.control.EventType.NEWCONSENSUS)

  # Blah...
  while controller.is_alive():
    time.sleep(1)

