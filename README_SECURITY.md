# Are there other attacks against Onion Services?

Yes. Many.

The attacks that you are at risk for depend on who your adversary is.

To help make this more clear, we're going to first go through the general
taxonomy of adversaries along with the types of attacks they can perform in
the [Adversaries](#adversaries) section.

In the [What can I do to be safer?](#what-can-i-do-to-be-safer) section, we'll
give some specific recommendations that will help defend against these
adversaries.

# Adversaries

Adversaries can be roughly categorized as having one or more of three
positions: "Network", "Local", or "Global".

Adversaries can have more than one position at the same time, and each of
these positions can be either "active", or "passive". They may also have
additional information that can help them mount their attacks.

## Adversaries: Network

Network adversaries are those that run relays in the Tor network, and/or that
compromise Tor relays. They can also use the network to inject traffic of
their choice (especially against onion services).

The vanguards addon is designed to protect against network adversaries.
Setting aside the attacks that this addon defends against (which are
documented in
[README\_TECHNICAL.md](https://github.com/mikeperry-tor/vanguards/blob/reamde/README_TECHNICAL.md)),
network adversaries can still perform the following attacks:

1. Determine your Guard relays, if they run one of your Layer2 middles.
2. Determine that you are running an onion service that is using this
   addon, if they run one of your Guard relays.
3. Determine that a specific onion service is running this addon.
4. Guess that your onion service may be using a particular Guard.
5. Confirm that a specific onion service is using their Guard or Layer2 middle
   relays, if it is.
6. Confirm that a specific onion service is not using their Guard or Layer2
   middle relays, if it is not.

The vanguards addon is designed to make these attacks as difficult and unlikely as
possible, and to take as long as possible, but they can still succeed if you
get unlucky. Tor takes these attacks seriously, and they are topics of [active
research](https://blog.torproject.org/tors-open-research-topics-2018-edition),
but for now, this addon is the best way we have to defend against this
adversary class.

For statistics on how long the first attack takes, please see [our analysis of our parameter choices](https://github.com/asn-d6/vanguard_simulator/wiki/Optimizing-vanguard-topologies).

If you are using a guard relay run by the network adversary, they can
determine that you are running an onion service that is using this addon
through [circuit fingerprinting attacks](https://www.usenix.org/node/190967).
All of your onion service circuits (which are recognizable via the techniques
from that paper) will be made to a small set of layer2 guard relays. Normal
onion services (which are also recognizable at the guard relay via these same
techniques) will make circuits to the entire set of relays in the Tor network.
This discrepancy allows a malicious guard to determine that you are using this
addon.

The network adversary can determine that a specific onion service (yours or
not) is running this addon by observing how that onion service behaves. In
particular, it can attempt one of the attacks that this addon defends against,
and see if the onion service closes circuits in response. In these cases, log
lines will be emitted by this addon at NOTICE level or above.

The network adversary may be able to guess that you are using a particular
guard by attacking that guard. If that guard goes down or becomes slower, they
may notice the effect on your onion service. This is one of the reasons why
the vanguards addon uses two guards in a balanced way by default.
Additionally, they may be able to flood your onion service with data to notice
spikes in our relay bandwidth statistics at the guard. Setting
**circ_max_megabytes** to an appropriate value for your service can help you
detect and mitigate this.

The network adversary is able to perform confirmation attacks to confirm that
you are or are not using their Guard or middles via the following mechanisms:

1. Inject special types of traffic at specific times towards your onion service (as was done [by CMU with RELAY_EARLY](https://blog.torproject.org/tor-security-advisory-relay-early-traffic-confirmation-attack), and [shown in the DropMark attack](https://petsymposium.org/2018/files/papers/issue2/popets-2018-0011.pdf)).
2. Inject large amounts of traffic towards your onion service, and look for these additional traffic patterns on their relays.
3. Close circuits at their relays, and observe if this causes any of their connections to your onion service to close.
4. Utilize [cryptographic tagging attacks](https://lists.torproject.org/pipermail/tor-dev/2012-March/003347.html) to mark circuits at their relays, and observe this mark at other relays (such
as the Rendezvous Point).

The vanguards addon has additional checks to detect activity related to these attacks, as well. Those details are covered in
[README\_TECHNICAL.md](https://github.com/mikeperry-tor/vanguards/blob/reamde/README_TECHNICAL.md).

## Adversaries: Local

Local adversaries include your WiFi router administrator, your ISP, hosting
provider, or VPN, as well as the ISP or hosting provider of the entry relays
you use to connect to the Tor network, and any other ISPs and routers along
your path to the Tor network.

The local adversary has less surveillance resolution than the network
adversary, because it cannot tell which of your packets belong to which Tor
circuit. This means that it cannot perform most of the fingerprinting and
related attacks that are possible from a guard relay.

However, local adversaries can do the following things:

1. Determine that you are using the public Tor network.
2. Guess that your Tor client might be running an unknown onion service.
3. Guess that your Tor client might be running the vanguards addon (soon to be
   fixed).
4. Confirm that you are running a specific onion service address, if you are
   running a specific service that is of interest to them.

Local adversaries can determine that you are running Tor because the list of
relays is public, and connections to them are obvious. (Unless you use bridges,
of course, which is one of our later recommendations).

Local adversaries can guess that your Tor client might be an unknown onion
service because it exhibits traffic patterns that are unlike most other Tor
clients. Your connections will stay open all of the time, and you will
regularly transmit data while other nearby humans are asleep, as well as while
they are awake. Your traffic will also be asymmetrical. While most Tor clients
download, you will likely be doing a lot of uploading.

Local adversaries can also guess that you might be using the vanguards addon,
at least until [Proposal
291](https://gitweb.torproject.org/torspec.git/tree/proposals/291-two-guard-nodes.txt)
is turned on. This is because you will be using two Guards in a balanced way,
as opposed to using a second Guard only sometimes (as normal clients do
today). Proposal 291 is a consensus parameter change. The rest of the Tor
Project just has to agree that it is a good idea. Agreement can take a while,
but once we decide, the change will be immediate.

With this information, the local adversary may suspect that you are running
an onion service, and maybe even one that wants high security, but they will
not know which one it is. If they are interested in specific onion services,
they can attempt to confirm that you are running one of them via a few
different mechanisms:

1. Block your connection to Tor to see if any onion services they care about go down.
2. Kill your TCP connections to see if any of their connections to that onion service close.
3. Send lots of traffic to the onion service to see if you get more traffic on your internet connection.
4. If you weren't using vanguards, they can confirm an onion service even
   easier (see [Proposal 291](https://gitweb.torproject.org/torspec.git/tree/proposals/291-two-guard-nodes.txt) for details).

## Adversaries: Global

A global adversary is an adversary that can observe large portions of the
internet. [The Five Eyes](https://en.wikipedia.org/wiki/Five_Eyes) and its
extended versions are the canonical example of this adversary. However, any
adversary that can compromise a large number of internet routers (such as
Russia or China) is also in this class.

The global adversary can perform all of the attacks that the local adversary
can, but everywhere. This means that they can:

1. Get a list of most/all IPs that connect to the public Tor network.
2. Guess which of these IPs might be running onion services.
3. Guess which of these IPs might be using this addon (soon to be fixed).
4. Guess that an IP might be running a specific onion service address, if it is
   running a specific service that is of interest to them.

This same adversary can theoretically perform additional attacks to attempt to
deanonymize all Tor traffic all of the time, but [there are
limits](http://archives.seul.org/or/dev/Sep-2008/msg00016.html) to how well
those attacks scale. These limits are also the reason that the global
confirmation attack has been degraded to a "guess" for #4. If there is enough
other traffic present, or other mitigating factors, they may not always be
certain, unless they send a large amount of traffic over a long period of
time, or become active on a global scale in terms of blocking or closing
very many connections (which is very expensive, noisy, and noticeable).

# What can I do to be safer?

Quite a few things. Using the vanguards addon is a good start, but it is not
the whole picture.

## Have Good Opsec

Before worrying about any of these advanced attacks on the Tor network, you
should make sure that your onion service is not leaking basic info via the
application layer, or by allowing connections outside of Tor.

For information about how to do this, you should have a look at the [Riseup Onion Services Best Practices document](https://riseup.net/en/security/network-security/tor/onionservices-best-practices).

## Consider Using Bridges

Bridges can help conceal the fact that you are connecting to the Tor network.
If you use a bridge address that is not known to the adversary, both the local
and global adversaries will have a harder time performing their attacks.

### The Best Way To Use Bridges

Right now, the best bridge protocol to use is obfs4, because it has additional
traffic analysis obfuscation techniques that make it harder for the local and
global adversaries to use bandwidth side channels and other traffic
characteristics.

[Snowflake](https://trac.torproject.org/projects/tor/wiki/doc/Snowflake) is a
close second, because its connections cannot be closed by simple TCP reset
attacks. This makes confirmation attacks more expensive. However, snowflake is
not in wide deployment at the moment. Snowflake also does not offer the
traffic analysis obfuscation protections that obfs4 does.

To use obfs4, obtain two bridges from
[bridges.torproject.org](https://bridges.torproject.org/bridges?transport=obfs4)
and add them to your torrc like so:

```
UseBridges 1
Bridge obfs4 85.17.30.79:443 FC259A04A328A07FED1413E9FC6526530D9FD87A cert=RutxZlu8BtyP+y0NX7bAVD41+J/qXNhHUrKjFkRSdiBAhIHIQLhKQ2HxESAKZprn/lR3KA iat-mode=2 
Bridge obfs4 38.229.1.78:80 C8CBDB2464FC9804A69531437BCF2BE31FDD2EE4 cert=Hmyfd2ev46gGY7NoVxA9ngrPF2zCZtzskRTzoWXbxNkzeVnGFPWmrTtILRyqCTjHR+s9dg iat-mode=2 

ClientTransportPlugin obfs2,obfs3,obfs4,scramblesuit exec /usr/bin/obfs4proxy
```

Note the use of the iat-mode=2 parameter. Setting this (as opposed to
iat-mode=0 or 1) causes obfs4 to inject traffic timing changes into your
outgoing traffic, which is exactly the direction you want as a service. The
bridge itself does not need to have the same setting.

You can get that obfs4proxy binary as a debian package, or from a recent Tor
Browser version, or [build it from source](https://gitweb.torproject.org/pluggable-transports/obfs4.git/).

## If You OnionBalance, OnionBalance Carefully

If you use it correctly,
[OnionBalance](https://onionbalance.readthedocs.io/en/latest/getting-started.html#architecture)
can help protect against some forms of traffic analysis and confirmation
attacks. It does this at the expense of more exposure to a larger number of
local adversaries, though, and if the adversary can tell that you are using
OnionBalance, they can counteract many of the benefits.

Despite exposing you to more local adversaries, OnionBalance helps protect
against local adversaries because they will no longer be able to observe all
of your onion service traffic, and it is more difficult for them to impact
your reachability for a reachability confirmation attack. Additionally, when
OnionBalance is used in combination with the addon's bandguards component
option **circ_max_megabytes**, this can help protect against bandwidth
confirmation attacks that send high volumes of traffic to interesting onion
services and watch for any evidence of results on a local internet connection.

OnionBalance helps protect against a global adversary for similar reasons. If
your OnionService is very popular, instead of all of the traffic exiting the
Tor network on one or two very loud connections to a single IP address, it will
be spread across multiple Backend Instances.

However, OnionBalance needs some tweaks to avoid giving an advantage to the
network adversary. Because multiple instances of this addon do not communicate
through OnionBalance, each additional instance of this addon will choose
different layer2 and layer3 guards. These additional layer2 and layer3 guards
increase the overall exposure to guard discovery attacks. In cases where it is
just as bad for the adversary to discover any of your onion service instances
as it is to discover all of them, then obviously each additional instance
lowers your security a bit.

### How to OnionBalance

To attempt to conceal the fact that you are using OnionBalance, you want your
OnionBalance service to produce descriptors with similar numbers of
introduction points as normal services. Normal services typically have between
3 and 7 introduction points. This means you should set the
**MAX_INTRO_POINTS** OnionBalance setting to 7, and also set
**DISTINCT_DESCRIPTORS=False**, to prevent it from generating multiple
descriptors.

To keep your layer2 and layer3 vanguards in sync, copy the vanguards state
file from your OnionBalance Management Server to each of your Backend
Instances, via tor+scp or some other secure mechanism. This should be done
once per hour (crontab is a good way to do this).

When they get this statefile (let's call it **mgmt-vanguards.state**), each of
your Backend Instances should run
```
  ./src/vanguards.py --one_shot_vanguards --state mgmt-vanguards.state
```

This will cause the Backend Instance to update its tor settings with the same
layer2 and layer3 guard information as on the management side. It does not matter if your
Backend Instances cannot write to their torrc files. The settings will still
be updated.

Then, to benefit from the other defenses, each Backend Instance should run a
separate vanguards process with a different state file, but with vanguards
itself disabled. This is done with something like:
```
  ./src/vanguards.py --disable_vanguards --state backend-vanguards.state
```

These backend instances will then still monitor and react to bandwidth side
channel attacks and Rendezvous Point overuse, without changing your layer2 or
layer3 guards.

## Monitor Your Service

As we discussed above, confirmation attacks can be performed by local and
global adversaries that block your access to Tor (or kill your Tor
connections) to determine if this impacts the reachability of a suspect hidden
service. This is a good reason to monitor your onion service reachability very
closely with something like [Nagios](https://www.nagios.org/),
[Munin](http://munin-monitoring.org/) or other reliability monitoring
software.

If you use OnionBalance, you need to monitor the ability of each of your
Backend Instances to connect to Tor and receive connections to their unique
backend onion service keys. If the adversary is able to determine that you are
using OnionBalance, they can perform reachability confirmation attacks against
the specific backend instances.

If you use bridges, you should monitor their uptime as well, and replace them
if they go down.

The vanguards addon also emits warnings when it detects that you have lost
connectivity to the Tor network, or when you still have connectivity to the Tor
network, but you are unable to build circuits. You should add the output
of the vanguards addon to your monitoring infrastructure for this reason (in
addition to watching for any evidence of attack).

## Consider Running Tor Relays Or Bridges (BUT DO IT RIGHT!)

All of the attacks performed by local and global adversaries, as well as some
of the confirmation attacks performed by network adversaries, are much harder if
there is additional traffic for your onion service to blend in with.

One way to accomplish this is to run a Tor relay or Tor Bridge with your onion
service. If the relay or bridge is used enough (especially by other onion
service client and service traffic), this will help obscure your service's
traffic.

For this to work, you have to be careful about how you set it up. Simply
running an additional Tor daemon on the same machine is not enough -- your
onion service will make separate (and distinguishable) TLS connections to other
relays, and thus you will get no benefit from the additional traffic against
an adversary that understands how Tor works.

The seemingly obvious approach would be to use the same Tor process for your
relay as you use for your onion service. This will accomplish the traffic
blending on the same TLS connections. Unfortunately, because Tor is single
threaded, your onion service activity can still cause stalls in the overall
network activity of your relay. See [Ticket #16585](https://trac.torproject.org/projects/tor/ticket/16585) for the gory details. Worse still, if it is the same process, your Tor relay will report
your onion service history in its read/write statistics, which result in a
[noticeable asymmetry in these statistcis](https://trac.torproject.org/projects/tor/ticket/8742).


### The Best Way to Run a Relay or Bridge with Your Service

The way through this minefield is to run your Tor relay as a separate process
on the same machine as your onion service Tor process, but **also** use that
relay locally as a bridge. In this way, your onion service activity will not
directly block the relay activity, but will still share all of its outbound
TLS connections to other relays. For this, you would add something like the
following to your onion service torrc:

```
UseBridges 1
Bridge 127.0.0.1:9001                # 9001 is the relay process's OR port.
```

The story deepens, however. When you do this, **your onion service uptime will
be strongly correlated to your relay uptime, and both are now very
easily observable by adversaries that aren't local, global, or even
in-network**.

OnionBalance is one way to address this (ie: running several Tor
relays on different machines, each with their own OnionBalance Backend
Instance), but again, if the adversary is able to determine that you are using
OnionBalance, they can try to determine if your individual Backend Instances
go up and down in correlation with any Tor relays over time. It is likely
harder for them to do this accurately than with a single relay and a single
service, but it may still be possible.

To look as much like a normal onion service as possible, you should use two
OnionBalance Backend Instances, one for each relay, and each on different
machines in different data centers. In this way, your traffic will appear as an
onion service that is using your two guards, and your onion service as a whole
won't go down unless both of your relays are down.

Again, this whole setup should be vigilantly monitored for any downtime of any
components, as any extended downtime will leak information.
