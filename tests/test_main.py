import sys
import stem

import stem.control
import vanguards.control
import vanguards.config
import vanguards.main

class MockController:
  def __init__(self):
    self.alive = True

  @staticmethod
  def from_port(ip, port):
    return MockController()

  @staticmethod
  def from_socket(infile):
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
    pass

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
vanguards.config.CBTVERIFY_ENABLED = True
vanguards.config.STATE_FILE = "tests/state.mock"

# TODO: Write config+argparsing tests
def test_main():
  sys.argv = ["test_main"]
  vanguards.main.main()
