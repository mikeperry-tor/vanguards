#!/bin/bash -e

SYS_PYTHON=$(which pypy3 || which pypy || which pypy2)

if [ -z $1 ]
then
  DEST=vanguardenv
else
  DEST=$1
fi

mkdir -p $DEST

# 1. Install python if needed
if [ -z "$(which $SYS_PYTHON)" ]
then
  echo "We need pypy or pypy3 to be in the path."
  echo
  echo "If you are on a Debian or Ubuntu system, you can try: "
  echo " sudo apt-get install pypy virtualenv"
  echo
  echo "If there is no pypy for your arch, edit this script to set"
  echo "SYS_PYTHON=\"python\""
  exit 1
fi

if [ -z "$(which virtualenv)" ]
then
  echo "We need virtualenv to be in the path. If you are on a debian system, try:"
  echo " sudo apt-get install virtualenv"
  exit 1
fi

# 2. Initialize virtualenv
if [ ! -f ${DEST}/bin/activate ]
then
  virtualenv --never-download -p $SYS_PYTHON $DEST
fi
source ${DEST}/bin/activate

# 3. Install stem+setuptools
pip install --require-hashes -r requirements.txt

$(basename $SYS_PYTHON) setup.py install

# 4. Inform user what to do
echo
echo "If we got this far, everything should be ready!"
echo
echo "Run 'source ${DEST}/bin/activate' to start the environment."
echo
echo "Then run 'vanguards' or './vanguards_parallel.sh'"
