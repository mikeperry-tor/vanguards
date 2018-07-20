# Vanguards (and other guard discovery mitigations)

[![Build Status](https://travis-ci.org/mikeperry-tor/vanguards.png?branch=master)](https://travis-ci.org/mikeperry-tor/vanguards) [![Coverage Status](https://coveralls.io/repos/github/mikeperry-tor/vanguards/badge.png?branch=master)](https://coveralls.io/github/mikeperry-tor/vanguards?branch=master)

Even after deployment of the [new v3 onion service
protocol](https://gitweb.torproject.org/torspec.git/tree/proposals/224-rend-spec-ng.txt),
the attacks facing onion services are wide-ranging, and still require
more extensive modifications to fix in Tor-core itself.

Because of this, we have decided to rapid-prototype these defenses in a
controller script in order to make them available ahead of their official
Tor-core release, for onion services that require high security as soon as
possible.

## What sort of attacks remain?

We believe that the most serious threat that v3 onion services currently face is
guard discovery. A guard discovery attack enables an adversary to determine
the guard node(s) that are in use by a Tor client and/or Tor onion service.

Once the guard node is known, traffic analysis attacks that can deanonymize an
onion service (or onion service user) become easier.

The most basic form of this attack is to make many connections to a Tor onion
service, in order to force it to create circuits until one of the adversary's
nodes is chosen for the middle hop next to the guard. At that point, a traffic
analysis side channel is used to confirm that the node is in fact next to the
actual onion service, leading to discovery of that onion service's guard node.

From that point, the guard node can be compromised, coerced, or surveilled to
determine the actual IP address of the onion service or client.

There are other vectors of attack, too. For more information (including the
Tor Project's mitigation plans), see [the SponsorV
page](https://trac.torproject.org/projects/tor/wiki/org/sponsors/SponsorV) as
well as [the guard discovery
tag](https://trac.torproject.org/projects/tor/query?keywords=~guard-discovery)
on our bug tracker.

# What does this script do?

This script uses the [Stem Tor control port
library](https://stem.torproject.org/) to connect to a Tor control port
listening on port 9051 (or on an alternate user-specified port, or UNIX file
system socket).

It has three defense subsystems: Vanguards, Rendguard, and Bandguards.

All three subsystems apply to both service-side and client-side onion service
activity, but **NOT** to any client traffic that exits the Tor network to the
normal Internet.

## The Vanguards Subsystem

The Vanguards subsystem uses the [Tor control
protocol](https://gitweb.torproject.org/torspec.git/tree/control-spec.txt) to
select nodes from the Tor consensus for use with the torrc options HSLayer2Nodes
and HSLayer3Nodes.

Each of these options is assigned its own set of nodes, which are rotated
based on the randomized selection algorithm specified in [the Mesh Vanguards
Proposal](https://gitweb.torproject.org/torspec.git/tree/proposals/292-mesh-vanguards.txt).

The number of nodes in each of these sets, as well as the ranges on rotation
times for each set, can be specified as config file parameters. The subsystem
currently uses 2 entry guards, 3 layer2 guards, and 8 layer3 guards.

See the Configuration section of this README for config information.

## The Rendguard Subsystem

The Rendguard subsystem keeps track of how often various relays appear in the
rendezvous point position on the service side of an onion service. Since
rendezvous points are chosen by the client that connects to a service, it
is possible for clients to [choose malicious, colluding rendezvous
points](https://www.ieee-security.org/TC/SP2013/papers/4977a080.pdf) to
help them mount guard discovery and other attacks.

This subsystem emits warnings and optionally closes the circuit when a
rendezvous point is chosen more than a 2X multiple of its consensus bandwidth
weight.

## The Bandguards Subsystem

The bandguards subsystem performs accounting to watch for signs of bandwidth
sidechannel attacks on individual onion service circuits. It then closes
circuits that exceed these limits and emits log messages. While we expect the
default values to be set properly, these limits can be tuned through
configuration as well. See the Configuration section for more details.

These limits (along with a reason for checking them) are as follows:

1. ***Dropped Cell Rate***

   Back in 2014, the Tor network [was attacked](https://blog.torproject.org/tor-security-advisory-relay-early-traffic-confirmation-attack) by Carnegie Mellon researchers ([likely on behalf of the FBI)](https://blog.torproject.org/did-fbi-pay-university-attack-tor-users). The attack used was to inject a side channel using a special packet type that could be recognized at both ends of a Tor circuit.

   This side channel was fixed. Unfortunately, there are many other side channels available that allow an adversary to inject traffic that is ignored by a Tor client.

   These remaining side channels are not as severe -- they cannot immediately be recognized by colluding relays using packet information alone, instead the adversary must rely on packet volume and timing information in order to recognize the signal. However, if the volume of injected traffic is large enough or other conditions are right, [it may still be possible](https://petsymposium.org/2018/files/papers/issue2/popets-2018-0011.pdf) to use statistical methods to recover a signal.

   This option uses [new control port
features](https://trac.torproject.org/projects/tor/ticket/25903) to measure
the quantity of traffic that Tor decides to drop from a circuit. If this
quantity exceeds a specified percentage of the legitimate traffic (currently
a 11 cell circuit setup overhead, and 0% after that), then the bandguards subsystem will close the circuit and issue a warning log message.

   Note that in normal operation, Tor onion service clients may still trigger this mechanism. This is because [clients can and do close connections before reading all of the data from them](https://trac.torproject.org/projects/tor/ticket/25573). Luckily on the service side, this does not happen. For this reason, on service-side circuits, the log message emitted is at WARN level. On the client side, it is at NOTICE level. In both cases, the circuit where this happens is closed by this script as soon as the limit is reached.

2. ***Total Hidden Service Descriptor Kilobytes***

   In addition to injecting relay cells that are dropped, it is also possible for relays to inject data at the end of an onion service descriptor, or in response to an onion service descriptor submission. Tor will continue reading this data prior to attempting to parse the descriptor or response, and these parsers can be convinced to discard additional data.

   The bandguards subsystem sets a limit on the total amount of traffic allowed on onion service descriptor circuits (currently 30 kilobytes). Once this limit is exceeded, the circuit is closed and a WARN log message is emitted by the bandguards subsystem.

3. ***Total Circuit Megabytes***

   A final vector for injecting side channel traffic is at the application layer.

   If an attacker wants to introduce a side channel towards an onion service, they can fetch large quantities of data from that service, or make large HTTP posts towards the service, in order to generate detectable traffic patterns.

   These traffic patterns can be detected in Tor's public relay bandwidth statistics, as well as via netflow connection volume records. The Tor Project is currently working on various mechanisms to reduce the granularity of these statistics and has deployed padding mechanisms to limit the resolution of netflow traffic logs, but it is not clear that these mechanisms are sufficient to obscure very large volumes of traffic.

   Because of this, the bandguards subsystem has the ability to limit the
total number of bytes sent over a circuit before a WARN is emitted and the
circuit is closed.  This limit is currently set to 0 (which means unlimited).
If you know a reasonable bound for the amount of data your application or
service should send on a circuit, be sure to set it to that value.

   **If your service or application depends upon the ability of people to make
very very large transfers (such as OnionShare, or a SecureDrop instance), you
should keep this disabled, or at best, set it to multiple gigabytes.**

   We believe that using two entry guards makes closing the circuit a
worthwhile defense for applications where it is possible to use it. If the
adversary is forced to split their side channel across multiple circuits, they
won't necessarily know which guard node each circuit traversed. This should
increase the quantity of data they must inject in order to successfully mount
this attack (and by more than just a factor of two, because of this uncertainty).

4. ***Max Circuit Age***

   Since Tor currently rotates to new TLS connections every week, if a circuit stays open longer than this period, then it will cause its old TLS connection to be held open. After a while, the circuit will be one of the few things using that TLS connection. This lack of multiplexing makes traffic analysis easier.

   For an example of an attack that makes use of this type of side channel, see [TorScan](https://eprint.iacr.org/2012/432.pdf). For additional discussion, see Tor Ticket [#22728](https://trac.torproject.org/projects/tor/ticket/22728) and [#23980](https://trac.torproject.org/projects/tor/ticket/23980).

   For this reason, if your onion service does not require long-lived circuits, it is wise to close any that hang around for long enough to approach this rotation time.

   The current default for maximum circuit age is 24 hours.

## Is this all I need to stay safe?

For additional operational security information on running an onion service,
you should have a look at the [Riseup Onion Services Best Practices
document](https://riseup.net/en/security/network-security/tor/onionservices-best-practices).

# Configuration

All of the above mechanisms can be tuned via a configuration file. Check out
this documented [example
configuration
file](https://github.com/mikeperry-tor/vanguards/blob/master/vanguards-example.conf)
for more information.

Configuration files can be specified on the command line. The default is to
read **vanguards.conf** from the current working directory. If the environment
variable **$VANGUARDS\_CONFIG** is set, the config file will be read from the
file specified in that variable.

# Installation

## Prerequisites

1. Install Tor 0.3.3.6 or above (0.3.4.4+ to make use of Bandguards).
2. Set either **ControlPort** or **ControlSocket**, and ideally also **CookieAuthentication** in your torrc. See the [Tor manpage](https://www.torproject.org/docs/tor-manual.html.en) for more information.
3. Explicitly set **DataDirectory** in your torrc.
4. Ensure Tor's DataDirectory can be read by the UNIX user or group that you intend to run this script under. (This script must directly parse the consensus).
5. Start Tor (and bring up your onion service).

## Running this script directly from git

1. [Install Stem](https://stem.torproject.org/download.html)
2. Run **./src/vanguards.py**
    * If your control port is on an alternate IP and Port, specify that with
**--control_host _IP_ --control_port _portnum_**. If you are using a control
socket, specify its full path with **--control_socket /path/to/socket**.
    * Note that **./src/vanguards.py** has several other options under **--help**.

## Using VirtualEnv

To install Stem and Vanguards into their own python virtualenv, run:

1. ./setup.sh
2. source vanguardenv/bin/activate
3. vanguards

If you do not want your environment to be in the vanguardenv subdirectory, you
can specify a different directory as an argument to setup.sh.

## PyPy and other performance tuning

For very high traffic onion services, we recommend using
[PyPy](https://pypy.org) instead of CPython. PyPy contains a JIT that should
make this script run considerably faster.

The setup.sh script above will automatically use pypy or pypy3 to create the
virtualenv if they are installed. This means that if you do **sudo apt-get
install pypy** or equivalent before running **./setup.sh**, your environment
will be using pypy when you run **vanguards** inside it. To switch to pypy
after running setup.sh, simply remove the vanguardenv directory and run
setup.sh again.

Additionally, you can disable components to reduce processing overhead. Try
disabling Rendguard first. If that is still insufficient, disable Bandguards.
Vanguards by itself should not require much overhead.

## Pip

XXX: Make pip packages

## How to use the script

### Onion service use

This script is primarily intended for onion service operators. To do so, setup
your onion service to expose a control port listener using the ControlPort
torrc directive:

```ControlPort 9099
CookieAuthentication 1
```

and then point your vanguards.py script to connect to it with --control-port=9099

### Client use

It is also possible to use the vanguards script as a regular Tor client with
Tor Browser or with Onionshare.

To use it with Tor Browser you should hack the torrc of Tor Browser so that it
exposes a control port, and then connect to it with vanguards.py. You can do it
by editing the ./Browser/TorBrowser/Data/Tor/torrc file and adding the Control
Port directive.

To use it with Onionshare, set up your Tor to expose a control port and attach
both onionshare and the vanguards.py script to it.

Note that as described above, Tor clients with the bandguards system will emit
false positives about the dropped limit being exceeded, due to Tor Browser
closing some connections before all data is read. These log messages will be at
NOTICE level for this activity as a result. See [Ticket
#25573](https://trac.torproject.org/projects/tor/ticket/25573) for more
information.

