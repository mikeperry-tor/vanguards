#!/bin/sh -e

# This script launches three vanguard components in parallel, logging to
# syslog, and ideally using pypy.
#
# This prevents vanguards from bottlenecking on a single CPU core.
#
# However, the bandguards instance may still require high CPU, since it
# listens to many events. Let us know if this script helps or does not help
# by commenting on: https://github.com/mikeperry-tor/vanguards/issues/62


# Use pypy or pypy3, if available
SYS_PY=$(which pypy3 || which pypy || which pypy2 || which python3 || which python2)

VANGUARDS_LOCATION=$(which vanguards || echo "$SYS_PY ./src/vanguards.py")

OTHER_OPTIONS="$@"

# Vanguards instance
$VANGUARDS_LOCATION --disable_bandguards --disable_rendguard --logfile :syslog: $OTHER_OPTIONS &

# Bandguards instance
$VANGUARDS_LOCATION --disable_vanguards --disable_rendguard --logfile :syslog: $OTHER_OPTIONS &

# Rendguards instance
$VANGUARDS_LOCATION --disable_vanguards --disable_bandguards --logfile :syslog: $OTHER_OPTIONS &

jobs -l

echo
echo "Vanguards is now running in the background as the above jobs."
echo "Note that they log to syslog to avoid overwriting eachother's logs"
echo
echo "If you still are experiencing high CPU from the vanguards process,"
echo "remember that it can be run with --one_shot_vanguards, once per hour"
echo "from cron."
