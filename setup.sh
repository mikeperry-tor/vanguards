#!/bin/bash
set -e

repo_dir=$(cd -- "$(dirname -- "$0")" && pwd)
destination=${1:-vanguardenv}

if [ -f "$destination/pyvenv.cfg" ]; then
  if [ -n "${PYTHON:-}" ]; then
    printf 'Choose a new destination when selecting PYTHON.\n' >&2
    exit 1
  fi
else
  "${PYTHON:-python3}" -m venv "$destination"
fi

"$destination/bin/python" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else "Vanguards requires Python 3.11 or later. Choose a new destination.")'
"$destination/bin/python" -m pip install --require-hashes -r "$repo_dir/requirements.txt"
"$destination/bin/python" -m pip install --no-deps "$repo_dir"

printf 'Installed Vanguards in %s.\n' "$destination"
printf 'Run %q/bin/vanguards --help to see the available options.\n' "$destination"
