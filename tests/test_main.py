import sys
import stem

import vanguards.control
import vanguards.config
import vanguards.main

class MockController:
  def __init__(self):
    pass

  # FIXME: os.path.join
  def get_network_statuses(self):
    return list(stem.descriptor.parse_file("tests/cached-microdesc-consensus",
                   document_handler =
                      stem.descriptor.DocumentHandler.ENTRIES))

  def add_event_listener(self, func, ev):
    pass

  def get_conf(self, key):
    if key == "DataDirectory":
      return "tests"

  def set_conf(self, key, val):
    pass

  def save_conf(self):
    pass

  def is_alive(self):
    return False

def mock_connect():
  return MockController()
vanguards.control.connect = mock_connect

# TODO: Write config+argparsing tests
def test_main():
  sys.argv = ["test_main"]
  vanguards.main.main()
