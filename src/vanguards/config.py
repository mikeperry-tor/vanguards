""" This file contains configuration defaults, options parsing, and config
    file code.
"""
import argparse

################### Vanguard options ##################
#
NUM_LAYER1_GUARDS = 2 # 0 is Tor default
NUM_LAYER2_GUARDS = 4
NUM_LAYER3_GUARDS = 8

# In days:
LAYER1_LIFETIME = 0 # Use tor default

# In hours
MIN_LAYER2_LIFETIME = 24*1
MAX_LAYER2_LIFETIME = 24*45

# In hours
MIN_LAYER3_LIFETIME = 1
MAX_LAYER3_LIFETIME = 48

# State file location
STATE_FILE = "vanguards.state"

################### RendWatcher Options ###############
# Use count prefs. These limits control when we emit warnings about circuits

# Are use counts enabled?
RENDWATCHER_ENABLED=True

# Minimum number of hops we have to see before applying use stat checks
USE_COUNT_TOTAL_MIN = 100

# Number of hops to scale counts down by two at
USE_COUNT_SCALE_AT = 1000

# Minimum number of times a relay has to be used before we check it for
# overuse
USE_COUNT_RELAY_MIN = 10

# How many times more than its bandwidth must a relay be used?
USE_COUNT_RATIO = 2.0

############ BandGuard Options #################

BANDGUARDS_ENABLED=True

# Kill a circuit if this much received bandwidth is not application related.
# This prevents an adversary from inserting cells that are silently dropped
# into a circuit, to use as a timing side channel.
BW_CIRC_MAX_DROPPED_READ_RATIO = 0.025

# Kill a circuit if this many read+write bytes have been exceeded.
# Very loud application circuits could be used to introduce timing
# side channels.
# Warning: if your application has large resources that cannot be
# split up over multipe requests (such as large HTTP posts for eg:
# securedrop), you must set this higher.
BW_CIRC_MAX_BYTES = 100*1024*1024 # 100M

# Kill circuits older than this many seconds.
# Really old circuits will continue to use old guards after the TLS connection
# has rotated, which means they will be alone on old TLS links. This lack
# of multiplexing may allow an adversary to use netflow records to determine
# the path through the Tor network to a hidden service.
BW_CIRC_MAX_AGE = 24*60*60 # 1 day

# Maximum size for an hsdesc fetch (including setup+get+dropped cells)
BW_CIRC_MAX_HSDESC_BYTES = 30*1024 # 30k

################# CBT Options ####################

CBTVERIFY_ENABLED=False

################# Control options ##################
CONTROL_HOST = "127.0.0.1"
CONTROL_PORT = 9051
CONTROL_SOCKET = None

def setup_options():
  global CONTROL_HOST, CONTROL_PORT, CONTROL_SOCKET, STATE_FILE
  global BANDGUARDS_ENABLED, RENDWATCHER_ENABLED, CBTVERIFY_ENABLED

  # XXX: Config file for other options
  parser = argparse.ArgumentParser()
  parser.add_argument("--state_file", dest="state_file", default=STATE_FILE,
                    help="File to store vanguard state (default: DataDirectory/vanguards)")

  parser.add_argument("--control_host", dest="control_host", default=CONTROL_HOST,
                    help="The IP address of the Tor Control Port to connect to (default: "+
                    CONTROL_HOST+")")
  parser.add_argument("--control_port", type=int, dest="control_port",
                      default=CONTROL_PORT,
                      help="The Tor Control Port to connect to (default: "+
                      str(CONTROL_PORT)+")")

  parser.add_argument("--control_socket", dest="control_socket",
                      default=CONTROL_SOCKET,
                      help="The Tor Control Socket path to connect to "+
                      "(default: "+str(CONTROL_SOCKET)+")")

  parser.add_argument("--disable-bandguards", dest="bandguards_enabled",
                      action="store_false",
                      help="Disable circuit side channel checks (may help performance)")
  parser.set_defaults(bandguards_eabled=BANDGUARDS_ENABLED)

  parser.add_argument("--disable-rendwatcher", dest="rendwatcher_enabled",
                      action="store_false",
                      help="Disable rendezvous misuse checks (may help performance)")
  parser.set_defaults(rendwatcher_enabled=RENDWATCHER_ENABLED)

  parser.add_argument("--enable-cbtverify", dest="cbtverify_enabled",
                      action="store_true",
                      help="Enable Circuit Build Time monitoring")
  parser.set_defaults(cbtverify_enabled=CBTVERIFY_ENABLED)

  options = parser.parse_args()

  (STATE_FILE, CONTROL_HOST, CONTROL_PORT, CONTROL_SOCKET, BANDGUARDS_ENABLED,
   RENDWATCHER_ENABLED, CBTVERIFY_ENABLED) = \
      (options.state_file, options.control_host, options.control_port,
       options.control_socket, options.bandguards_enabled,
       options.rendwatcher_enabled,options.cbtverify_enabled)

  return options


