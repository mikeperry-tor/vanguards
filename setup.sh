#!/bin/sh -e

DEST="${1}"
DEST="${DEST:=vanguardenv}"
mkdir -p "${DEST}"

SYS_PYTHON=$(command -v pypy3 || command -v pypy || command -v pypy2)

# 1. Install python if needed
if [ -z "${SYS_PYTHON}" ]; then
  printf "We need pypy or pypy3 to be in the path.\n
  \b\bIf you are on a Debian or Ubuntu system, you can try:
  \tsudo apt-get install pypy virtualenv\n
  \b\bIf there is no pypy for your arch, edit this script to set
  \tSYS_PYTHON=\"python\"\n"
  exit 1
fi

if [ -z "$(command -v virtualenv)" ]; then
  printf "We need virtualenv to be in the path. If you are on a debian system, try:
  \tsudo apt-get install virtualenv\n"
  exit 1
fi

# 2. Initialize virtualenv
[ ! -f "${DEST}"/bin/activate ] && virtualenv --never-download -p "${SYS_PYTHON}" "${DEST}"
. "${DEST}"/bin/activate

# 3. Install stem+setuptools
pip install --require-hashes -r requirements.txt

BASE_SYS_PYTHON=${SYS_PYTHON##*/}
"${BASE_SYS_PYTHON}" setup.py install

# 4. Inform user what to do
printf %s"\nIf we got this far, everything should be ready!\n
Run '. ${DEST}/bin/activate' to start the environment.\n
Then run 'vanguards' or './vanguards_parallel.sh'\n"
