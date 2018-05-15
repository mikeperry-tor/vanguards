from vanguards.vanguards import VanguardState
from stem.response import ControlMessage

state = VanguardState.read_from_file(open("tests/state.mock", "rb"))

# Test plan:
# - Test HS client rend -- should do nothing
# - Test lots of hs service rends - should complain
# - Test scaling

def test_parsecirc():
  assert True
