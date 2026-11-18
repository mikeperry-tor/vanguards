# The Vanguards Onion Service Addon

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
2. Use Python 3.11 or later and [install Stem](https://stem.torproject.org/download.html) 1.8.0 or later.
3. Run `python3 src/vanguards.py`.

By default, Vanguards first tries `/run/tor/control`, then asks Stem to try
local control ports 9051 and 9151 in that order.

If your control port is on an alternate IP and Port, specify that with
**--control_ip _IP_ --control_port _portnum_**.

If you are using a different control socket path, specify its full path with
**--control_socket /path/to/socket**.

Use `python3 src/vanguards.py --help` to see the other options.

## Installing this checkout in a virtual environment

Use Python 3.11 or later. The helper creates a virtual environment, installs
the hash-pinned runtime dependency, and builds and installs this checkout.
The build backend is resolved separately by pip.

```
./setup.sh
vanguardenv/bin/vanguards --help
```

Pass a different destination as the first argument. To select an interpreter
with `PYTHON`, use a new destination. Running the helper again without `PYTHON`
reuses the existing environment. To install directly, run
`python -m pip install .` inside your virtual environment.

## Pip

This project is also listed on the Python Package Index. To install the
latest release via pip **without any verification**, do:

```
torsocks pip install vanguards
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
  python3 src/vanguards.py
```

If you also have a system Tor, you will need to specify Tor Browser's control
port with `--control_port 9151`

To use it with Onionshare, set up your Tor to expose a control port and attach
both onionshare and the vanguards addon to it.

## Performance Tuning

For high-traffic onion services, you can try running Vanguards components in parallel, so that
the system does not bottleneck on one CPU core. A simple test script called
[vanguards\_parallel.sh](https://github.com/mikeperry-tor/vanguards/blob/master/vanguards_parallel.sh)
is available to try this. If it helps,
[please let us know](https://github.com/mikeperry-tor/vanguards/issues/62)!

Vanguards by itself should not require much overhead, but if even that is too
much, you can run the following once per hour from cron to update your torrc
with fresh layer2 and layer3 guards:

```
  python3 src/vanguards.py --one_shot_vanguards
```

One-shot mode requires addon-managed guards and a usable consensus. It reports
a failure and leaves Tor's saved configuration alone if guard setup cannot
be completed.

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

