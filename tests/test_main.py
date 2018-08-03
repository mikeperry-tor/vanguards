import sys
import stem
import getpass
import os
import shutil

import stem.control
import vanguards.control
import vanguards.config
import vanguards.main

GOT_SOCKET = ""
THROW_SOCKET = False
THROW_AUTH = False
DATA_DIR = "tests"
NO_HSLAYER = False
TOR_VERSION = stem.version.Version("0.3.4.4-rc")
DEFAULT_CONFIG=os.path.join("tests", "default.conf")
GOT_SAVE_CONF = False
FAIL_SAVE_CONF = False

class MockController:
  def __init__(self):
    self.alive = True

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

  # FIXME: os.path.join
  def get_network_statuses(self):
    return list(stem.descriptor.parse_file("tests/cached-microdesc-consensus",
                   document_handler =
                      stem.descriptor.DocumentHandler.ENTRIES))

  def add_event_listener(self, func, ev):
    pass

  def authenticate(self, password=None):
    if THROW_AUTH:
      raise stem.connection.AuthenticationFailure("Bad")
    if password == None:
      raise stem.connection.MissingPassword("Bad")
    elif password != "foo":
      raise stem.connection.PasswordAuthFailed("Bad")

  def get_version(self):
    return TOR_VERSION

  def get_conf(self, key):
    if key == "DataDirectory":
      return DATA_DIR

  def get_info(self, key, default=None):
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

stem.control.Controller = MockController
vanguards.config.ENABLE_CBTVERIFY = True
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
  sys.argv = ["test_main", "--config", "tests/conf.mock"]
  vanguards.main.main()
  assert GOT_SOCKET == "conf.sock"

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
  try:
    vanguards.main.main()
    assert False
  except SystemExit:
    assert True

  # Test bogus DataDirectory
  vanguards.config.apply_config(DEFAULT_CONFIG)
  DATA_DIR = "/.bogus23"
  sys.argv = ["test_main" ]
  try:
    vanguards.main.main()
    assert False
  except SystemExit:
    assert True
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
