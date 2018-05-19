import functools
import stem
import time

import stem.response.events

from . import control
from . import rendguard
from . import vanguards
from . import bandguards
from . import cbtverify

from . import config

def main():
  config.apply_config(config._CONFIG_FILE)
  config.setup_options()
  try:
    # TODO: Use tor's data directory.. or our own
    state = vanguards.VanguardState.read_from_file(config.STATE_FILE)
  except:
    state = vanguards.VanguardState(config.STATE_FILE)

  stem.response.events.PARSE_NEWCONSENSUS_EVENTS = False

  if config.CONTROL_SOCKET != "":
    controller = control.connect_to_socket(config.CONTROL_SOCKET)
  else:
    controller = control.connect_to_ip(config.CONTROL_IP, config.CONTROL_PORT)

  control.authenticate_any(controller)

  state.new_consensus_event(controller, None)
  timeouts = cbtverify.TimeoutStats()
  bandwidths = bandguards.BandwidthStats(controller)

  # Thread-safety: state, timeouts, and bandwidths are effectively
  # transferred to the event thread here. They must not be used in
  # our thread anymore.

  if config.ENABLE_RENDGUARD:
    controller.add_event_listener(
                 functools.partial(rendguard.RendGuard.circ_event,
                                   state.rendguard, controller),
                                  stem.control.EventType.CIRC)
  if config.ENABLE_BANDGUARDS:
    controller.add_event_listener(
                 functools.partial(bandguards.BandwidthStats.circ_event, bandwidths),
                                  stem.control.EventType.CIRC)
    controller.add_event_listener(
                 functools.partial(bandguards.BandwidthStats.bw_event, bandwidths),
                                  stem.control.EventType.BW)
    controller.add_event_listener(
                 functools.partial(bandguards.BandwidthStats.circbw_event, bandwidths),
                                  stem.control.EventType.CIRC_BW)

  if config.ENABLE_CBTVERIFY:
    controller.add_event_listener(
                 functools.partial(cbtverify.TimeoutStats.circ_event, timeouts),
                                  stem.control.EventType.CIRC)
    controller.add_event_listener(
                 functools.partial(cbtverify.TimeoutStats.cbt_event, timeouts),
                                  stem.control.EventType.BUILDTIMEOUT_SET)

  # Thread-safety: We're effectively transferring controller to the event
  # thread here.
  controller.add_event_listener(
               functools.partial(vanguards.VanguardState.new_consensus_event,
                                 state, controller),
                                stem.control.EventType.NEWCONSENSUS)

  # Blah...
  while controller.is_alive():
    time.sleep(1)

