import sys
import stem
import getpass
import logging
import os
import shutil
import pytest

import stem.connection
import stem.control
import vanguards.control
import vanguards.config
import vanguards.main

GOT_SOCKET = ""
THROW_SOCKET = False
THROW_AUTH = False
DATA_DIR = "tests"
NO_HSLAYER = False
TOR_VERSION = stem.version.Version("0.3.5.1-alpha")
DEFAULT_CONFIG=os.path.join("tests", "default.conf")
GOT_SAVE_CONF = False
FAIL_SAVE_CONF = False

class MockController:
  def __init__(self):
    self.alive = True
    self._logguard = None

  def signal(self, sig):
    pass

  @staticmethod
  def from_port(ip, port):
    if THROW_SOCKET:
      raise stem.SocketError("Ded")
    else:
      return MockController()

  @staticmethod
  def from_socket_file(infile):
    global GOT_SOCKET
    if THROW_SOCKET:
      raise stem.SocketError("Ded")
    else:
      GOT_SOCKET = infile
      return MockController()

  def add_event_listener(self, func, *events):
    pass

  def get_circuits(self):
    return []

  def authenticate(self, password=None):
    if THROW_AUTH:
      raise stem.connection.AuthenticationFailure("Bad")
    if password == None:
      raise stem.connection.MissingPassword("Bad")
    elif password != "foo":
      raise stem.connection.PasswordAuthFailed("Bad")

  def get_version(self):
    return TOR_VERSION

  def get_conf(self, key, default=None):
    if key == "DataDirectory":
      return DATA_DIR
    return default

  def get_info(self, key, default=None):
    if key == "consensus/valid-after":
      return "2018-04-21 18:00:00"
    if key == "orconn-status":
      return "$3E53D3979DB07EFD736661C934A1DED14127B684~Unnamed CONNECTED\n"+\
             "$3E53D3979DB07EFD736661C934A1DED14127B684~Unnamed CONNECTED"
    return default

  def set_conf(self, key, val):
    if NO_HSLAYER and key == "HSLayer2Nodes":
      raise stem.InvalidArguments("Bad")

  def save_conf(self):
    global GOT_SAVE_CONF
    GOT_SAVE_CONF = True
    if FAIL_SAVE_CONF:
      raise stem.OperationFailed("Bad")

  def is_alive(self):
    if self.alive:
      self.alive = False
      return True
    return False

  def close(self):
    return

stem.control.Controller = MockController
vanguards.config.ENABLE_CBTVERIFY = True
vanguards.config.ENABLE_PATHVERIFY = True
vanguards.config.STATE_FILE = "tests/state.mock.test"
vanguards.config._RETRY_LIMIT = 1

def mock_getpass(msg):
  return "foo"
getpass.getpass = mock_getpass

def test_main():
  shutil.copy("tests/state.mock", "tests/state.mock.test")
  sys.argv = ["test_main"]
  vanguards.main.main()
  os.remove("tests/state.mock.test")

# Test plan:
# - Test ability to override CONTROL_SOCKET
#   - Via conf file
#   - Via param
#   - Verify override
# TODO: - Test other params too?
def test_configs():
  global GOT_SOCKET
  shutil.copy("tests/state.mock", "tests/state.mock.test")
  sys.argv = ["test_main", "--control_socket", "arg.sock" ]
  vanguards.main.main()
  assert GOT_SOCKET == "arg.sock"

  vanguards.config.apply_config(DEFAULT_CONFIG)
  assert vanguards.control._CLOSE_CIRCUITS == True
  sys.argv = ["test_main", "--config", "tests/conf.mock"]
  vanguards.main.main()
  assert GOT_SOCKET == "conf.sock"
  assert vanguards.control._CLOSE_CIRCUITS == False

  vanguards.config.apply_config(DEFAULT_CONFIG)
  sys.argv = ["test_main", "--control_socket", "arg.sock", "--config", "tests/conf.mock" ]
  EXPECTED_SOCKET = "arg.sock"
  vanguards.main.main()
  assert GOT_SOCKET == "arg.sock"

  # TODO: Check that this is sane
  vanguards.config.apply_config(DEFAULT_CONFIG)
  sys.argv = ["test_main", "--generate_config", "wrote.conf" ]
  try:
    vanguards.main.main()
    assert False
  except SystemExit:
    assert True
  os.remove("tests/state.mock.test")

