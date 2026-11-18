import functools
import stem
import time
import sys
from threading import Lock

import stem.response.events

from . import control
from . import vanguards
from . import bandguards
from . import logguard
from . import cbtverify
from . import pathverify

from . import config

from .logger import plog

_MIN_TOR_VERSION_FOR_BW = stem.version.Version("0.3.4.10")

def disable_conflux(controller, event=None):
  if event is not None and event.signal != "RELOAD":
    return
  try:
    try:
      enabled = controller.get_conf("ConfluxEnabled")
    except stem.InvalidArguments:
      return
    if enabled in (None, "0"):
      return
    controller.set_conf("ConfluxEnabled", "0")
  except stem.ControllerError:
    if event is None:
      raise
    plog("WARN", "Bandguards could not disable Conflux after Tor reloaded.")
    return
  plog("NOTICE", "Set ConfluxEnabled=0 to avoid incompatible Bandguards "
       "accounting. Onion services do not use Conflux.")

def main():
  try:
    run_main()
  except KeyboardInterrupt as e:
    plog("NOTICE", "Got CTRL+C. Exiting.")

def run_main():
  try:
    config.apply_config(config._CONFIG_FILE)
  except:
    pass # Default config can be absent.
  options = config.setup_options()

  # If the user specifies a config file, any values there should override
  # any previous config file options, but not options on the command line.
  if options.config_file != config._CONFIG_FILE:
    try:
      config.apply_config(options.config_file)
    except Exception as e:
      plog("ERROR",
           "Specified config file "+options.config_file+\
           " can't be read: "+str(e))
      sys.exit(1)
    options = config.setup_options()

  if config.ONE_SHOT_VANGUARDS and not config.ENABLE_VANGUARDS:
    plog("ERROR", "One-shot mode requires addon-managed vanguards.")
    sys.exit(1)

  state_file = config.STATE_FILE
  if (options.parallel_rendguard_state and config.ENABLE_RENDGUARD and
      not config.ENABLE_VANGUARDS):
    state_file += ".rendguard"

  try:
    # TODO: Use tor's data directory.. or our own
    state = vanguards.VanguardState.read_from_file(state_file)
    plog("INFO", "Current layer2 guards: "+state.layer2_guardset())
    plog("INFO", "Current layer3 guards: "+state.layer3_guardset())
  except Exception as e:
    plog("NOTICE", "Creating new vanguard state file at: "+state_file)
    state = vanguards.VanguardState(state_file)

  state.enable_vanguards = config.ENABLE_VANGUARDS
  stem.response.events.PARSE_NEWCONSENSUS_EVENTS = False

  reconnects = 0
  last_connected_at = None
  connected = False
  while options.retry_limit == None or reconnects < options.retry_limit:
    ret = control_loop(state)
    if not last_connected_at:
      last_connected_at = time.time()

    if ret == "closed":
      connected = True
    # Try once per second but only tell the user every 10 seconds
    if ret == "closed" or reconnects % 10 == 0:
      if time.time() - last_connected_at > \
        bandguards.CONN_MAX_DISCONNECTED_SECS:
        plog("WARN", "Tor daemon connection "+ret+". Trying again...")
      else:
        plog("NOTICE", "Tor daemon connection "+ret+". Trying again...")
    reconnects += 1
    time.sleep(1)

  if not connected:
    sys.exit(1)

