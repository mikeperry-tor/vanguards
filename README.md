# Vanguards (and other guard discovery mitigations)

This project is a prototype of [Tor proposal 247](https://gitweb.torproject.org/torspec.git/tree/proposals/247-hs-guard-discovery.txt).

We created this to enable us to rapidly test different parameters of that
proposal for performance. We also hope that it will be useful for people who
run onion services that require high security.

Where possible, we will also use it to implement prototypes of additional
client-side defenses, mitigations, and detection mechanisms for other forms of
guard discovery attack.

## What are guard discovery attacks?

In brief, guard discovery attacks enable an adversary to determine the guard
node(s) that are in use by a Tor client and/or Tor onion service.

The most basic form of this attack is to make many connections to a Tor onion
service, forcing it to create circuits until one of the adversary's nodes is
chosen for the middle hop next to the guard. At that point, a side channel is
used to confirm that the node is in fact next to the actual onion service,
leading to discovery of that onion service's guard node.

There are other vectors of attack, too. For more information (including the
Tor Project's mitigation plans), see [the SponsorV
page](https://trac.torproject.org/projects/tor/wiki/org/sponsors/SponsorV) as
well as [the guard discovery
tag](https://trac.torproject.org/projects/tor/query?keywords=~guard-discovery)
on our bug tracker.

## What does this script do?

This script uses the [Stem Tor control port
library](https://stem.torproject.org/) to connect to a Tor client running on
port 9051 (or on an alternate user-specified port or file system socket). It
then uses the [Tor control
protocol](https://gitweb.torproject.org/torspec.git/tree/control-spec.txt) to
select nodes from the Tor consensus for use with the torrc options \_HSLayer2Nodes
and \_HSLayer3Nodes.

Each of these options is assigned its own set of nodes, which are rotated
based on the randomized selection algorithm specified in [Tor proposal
247](https://gitweb.torproject.org/torspec.git/tree/proposals/247-hs-guard-discovery.txt).
The number of nodes in each of these sets, as well as the ranges on rotation
times for each set, can be specified as command line parameters.

This script and associated torrc options apply to both service-side and
client-side onion service activity, but **NOT** to any client traffic that
exits the Tor network to the normal Internet.

## Is this all I need to stay safe?

First, this script is a prototype. Second, while this prototype is functional,
it is incomplete. Right now it is use at your own risk. Watch out for falling
bits and git commits.

In particular, the following things still need to be done:
 * Optimal values for the number of Layer2 and Layer3 nodes, as well as
   their rotation time ranges, still need to be determined. These values
   will be chosen based on the results of security and performance simulations.
 * Improved usability, better install options, test coverage, release
   versioning, etc.

You should also have a look at the [Riseup Onion Services Best Practices
document](https://riseup.net/en/security/network-security/tor/onionservices-best-practices).

## How do I use it?

1. Install Tor 0.3.3.1-alpha or newer.
    * Set either **ControlPort** or **ControlSocket**, and ideally also
**CookieAuthentication** in your torrc. See the [Tor manpage](https://www.torproject.org/docs/tor-manual.html.en) for more information.
2. [Install Stem](https://stem.torproject.org/download.html)
3. Start Tor (and bring up your hidden service).
4. Run **./src/vanguards.py**
    * If your control port is on an alternate IP and Port, specify that with
**--control_host _IP_ --control_port _portnum_**. If you are using a control
socket, specify its full path with **--control_socket /path/to/socket**.
    * Note that **./src/vanguards.py** has several other options under **--help**. These are for performance experiments only and are not recommended for normal use.