def test_failures():
  global THROW_SOCKET,THROW_AUTH,DATA_DIR,NO_HSLAYER
  global TOR_VERSION
  shutil.copy("tests/state.mock", "tests/state.mock.test")
  # Test lack of failures
  vanguards.config.apply_config(DEFAULT_CONFIG)
  sys.argv = ["test_main" ]
  try:
    vanguards.main.main()
    assert True
  except SystemExit:
    assert False

  # Test empty DataDirectory
  vanguards.config.apply_config(DEFAULT_CONFIG)
  DATA_DIR = None
  sys.argv = ["test_main" ]
  vanguards.main.main()

  # Test bogus DataDirectory
  vanguards.config.apply_config(DEFAULT_CONFIG)
  DATA_DIR = "/.bogus23"
  sys.argv = ["test_main" ]
  vanguards.main.main()
  DATA_DIR = "tests"

  # Test connection failures for socket
  vanguards.config.apply_config(DEFAULT_CONFIG)
  vanguards.config.CONTROL_SOCKET=""
  sys.argv = ["test_main" ]
  THROW_SOCKET=True
  try:
    vanguards.main.main()
    assert False
  except SystemExit:
    assert True
  THROW_SOCKET=False

  # Test connection failures for socket+ file
  vanguards.config.apply_config(DEFAULT_CONFIG)
  sys.argv = ["test_main", "--control_socket", "None.conf" ]
  THROW_SOCKET=True
  try:
    vanguards.main.main()
    assert False
  except SystemExit:
    assert True
  THROW_SOCKET=False

  # Test connection failures for name resolution
  vanguards.config.apply_config(DEFAULT_CONFIG)
  sys.argv = ["test_main", "--control_ip", "localbogusxyzzy" ]
  THROW_SOCKET=True
  try:
    vanguards.main.main()
    assert False
  except SystemExit:
    assert True
  THROW_SOCKET=False

  # Test fail to read config file
  vanguards.config.apply_config(DEFAULT_CONFIG)
  sys.argv = ["test_main", "--config", "None.conf" ]
  try:
    vanguards.main.main()
    assert False
  except SystemExit:
    assert True

  # Test fail to read state file
  vanguards.config.apply_config(DEFAULT_CONFIG)
  sys.argv = ["test_main", "--state", "/.bogus/None.state" ]
  try:
    vanguards.main.main()
    assert False
  except SystemExit:
    assert True

  # Cover partially unsupported Tor versions
  vanguards.config.apply_config(DEFAULT_CONFIG)
  sys.argv = ["test_main" ]
  TOR_VERSION=stem.version.Version("0.3.4.4-rc")
  try:
    vanguards.main.main()
    assert True
  except SystemExit:
    assert False

  # Cover partially unsupported Tor versions
  vanguards.config.apply_config(DEFAULT_CONFIG)
  sys.argv = ["test_main" ]
  TOR_VERSION=stem.version.Version("0.3.3.5-rc-dev")
  try:
    vanguards.main.main()
    assert True
  except SystemExit:
    assert False

  # Test fully unsupported Tor version
  vanguards.config.apply_config(DEFAULT_CONFIG)
  NO_HSLAYER=True
  sys.argv = ["test_main" ]
  TOR_VERSION=stem.version.Version("0.2.9.6")
  try:
    vanguards.main.main()
    assert False
  except SystemExit:
    assert True
  NO_HSLAYER=False

  # Test loglevel failure
  vanguards.config.apply_config(DEFAULT_CONFIG)
  sys.argv = ["test_main", "--loglevel", "INFOg" ]
  try:
    vanguards.main.main()
    assert False
  except SystemExit:
    assert True

  # Test log failure
  vanguards.config.apply_config(DEFAULT_CONFIG)
  sys.argv = ["test_main", "--loglevel", "INFO", "--logfile", "/.invalid/diaf" ]
  try:
    vanguards.main.main()
    assert False
  except SystemExit:
    assert True

  # Test syslog success
  vanguards.config.apply_config(DEFAULT_CONFIG)
  sys.argv = ["test_main", "--logfile", ":syslog:" ]
  try:
    vanguards.main.main()
    assert True
  except SystemExit:
    assert False

  # Test loglevel and log success
  vanguards.config.apply_config(DEFAULT_CONFIG)
  sys.argv = ["test_main", "--loglevel", "INFO", "--logfile", "valid.log.test" ]
  try:
    vanguards.main.main()
    assert True
  except SystemExit:
    assert False
  os.stat("valid.log.test")

  # Test bad password auth:
  vanguards.config.apply_config(DEFAULT_CONFIG)
  THROW_AUTH=True
  sys.argv = ["test_main"]
  try:
    vanguards.main.main()
    assert False
  except SystemExit:
    assert True

  vanguards.config.apply_config(DEFAULT_CONFIG)
  THROW_AUTH=False
  sys.argv = ["test_main", "--control_pass", "invalid" ]
  try:
    vanguards.main.main()
    assert False
  except SystemExit:
    assert True

  # Clean up temporary test data
  os.remove("tests/state.mock.test")
  os.remove("vanguards.state.test")
  os.remove("valid.log.test")

