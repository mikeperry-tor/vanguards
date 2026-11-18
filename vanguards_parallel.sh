#!/bin/sh -e

# This script launches three vanguard components in parallel, logging to
# syslog.
#
# This prevents vanguards from bottlenecking on a single CPU core.
#
# However, the bandguards instance may still require high CPU, since it
# listens to many events. Let us know if this script helps or does not help
# by commenting on: https://github.com/mikeperry-tor/vanguards/issues/62


VANGUARDS_SOURCE="$(dirname "$0")/src/vanguards.py"
VANGUARDS_LOCATION=
if [ ! -f "$VANGUARDS_SOURCE" ]; then
    VANGUARDS_LOCATION=$(command -v vanguards) || {
        printf '%s\n' 'Cannot find the vanguards command on PATH.' >&2
        exit 1
    }
fi

run_vanguards() {
    if [ -n "$VANGUARDS_LOCATION" ]; then
        exec "$VANGUARDS_LOCATION" "$@"
    else
        exec python3 "$VANGUARDS_SOURCE" "$@"
    fi
}

# Vanguards instance
run_vanguards --disable_bandguards --disable_rendguard --logfile :syslog: "$@" &

# Bandguards instance
run_vanguards --disable_vanguards --disable_rendguard --logfile :syslog: "$@" &

# Rendguard instance
run_vanguards --disable_vanguards --disable_bandguards --parallel_rendguard_state --logfile :syslog: "$@" &

jobs -l

echo
echo "Vanguards is now running in the background as the above jobs."
echo "Note that they log to syslog to avoid overwriting eachother's logs"
echo
echo "If you still are experiencing high CPU from the vanguards process,"
echo "remember that it can be run with --one_shot_vanguards, once per hour"
echo "from cron."
