from vanguards.vanguards import VanguardState
from stem.response import ControlMessage

state = VanguardState.read_from_file(open("tests/state.mock", "rb"))

# Test plan:
# - Load a routerlist using stem
# - Perform basic rank checks from sort_and_index
# - Reset expiration times on layer2+layer3
# - Remove a layer2 guard from it
# - Remove a layer3 guard from it
# - Mark a layer2 guard way in the past
# - Mark a layer3 guard way in the past
# - Update the consensus.
# - Remove all guards from consensus
# - Update the consensus.
# - Mark all guards way in the past

def test_vanguards():
  assert True