def test_oneshot():
  global GOT_SAVE_CONF, FAIL_SAVE_CONF
  # Test no saveconf, no exit by default
  vanguards.config.apply_config(DEFAULT_CONFIG)
  sys.argv = ["test_main" ]
  try:
    assert not GOT_SAVE_CONF
    vanguards.main.main()
    assert True
    assert not GOT_SAVE_CONF
  except SystemExit:
    assert False

  # Test lack of failures
  vanguards.config.apply_config(DEFAULT_CONFIG)
  sys.argv = ["test_main", "--one_shot_vanguards" ]
  try:
    assert not GOT_SAVE_CONF
    vanguards.main.main()
    assert False
  except SystemExit:
    assert True
    assert GOT_SAVE_CONF

  # Test failure
  GOT_SAVE_CONF = False
  vanguards.config.apply_config(DEFAULT_CONFIG)
  sys.argv = ["test_main", "--one_shot_vanguards" ]
  try:
    assert not GOT_SAVE_CONF
    FAIL_SAVE_CONF = True
    vanguards.main.main()
    assert False
  except SystemExit:
    assert True
    assert GOT_SAVE_CONF

  os.remove("vanguards.state.test")

def test_oneshot_does_not_save_without_consensus(monkeypatch, tmp_path, caplog):
  vanguards.config.apply_config(DEFAULT_CONFIG)
  monkeypatch.setattr(sys, "argv", ["vanguards", "--one_shot_vanguards", "--state", str(tmp_path / "state")])
  monkeypatch.setattr(sys.modules[__name__], "DATA_DIR", str(tmp_path))
  monkeypatch.setattr(sys.modules[__name__], "GOT_SAVE_CONF", False)
  with pytest.raises(SystemExit) as error:
    vanguards.main.main()
  assert error.value.code == 1
  assert "Cannot configure guards" in caplog.text
  assert not GOT_SAVE_CONF
  assert not (tmp_path / "state").exists()

def test_oneshot_requires_addon_guard_management(monkeypatch):
  vanguards.config.apply_config(DEFAULT_CONFIG)
  monkeypatch.setattr(vanguards.config, "ENABLE_VANGUARDS", True)
  monkeypatch.setattr(sys, "argv", ["vanguards", "--one_shot_vanguards", "--disable_vanguards"])
  monkeypatch.setattr(sys.modules[__name__], "GOT_SAVE_CONF", False)
  with pytest.raises(SystemExit) as error:
    vanguards.main.main()
  assert error.value.code == 1
  assert not GOT_SAVE_CONF

