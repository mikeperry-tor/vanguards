import sys
import stem

import stem.control
import vanguards.control
import vanguards.config
import vanguards.main

GOT_SOCKET = ""

class MockController:
  def __init__(self):
    self.alive = True

  @staticmethod
  def from_port(ip, port):
    return MockController()

  @staticmethod
  def from_socket_file(infile):
    global GOT_SOCKET
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
    return stem.version.Version("0.3.3.5-rc-dev")

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

  # XXX: Test fail to read config file (and add better error reporting)

  # XXX: Test fail to read state file


# XXX: Test connection failures for socket+ file
# XXX: Test password auth (and password auth should warn to use cookie auth)
# XXX: Test no auth (and no auth should warn to use cookie auth)
def test_failures():
  pass
