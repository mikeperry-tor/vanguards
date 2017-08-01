#!/bin/bash -e

THIS_DIR=$(dirname "$0")
THIS_DIR=$(readlink -f "$THIS_DIR")

PYTHON=$(which python2.6 || which python2.7)

# 1. Install python if needed
if [ -z "$(which $PYTHON)" ]
then
  echo "We need python2.6 or 2.7 to be in the path."
  echo "If you are on a Debian or Ubuntu system, you can try: "
  echo " sudo apt-get install python2.7 python-virtualenv"
  exit 1
fi

if [ -z "$(which virtualenv)" ]
then
  echo "We need virtualenv to be in the path. If you are on a debian system, try:"
  echo " sudo apt-get install python-virtualenv"
  exit 1
fi

# 2. Initialize virtualenv
if [ ! -f vanguardenv/bin/activate ]
then
  virtualenv -p $PYTHON vanguardenv
fi
source vanguardenv/bin/activate

# Not needed: Install new pip and peep
#pip install --upgrade https://pypi.python.org/packages/source/p/pip/pip-6.1.1.tar.gz#sha256=89f3b626d225e08e7f20d85044afa40f612eb3284484169813dc2d0631f2a556
#pip install https://pypi.python.org/packages/source/p/peep/peep-2.4.1.tar.gz#sha256=2a804ce07f59cf55ad545bb2e16312c11364b94d3f9386d6e12145b2e38e5c1c
#peep install -r $SCANNER_DIR/requirements.txt

# 3. Install stem
pip install https://pypi.python.org/packages/b3/4e/fc6bb6262fa9ca1b308aa735fc2186586106cef0cb4b4ba80aaaa3c9a071/stem-1.5.4.tar.gz#sha256=3649133037ee186e80115650094a2fb2f60a23f006ebddab34d9039be9b2f7c8

# 4. Inform user what to do
echo
echo "If we got this far, everything should be ready!"
echo
