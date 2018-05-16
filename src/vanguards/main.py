import functools
import stem
import time

from . import config
from . import control
from .vanguards import VanguardState
from .bandguards import BandwidthStats
from .cbtverify import TimeoutStats
from .rendguard import RendGuard

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

  if config.RENDGUARD_ENABLED:
    controller.add_event_listener(
                 functools.partial(RendGuard.circ_event, state.rendguard,
                                   controller),
                                  stem.control.EventType.CIRC)
  if config.BANDGUARDS_ENABLED:
    controller.add_event_listener(
                 functools.partial(BandwidthStats.circ_event, bandwidths),
                                  stem.control.EventType.CIRC)
    controller.add_event_listener(
                 functools.partial(BandwidthStats.bw_event, bandwidths),
                                  stem.control.EventType.BW)
    controller.add_event_listener(
                 functools.partial(BandwidthStats.circbw_event, bandwidths),
                                  stem.control.EventType.CIRC_BW)

  if config.CBTVERIFY_ENABLED:
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