@pytest.mark.parametrize("bandguards", [False, True])
def test_monitoring_only_leaves_tor_settings_owned_by_tor(monkeypatch, tmp_path, bandguards):
  vanguards.config.apply_config(DEFAULT_CONFIG)
  monkeypatch.setattr(vanguards.config, "ENABLE_PATHVERIFY", False)
  monkeypatch.setattr(sys.modules[__name__], "TOR_VERSION", stem.version.Version("0.4.9.17"))
  monkeypatch.setattr(vanguards.main.time, "sleep", lambda _: None)
  subscribed = set()
  writes = []
  monkeypatch.setattr(MockController, "add_event_listener",
                      lambda controller, handler, *events: subscribed.update(events))
  monkeypatch.setattr(MockController, "set_conf", lambda controller, *setting: writes.append(setting))
  monkeypatch.setattr(vanguards.config, "ENABLE_VANGUARDS", True)
  arguments = ["vanguards", "--disable_vanguards", "--disable_logguard",
               "--state", str(tmp_path / "state")]
  if not bandguards:
    arguments.append("--disable_bandguards")
  monkeypatch.setattr(sys, "argv", arguments)
  vanguards.main.main()
  assert "CIRC" in subscribed and "NEWCONSENSUS" in subscribed
  assert ("CIRC_BW" in subscribed) == bandguards
  assert "SIGNAL" not in subscribed and not writes

def test_bandguards_config_file_opt_out(monkeypatch, tmp_path):
  vanguards.config.apply_config(DEFAULT_CONFIG)
  config = tmp_path / "vanguards.conf"
  config.write_text("[Global]\nenable_bandguards = False\n")
  monkeypatch.setattr(vanguards.config, "ENABLE_BANDGUARDS", True)
  monkeypatch.setattr(sys, "argv", ["vanguards", "--config", str(config),
                                   "--disable_vanguards", "--disable_rendguard"])
  monkeypatch.setattr(vanguards.main.time, "sleep", lambda _: None)
  subscribed = []
  monkeypatch.setattr(MockController, "add_event_listener",
                      lambda controller, handler, *events: subscribed.extend(events))
  vanguards.main.main()
  assert not vanguards.config.ENABLE_BANDGUARDS
  assert "CIRC_BW" not in subscribed and "NETWORK_LIVENESS" not in subscribed

def test_managed_reload_only_reapplies_guard_settings(monkeypatch, tmp_path):
  vanguards.config.apply_config(DEFAULT_CONFIG)
  monkeypatch.setattr(sys.modules[__name__], "TOR_VERSION", stem.version.Version("0.4.9.17"))
  monkeypatch.setattr(vanguards.main.time, "sleep", lambda _: None)
  handlers = []
  writes = []

  def subscribe(controller, handler, *events):
    if "SIGNAL" in events:
      handlers.append(handler)

  get_conf = MockController.get_conf
  monkeypatch.setattr(MockController, "get_conf", lambda controller, key, default=None:
                      "1" if key == "ConfluxEnabled" else get_conf(controller, key, default))
  monkeypatch.setattr(MockController, "add_event_listener", subscribe)
  monkeypatch.setattr(MockController, "set_conf", lambda controller, key, value: writes.append(key))
  state = vanguards.main.vanguards.VanguardState(str(tmp_path / "state"))
  assert vanguards.main.control_loop(state) == "closed"
  writes.clear()
  event = stem.response.ControlMessage.from_str("650 SIGNAL RELOAD\r\n", "EVENT")
  for handler in handlers:
    handler(event)
  assert set(writes) == {"HSLayer2Nodes", "HSLayer3Nodes", "NumEntryGuards", "NumDirectoryGuards"}

