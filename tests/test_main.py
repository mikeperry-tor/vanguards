import sys
import stem

import stem.control
import vanguards.control
import vanguards.config
import vanguards.main

GOT_SOCKET = ""
THROW_SOCKET = None
TOR_VERSION = stem.version.Version("0.3.4.0-alpha")

class MockController:
  def __init__(self):
    self.alive = True

  @staticmethod
  def from_port(ip, port):
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

  def authenticate(self):
    pass

  def get_version(self):
    return TOR_VERSION

  def get_conf(self, key):
    if key == "DataDirectory":
      return "tests"

  def set_conf(self, key, val):
    pass

  def save_conf(self):
    pass

  def is_alive(self):
    if self.alive:
      self.alive = False
      return True
    return False


stem.control.Controller = MockController
vanguards.config.ENABLE_CBTVERIFY = True
vanguards.config.STATE_FILE = "tests/state.mock"

def test_main():
  sys.argv = ["test_main"]
  vanguards.main.main()

# Test plan:
# - Test ability to override CONTROL_SOCKET
#   - Via conf file
#   - Via param
#   - Verify override
# TODO: - Test other params too?
def test_configs():
  global GOT_SOCKET
  sys.argv = ["test_main", "--control_socket", "arg.sock" ]
  vanguards.main.main()
  assert GOT_SOCKET == "arg.sock"

  sys.argv = ["test_main", "--config", "tests/conf.mock"]
  vanguards.main.main()
  assert GOT_SOCKET == "conf.sock"

  sys.argv = ["test_main", "--control_socket", "arg.sock", "--config", "tests/conf.mock" ]
  EXPECTED_SOCKET = "arg.sock"
  vanguards.main.main()
  assert GOT_SOCKET == "arg.sock"

  # TODO: Check that this is sane
  sys.argv = ["test_main", "--generate_config", "wrote.conf" ]
  try:
    vanguards.main.main()
    assert False
  except SystemExit:
    assert True

def test_failures():
  global THROW_SOCKET
  global TOR_VERSION
  # Test fail to read config file
  sys.argv = ["test_main", "--config", "None.conf" ]
  try:
    vanguards.main.main()
    assert False
  except SystemExit:
    assert True

  # Test fail to read state file
  sys.argv = ["test_main", "--state", "None.state" ]
  vanguards.main.main()

  # Test connection failures for socket+ file
  sys.argv = ["test_main", "--control_socket", "None.conf" ]
  THROW_SOCKET=True
  try:
    vanguards.main.main()
    assert False
  except SystemExit:
    assert True

  # Cover unsupported Tor version
  THROW_SOCKET=False
  TOR_VERSION=stem.version.Version("0.3.3.5-rc-dev")
  try:
    vanguards.main.main()
    assert True
  except SystemExit:
    assert False

  # Test loglevel and log failure
  sys.argv = ["test_main", "--loglevel", "INFOg" ]
  try:
    vanguards.main.main()
    assert False
  except SystemExit:
    assert True

  # Test loglevel and log failure
  sys.argv = ["test_main", "--loglevel", "INFO", "--logfile", "/.invalid/diaf" ]
  try:
    vanguards.main.main()
    assert False
  except SystemExit:
    assert True

  # Test loglevel and log success
  sys.argv = ["test_main", "--loglevel", "INFO", "--logfile", "valid" ]
  try:
    vanguards.main.main()
    assert True
  except SystemExit:
    assert False

  # XXX: Test password auth (and password auth should warn to use cookie auth)
  # XXX: Test no auth (and no auth should warn to use cookie auth)
