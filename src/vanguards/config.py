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

################### RendWatcher Options ###############
# Use count limits. These limits control when we emit warnings about circuits
#
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

################# Control options ##################
CONTROL_HOST = "127.0.0.1"
CONTROL_PORT = 9051
CONTROL_SOCKET = None

def setup_options():
  global CONTROL_HOST, CONTROL_PORT, CONTROL_SOCKET

  # XXX: Enable/disable for circ handlers
  # XXX: Config file for other options
  parser = argparse.ArgumentParser()
  parser.add_argument("--state_file", dest="state_file", default="vanguards.state",
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

  options = parser.parse_args()

  (CONTROL_HOST, CONTROL_PORT, CONTROL_SOCKET) = \
      (options.control_host, options.control_port, options.control_socket)

  return options


