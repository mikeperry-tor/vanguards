# The Vanguards Onion Service Addon

[![Build Status](https://travis-ci.org/mikeperry-tor/vanguards.png?branch=master)](https://travis-ci.org/mikeperry-tor/vanguards) [![Coverage Status](https://coveralls.io/repos/github/mikeperry-tor/vanguards/badge.png?branch=master)](https://coveralls.io/github/mikeperry-tor/vanguards?branch=master)

Even after deployment of the [new v3 onion service
protocol](https://gitweb.torproject.org/torspec.git/tree/proposals/224-rend-spec-ng.txt),
the attacks facing onion services are wide-ranging, and still require
more extensive modifications to fix in Tor-core itself.

Because of this, we have decided to rapid-prototype these defenses in a
controller addon in order to make them available ahead of their official
Tor-core release, for onion services that require high security as soon as
possible.

For details about the defenses themselves, please see
[README\_TECHNICAL.md](https://github.com/mikeperry-tor/vanguards/blob/master/README_TECHNICAL.md).

For additional security information, please see
[README\_SECURITY.md](https://github.com/mikeperry-tor/vanguards/blob/master/README_SECURITY.md).

# Installation Methods

There are several ways to use this addon.

Packages for debian-like systems exist, but they are typically out of date.
Check backports, if you're lucky it might get updated there.

If you are using this addon with a system tor, and not using a system
vanguards package, you will need to run the following as the system Tor user,
because this addon needs access to Tor's data directory. To do this on
debian-like systems, do:

```
  sudo -u debian-tor bash
```

Then, run all of the following as the `debian-tor` user.

## Running this addon directly from git

**This is the safest option to use, since it avoids having pip and/or
virtualenv download packages from PYPI without verification.**

1. Retrieve this repository and optionally verify a signed git version tag.
2. [Install Stem](https://stem.torproject.org/download.html)
3. Run **./src/vanguards.py**

By default, vanguards will try to connect to "/run/tor/control", and if that
fails, will try control port 9051 (System Tor), and then 9151 (Tor Browser).

If your control port is on an alternate IP and Port, specify that with
**--control_host _IP_ --control_port _portnum_**.

If you are using a different control socket path, specify its full path with
**--control_socket /path/to/socket**.

Note that **./src/vanguards.py** has several other options under **--help**.

## Using VirtualEnv

**This option tells virtualenv not to download packages, and only downloads
pip packages with --require-hashes. It should be safe.**

To install Stem and Vanguards into their own python virtualenv, run:

```
torsocks ./setup.sh
source vanguardenv/bin/activate
vanguards
```

If you do not want your environment to be in the vanguardenv subdirectory, you
can specify a different directory as an argument to **setup.sh**.

## Pip

This project is also listed on the Python Package Index. To install the
latest release via pip **without any verification**, do:

```
torsocks pip install vanguards
```

If your distribution provides pypy3 (see
[Performance Tuning](#performance-tuning)), you can do:

```
torsocks pypy3 -m pip install vanguards
```

# How to use the addon

## Configuration

All of the subsystems of this addon can be tuned via a configuration file.
Check out this documented [example configuration file](https://github.com/mikeperry-tor/vanguards/blob/master/vanguards-example.conf) for more information.

Configuration files can be specified on the command line. The default is to
read **vanguards.conf** from the current working directory. If the environment
variable **$VANGUARDS\_CONFIG** is set, the config file will be read from the
file specified in that variable.

## Onion service use

This addon is primarily intended for onion service operators. To use it,
set up your onion service to expose a control port listener using the
ControlPort or ControlSocket torrc directives:

```
ControlPort 9099             # or ControlSocket /path/to/socket
CookieAuthentication 1
DataDirectory /path/to/tor/datadir
```

and then run:

```
vanguards --control_port 9099     # (or --control_socket /path/to/socket).
```

## Client use

It is also possible to use the vanguards addon as a regular Tor client with
Tor Browser or with Onionshare.

To use it with Tor Browser, all you have to do is start Tor Browser, and then run:
```
  ./src/vanguards.py
```

If you also have a system Tor, you will need to specify Tor Browser's control
port with `--control_port 9151`

To use it with Onionshare, set up your Tor to expose a control port and attach
both onionshare and the vanguards addon to it.

## Performance Tuning

For very high traffic onion services, we recommend using
[PyPy](https://pypy.org) instead of CPython. PyPy contains a JIT that should
make this addon run considerably faster.

The easiest way to use PyPy is to do **sudo apt-get install pypy3** or
equivalent before running **./setup.sh** as per above. The setup.sh script will
then see that pypy is installed, and use it by default in the resulting
virtualenv.

To switch to pypy after running **setup.sh**, simply remove the vanguardenv
directory and run **setup.sh** again.

If you want to use pypy outside of a virtualenv, install Stem 1.7.0 or later
on your system, and then run the addon directly from the source tree with:

```
  pypy3 ./src/vanguards.py
```

Additionally, you can try running vanguards components in parallel, so that
the system does not bottleneck on one CPU core. A simple test script called
[vanguards\_parallel.sh](https://github.com/mikeperry-tor/vanguards/blob/master/vanguards_parallel.sh)
is available to try this. If it helps,
[please let us know](https://github.com/mikeperry-tor/vanguards/issues/62)!

Vanguards by itself should not require much overhead, but if even that is too
much, you can run the following once per hour from cron to update your torrc
with fresh layer2 and layer3 guards:

```
  ./src/vanguards.py --one_shot_vanguards
```

# What do the logs mean?

This is an experimental addon with many heuristics that still need tuning.
Events that represent severe issues are at WARN level. You should
[react to these events](https://github.com/mikeperry-tor/vanguards/blob/master/README_SECURITY.md#monitor-your-service).

Warns are currently emitted for the following conditions:

1. When your service is disconnected from the Tor network, we WARN. Downtime
can be a side channel signal or a passive information leak,
and you should ensure your Internet connection is reliable to minimize
downtime of your service as much as possible.
2. When a hidden service descriptor circuit sends more than 30KB, we WARN. If this
happens, it is either a bug, a heavily-modified hidden service descriptor,
or an actual attack.
3. When you set ExcludeNodes in Tor to exclude countries, but do not give
Tor a GeoIP file, we WARN.
4. If you disable killing circuits in the rendguard component, we WARN when
use counts for rends are exceeded.
5. We WARN upon receipt of any cell that the Tor client drops or ignores.
6. If you enable introduction circuit rate limiting, a WARN is emitted when
introduction circuits are killed.

Events that are detected by heuristics that still need tuning are at NOTICE
level. They may be a bug, a false positive, or an actual attack. If in doubt,
don't panic. Please check the [Github
issues](https://github.com/mikeperry-tor/vanguards/issues/) to see if any
known false positives are related to these lines, and if not, consider filing
an issue. Please redact any relay fingerprints from the messages before
posting.

# What else should I read?

For technical details about the defenses that this addon provides, please see
[README\_TECHNICAL.md](https://github.com/mikeperry-tor/vanguards/blob/master/README_TECHNICAL.md).

For additional security information, please see
[README\_SECURITY.md](https://github.com/mikeperry-tor/vanguards/blob/master/README_SECURITY.md).