@pytest.mark.parametrize("recover_on_bw", [False, True])
def test_bandguards_stays_active_while_consensus_is_unavailable(monkeypatch, tmp_path, recover_on_bw):
  vanguards.config.apply_config(DEFAULT_CONFIG)
  monkeypatch.setattr(sys.modules[__name__], "TOR_VERSION", stem.version.Version("0.4.9.17"))
  monkeypatch.setattr(sys.modules[__name__], "DATA_DIR", str(tmp_path))
  monkeypatch.setattr(vanguards.main.time, "sleep", lambda _: None)
  now = 0
  monkeypatch.setattr(vanguards.main.time, "monotonic", lambda: now)
  handlers = {}
  rendguard_calls = []
  state = vanguards.main.vanguards.VanguardState(str(tmp_path / "state"))
  monkeypatch.setattr(type(state.rendguard), "circ_event",
                      lambda guard, controller, event: rendguard_calls.append(event))

  def subscribe(controller, handler, *events):
    for event in events:
      handlers.setdefault(event, []).append(handler)

  monkeypatch.setattr(MockController, "add_event_listener", subscribe)
  monkeypatch.setattr(MockController, "remove_event_listener",
                      lambda controller, handler: handlers["BW"].remove(handler), raising=False)
  assert vanguards.main.control_loop(state) == "closed"
  assert "CIRC_BW" in handlers and "NEWCONSENSUS" in handlers
  event = object()
  handlers["CIRC"][0](event)
  assert not rendguard_calls
  assert not (tmp_path / "state").exists()

  retry = handlers["BW"][-1]
  retry(event)
  assert retry in handlers["BW"] and not (tmp_path / "state").exists()
  shutil.copy("tests/cached-microdesc-consensus", tmp_path)
  if recover_on_bw:
    retry(event)
    assert not (tmp_path / "state").exists()
    now = vanguards.main._CONSENSUS_RETRY_SECONDS
    retry(event)
  else:
    handlers["NEWCONSENSUS"][0](event)
    retry(event)
  assert retry not in handlers["BW"]
  handlers["CIRC"][0](event)
  assert rendguard_calls == [event]
  assert (tmp_path / "state").is_file()

def test_fatal_consensus_callback_exits_the_control_loop(monkeypatch, tmp_path):
  vanguards.config.apply_config(DEFAULT_CONFIG)
  state = vanguards.main.vanguards.VanguardState(str(tmp_path / "state"))
  returned = []

  def update(controller, event, *, require_guards=False):
    if event is None:
      raise stem.DescriptorUnavailable("No consensus yet")
    raise SystemExit(1)

  def subscribe(controller, handler, *events):
    if "NEWCONSENSUS" in events:
      handler(object())
      returned.append(True)

  monkeypatch.setattr(state, "new_consensus_event", update)
  monkeypatch.setattr(MockController, "add_event_listener", subscribe)
  with pytest.raises(SystemExit) as exc:
    vanguards.main.control_loop(state)
  assert exc.value.code == 1 and returned

def test_reload_during_initial_consensus_is_reapplied(monkeypatch, tmp_path):
  vanguards.config.apply_config(DEFAULT_CONFIG)
  state = vanguards.main.vanguards.VanguardState(str(tmp_path / "state"))
  signals = []
  reapplied = []
  reload_lock = vanguards.main.Lock()
  monkeypatch.setattr(vanguards.main, "Lock", lambda: reload_lock)
  reload_event = stem.response.ControlMessage.from_str("650 SIGNAL RELOAD\r\n", "EVENT")

  def subscribe(controller, handler, *events):
    if "SIGNAL" in events:
      signals.append(handler)

  def update(controller, event, *, require_guards=False):
    signals[0](reload_event)
    assert not reapplied

  monkeypatch.setattr(MockController, "add_event_listener", subscribe)
  monkeypatch.setattr(state, "new_consensus_event", update)
  monkeypatch.setattr(state, "signal_event",
                      lambda controller, event: reapplied.append((event, reload_lock.locked())))
  monkeypatch.setattr(vanguards.main.time, "sleep", lambda _: None)
  assert vanguards.main.control_loop(state) == "closed"
  assert reapplied == [(reload_event, True)]