def control_loop(state):
  if not config.CONTROL_SOCKET and not config.CONTROL_PORT:
    try:
      controller = \
        stem.control.Controller.from_socket_file("/run/tor/control")
      plog("NOTICE", "Connected to Tor via /run/tor/control socket")
    except stem.SocketError as e:
      try:
        controller = stem.control.Controller.from_port(config.CONTROL_IP)
      except stem.SocketError as e:
        return "failed: "+str(e)
      plog("NOTICE", "Connected to Tor via "+config.CONTROL_IP+" control port")
  else:
    try:
      if config.CONTROL_SOCKET != "":
        controller = \
          stem.control.Controller.from_socket_file(config.CONTROL_SOCKET)
        plog("NOTICE", "Connected to Tor via socket "+config.CONTROL_SOCKET)
      else:
        if not config.CONTROL_PORT or config.CONTROL_PORT == "default":
          controller = stem.control.Controller.from_port(config.CONTROL_IP)
          plog("NOTICE", "Connected to Tor via "+config.CONTROL_IP+
                         " control port")
        else:
          controller = stem.control.Controller.from_port(config.CONTROL_IP,
                                                     int(config.CONTROL_PORT))
          plog("NOTICE", "Connected to Tor via control port "+
               config.CONTROL_IP+ ":"+config.CONTROL_PORT)
    except ValueError as e:
      plog("ERROR", "Control port must be an integer or 'default'. Got "+
           str(config.CONTROL_PORT))
      sys.exit(1)
    except stem.SocketError as e:
      return "failed: "+str(e)

  control.authenticate_any(controller, config.CONTROL_PASS)

  consensus_ready = False
  pending_reload = None
  fatal_error = None
  reload_lock = Lock()

  def reload_guards(event):
    nonlocal fatal_error, pending_reload
    if event.signal != "RELOAD":
      return
    with reload_lock:
      if not consensus_ready:
        pending_reload = event
        return
    try:
      state.signal_event(controller, event)
    except SystemExit as exc:
      fatal_error = exc

  if config.ENABLE_VANGUARDS and not config.ONE_SHOT_VANGUARDS:
    controller.add_event_listener(reload_guards, stem.control.EventType.SIGNAL)

  # The new_consensus_event must still get called even if vanguards
  # is "disabled", because we also have to parse the consensus to
  # update rendguard counts
  if config.ENABLE_VANGUARDS or config.ENABLE_RENDGUARD:
    try:
      state.new_consensus_event(controller, None)
      with reload_lock:
        consensus_ready = True
        early_reload, pending_reload = pending_reload, None
      if early_reload is not None:
        state.signal_event(controller, early_reload)
    except stem.DescriptorUnavailable as e:
      if config.ONE_SHOT_VANGUARDS:
        controller.close()
        plog("ERROR", "Cannot configure guards: %s", str(e))
        sys.exit(1)
      plog("NOTICE", "Waiting for Tor consensus data: %s", str(e))

  if config.ONE_SHOT_VANGUARDS:
    try:
      controller.save_conf()
    except stem.OperationFailed as e:
      plog("NOTICE", "Tor can't save its own config file: "+str(e))
      sys.exit(1)
    plog("NOTICE", "Updated vanguards in torrc. Exiting.")
    sys.exit(0)

  # Thread-safety: state, timeouts, and bandwidths are effectively
  # transferred to the event thread here. They must not be used in
  # our thread anymore.

  def refresh_consensus(event):
    nonlocal consensus_ready, fatal_error, pending_reload
    try:
      if state.new_consensus_event(controller, event):
        with reload_lock:
          consensus_ready = True
          pending_reload = None
    except SystemExit as exc:
      # A fatal setup error must exit from the main thread.
      fatal_error = exc

  def retry_initial_consensus(event):
    # Close the gap between the initial query and NEWCONSENSUS subscription.
    controller.remove_event_listener(retry_initial_consensus)
    if not consensus_ready:
      refresh_consensus(event)

  def rendguard_event(event):
    if consensus_ready:
      state.rendguard.circ_event(controller, event)

  if config.ENABLE_RENDGUARD:
    controller.add_event_listener(rendguard_event, stem.control.EventType.CIRC)

  # Ok, little low on fucks here. But this is fine. This will work.
  # We check for None in control.try_close_circuit()
  controller._logguard = None

  if config.ENABLE_LOGGUARD:
    logs = logguard.LogGuard(controller) # Also registeres logbuffer events

    # Make the log object available later for log dumping
    controller._logguard = logs

    # Always log warns
    controller.add_event_listener(
                 functools.partial(logguard.LogGuard.log_warn_event,
                                   logs),
                                   stem.control.EventType.WARN)

    # For post-close logs
    controller.add_event_listener(
                 functools.partial(logguard.LogGuard.circ_event, logs),
                                  stem.control.EventType.CIRC)


  if config.ENABLE_BANDGUARDS:
    bandwidths = bandguards.BandwidthStats(controller)
    supports_circ_bw = controller.get_version() >= _MIN_TOR_VERSION_FOR_BW
    if supports_circ_bw:
      controller.add_event_listener(functools.partial(disable_conflux, controller),
                                    stem.control.EventType.SIGNAL)
      disable_conflux(controller)
    bandwidths.attach_circuits(supports_circ_bw)

    controller.add_event_listener(
                 functools.partial(bandguards.BandwidthStats.bw_event, bandwidths),
                                  stem.control.EventType.BW)
    controller.add_event_listener(
                 functools.partial(bandguards.BandwidthStats.orconn_event, bandwidths),
                                  stem.control.EventType.ORCONN)
    controller.add_event_listener(
                 functools.partial(bandguards.BandwidthStats.network_liveness_event,
                                   bandwidths),
                                  stem.control.EventType.NETWORK_LIVENESS)

    if supports_circ_bw:
      controller.add_event_listener(
                   functools.partial(bandguards.BandwidthStats.circbw_event, bandwidths),
                                    stem.control.EventType.CIRC_BW)
    else:
      plog("NOTICE", "In order for bandwidth-based protections to be "+
                      "enabled, you must use Tor 0.3.4.10 or newer.")


  if config.ENABLE_CBTVERIFY:
    timeouts = cbtverify.TimeoutStats()

    controller.add_event_listener(
                 functools.partial(cbtverify.TimeoutStats.circ_event, timeouts),
                                  stem.control.EventType.CIRC)
    controller.add_event_listener(
                 functools.partial(cbtverify.TimeoutStats.cbt_event, timeouts),
                                  stem.control.EventType.BUILDTIMEOUT_SET)

  if config.ENABLE_PATHVERIFY:
    paths = pathverify.PathVerify(controller,
                                  config.ENABLE_VANGUARDS,
                                  vanguards.NUM_LAYER1_GUARDS,
                                  vanguards.NUM_LAYER2_GUARDS,
                                  vanguards.NUM_LAYER3_GUARDS)

    controller.add_event_listener(
                 functools.partial(pathverify.PathVerify.circ_event, paths),
                                  stem.control.EventType.CIRC)
    controller.add_event_listener(
                 functools.partial(pathverify.PathVerify.circ_minor_event, paths),
                                  stem.control.EventType.CIRC_MINOR)
    controller.add_event_listener(
                 functools.partial(pathverify.PathVerify.orconn_event, paths),
                                  stem.control.EventType.ORCONN)
    controller.add_event_listener(
                 functools.partial(pathverify.PathVerify.guard_event, paths),
                                  stem.control.EventType.GUARD)
    controller.add_event_listener(
                 functools.partial(pathverify.PathVerify.conf_changed_event,
                                   paths),
                                  stem.control.EventType.CONF_CHANGED)
    # After launch pathverify, we send a NEWNYM to get fresh circs and
    # vg-lite guards
    controller.signal("NEWNYM")


  # Thread-safety: We're effectively transferring controller to the event
  # thread here.
  if config.ENABLE_VANGUARDS or config.ENABLE_RENDGUARD:
    controller.add_event_listener(refresh_consensus, stem.control.EventType.NEWCONSENSUS)
    if not consensus_ready:
      controller.add_event_listener(retry_initial_consensus, stem.control.EventType.BW)

  # Blah...
  while fatal_error is None and controller.is_alive():
    time.sleep(1)
  if fatal_error is not None:
    # Exit directly. Closing a Stem controller here joins its event thread,
    # which may itself be waiting to send a control command.
    raise fatal_error

  return "closed"
