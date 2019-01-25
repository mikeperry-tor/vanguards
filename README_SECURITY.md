# What other attacks are there against Onion Services?

In addition to the attacks that the vanguards addon mitigates (which are
documented in
[README\_TECHNICAL.md](https://github.com/mikeperry-tor/vanguards/blob/master/README_TECHNICAL.md)),
there are many other attacks on onion services. Most of these attacks are
theoretical and have not been observed in the wild, but that does not make
them impossible. The attacks that you are at risk for depends upon who is
interested in trying to deanonymize you, and what their capabilities are.

To help make this more clear, we're going to first go through the general
taxonomy of adversaries, along with their capabilities and the types of
attacks they can perform, in the [Adversaries](#adversaries) section.

In the [What can I do to be safer?](#what-can-i-do-to-be-safer) section, we'll
give some specific recommendations that will help defend against these
adversaries.

# Adversaries

Adversaries can be roughly categorized as having one or more of four
positions: [Client](#adversaries-client), [Network](#adversaries-network),
[Local](#adversaries-local), or [Global](#adversaries-global).

Adversaries can have more than one position at the same time, and each of
these positions can be either "**active**", or "**passive**". For brevity, we
do not make heavy use of the **active/passive** distinction in this document.

The adversary may also have additional outside information or suspicions that
can help them mount their attacks.

Each of the adversary subsections below starts with a list of capabilities
that the adversary has, and this list is followed by additional paragraphs
that describe the specific attacks that provide those capabilities. When
relevant, we link to our specific mitigation recommendations from each attack
description paragraph.

We classify each adversary capability using the following action verbs that
describe the scope of that capability:

 1. **Suspect** - When we say **"suspect"** with respect to a capability, that
means that the adversary can perform an attack to obtain this information, but
they will not have high certainty that they are correct. Depending on the
attack, they may end up suspecting a lot of unrelated Tor clients as a result
of their attack. These attacks may also fail to suspect the client that is
actually of interest to them.
 2. **Confirm** - When we say **"confirm"** with respect to a capability,
that means that the adversary is able to use an attack to confirm outside
information, prior suspicion, or speculation with extremely high certainty.
 3. **Determine** - When we say **"determine"** with respect to a capability, that
means that the adversary can perform an attack to obtain the described
information with extremely high certainty in a relatively short amount of
time, if the conditions for the attack are met.

Attacks that merely allow the adversary to **suspect** information are not
typically useful, unless there is also an attack that allows the adversary to
**confirm** that information.

Attacks that allow an adversary to **confirm** information are not useful
unless the adversary has some prior information or suspicion.

Attacks that **determine** information right away are thus more powerful
than attacks that **confirm** information, because they do not require any
prior information or suspicion. They are also more useful to the adversary
than attacks that allow them to **suspect** information, because they provide
a very high degree of certainty.

## Adversaries: Client

Client adversaries are those that attack your onion service using nothing more
than a Tor client and normal internet access. 

In addition to nuisances such as DoS attacks, these adversaries can
perform anonymity attacks that provide the following capabilities:

1. **Determine** if a specific onion service is exploitable, and if so, exploit it (possibly learning the IP address).
2. **Determine** if a specific onion service is also listening on a public IP address, by scanning the public internet for it.
3. **Determine** if a specific onion service always goes down at the same time as
a public Tor relay goes down.
4. **Determine** that a specific onion service is running the vanguards addon.
5. **Suspect** that a specific onion service is using [OnionBalance](https://github.com/DonnchaC/onionbalance).
6. **Suspect** that a specific onion service may be using a particular Guard.

Capabilities #1-3 should be self-explanatory.

For capability #4, the client adversary can **determine** that a specific onion
service address is running the vanguards addon by observing how that onion
service behaves. In particular, it can attempt one of the attacks that the
vanguards addon defends against, and see if the onion service closes circuits
in response. In these cases, log lines will be emitted by the vanguards addon
at NOTICE level or above. If you do not want client adversaries to be able to
easily detect this addon, you can set **close_circuits=False** in
[vanguards.conf](https://github.com/mikeperry-tor/vanguards/blob/master/vanguards-example.conf).
However, a network adversary who runs your Guard node can still **determine**
that you use this addon (see the [network adversary
section](#adversaries-network) for details).

For capability #5, the client adversary can **suspect** that a specific onion
service address is running
[OnionBalance](https://github.com/DonnchaC/onionbalance). This is because the
onion service descriptors for OnionBalance instances will often contain more
introduction points than normal, and these introduction points may even be
split across multiple distinct onion service descriptors. (The client only
**suspects** this because both of these things can happen in normal onion
service operation as well). To reduce the ability of the client adversary to
**suspect** this, set **DISTINCT_DESCRIPTORS=False** and
**MAX_INTRO_POINTS=7** in your OnionBalance configuration.

For capability #6, the client adversary may be able to **suspect** that a specific
onion service is using a particular guard by attacking that guard. If that
guard goes down or becomes slower, they may notice the effect on that onion
service. This is one of the reasons why the vanguards addon uses two guards in
a balanced way by default. Additionally, the adversary may be able to flood an
onion service with traffic to notice spikes in our public relay bandwidth
statistics at the guard.  Setting **circ_max_megabytes** in
[vanguards.conf](https://github.com/mikeperry-tor/vanguards/blob/master/vanguards-example.conf)
to an appropriate value for your service can help you detect and mitigate this
attack.

## Adversaries: Network

Network adversaries are those that run relays in the Tor network, and/or that
compromise Tor relays. They can also use the network (or a Tor client) to
inject traffic of their choice (especially against onion services).

The vanguards addon is designed to protect against network adversaries.
Setting aside the attacks that the vanguards addon defends against (which are
documented in
[README\_TECHNICAL.md](https://github.com/mikeperry-tor/vanguards/blob/reamde/README_TECHNICAL.md)),
network adversaries can still perform attacks that provide the following
capabilities:

1. **Determine** your Guard relays, if they run one of your Layer2 middle relays.
2. **Determine** that you are running an onion service that is using the vanguards
   addon, if they run one of your Guard relays.
3. **Confirm** that a specific onion service is using their Guard or Layer2 middle
   relays, if it is.
4. **Confirm** that a specific onion service is not using their Guard or Layer2
   middle relays, if it is not.

The vanguards addon is designed to make the network adversary's attacks as
difficult and unlikely as possible, and to take as long as possible, but they
can still succeed if you get unlucky. The Tor Project takes these attacks
seriously, and they are topics of [active
research](https://blog.torproject.org/tors-open-research-topics-2018-edition),
but for now, the vanguards addon is the best way we have to defend against
this adversary class.

For statistics on how long capability #1 takes, please see [our analysis of
our parameter
choices](https://github.com/asn-d6/vanguard_simulator/wiki/Optimizing-vanguard-topologies).

For capability #2, if you are using a guard relay run by the network adversary, they can
**determine** that you are running an onion service that is using the
vanguards addon through [circuit fingerprinting attacks](https://www.usenix.org/node/190967).
All of your onion service circuits (which are recognizable via the techniques
from that paper) will be made to a small set of layer2 vanguard relays. Normal
onion services (which are also recognizable at the guard relay via these same
techniques) will make circuits to the entire set of relays in the Tor network.
This discrepancy allows a malicious guard to determine that you are using the
vanguards addon.

For capability #3 and #4, the network adversary is able to perform
**confirmation** attacks to **confirm** that you are or are not using their
Guard or middle relays via the following mechanisms:

1. Inject special types of traffic at specific times towards your onion service (as was done [by CMU with RELAY_EARLY](https://blog.torproject.org/tor-security-advisory-relay-early-traffic-confirmation-attack), and [shown in the DropMark attack](https://petsymposium.org/2018/files/papers/issue2/popets-2018-0011.pdf)).
2. Inject large amounts of traffic towards your onion service, and look for these additional traffic patterns on their relays.
3. Close circuits at their relays, and observe if this causes any of their connections to your onion service to close.
4. Utilize [cryptographic tagging attacks](https://lists.torproject.org/pipermail/tor-dev/2012-March/003347.html) to mark circuits at their relays, and observe this mark at other relays (such
as the Rendezvous Point).

The vanguards addon has additional checks to detect activity related to these attacks, as well. Those details are covered in
[README\_TECHNICAL.md](https://github.com/mikeperry-tor/vanguards/blob/reamde/README_TECHNICAL.md).

## Adversaries: Local

Local adversaries include your WiFi [router
administrator](https://nakedsecurity.sophos.com/2018/04/18/russias-grizzly-steppe-gunning-for-vulnerable-routers/), ISP, hosting provider, or VPN, as well as the ISP or hosting provider of
the Tor relays you use to connect to the Tor network, and any other ISPs and
[routers](https://spectrum.ieee.org/tech-talk/computing/hardware/us-suspicions-of-chinas-huawei-based-partly-on-nsas-own-spy-tricks) along your path to the Tor network.

The local adversary has less surveillance resolution than the network
adversary, because Tor's TLS encryption prevents it from knowing  which of
your packets belong to which Tor circuit. This means that the local adversary
cannot perform most of the fingerprinting and related attacks that the network
adversary can perform.

However, local adversaries still have the following capabilities:

1. **Determine** that you are using the public Tor network.
2. **Suspect** that your Tor client might be running an unknown onion service.
3. **Suspect** that your Tor client might be running the vanguards addon (soon to be
   fixed).
4. **Confirm** that you are running a specific onion service address, if you are
   running a specific service that is of interest to them.

For capability #1, local adversaries can **determine** that you are running Tor
because the list of Tor relays is public, and connections to them are obvious.
[Using a bridge with your onion service](#the-best-way-to-use-bridges) can
help mitigate this attack.

For capability #2, local adversaries might **suspect** that your Tor client could
be an unknown onion service because it exhibits traffic patterns that are
unlike most other Tor clients. Your connections will stay open all of the
time, and you will regularly transmit data while other nearby humans are
asleep, as well as while they are awake. Your traffic will also be
asymmetrical. While most Tor clients download, you will likely be doing a lot
of uploading. [Using or running a bridge or Tor
relay](#Use-Bridges-or-Run-a-Relay-or-Bridge) with your
Onion Service can help conceal these traffic patterns, especially when [used
in combination with OnionBalance](#using-onionbalance).

For capability #3, local adversaries might also **suspect** that you could be
using the vanguards addon, at least until [Proposal
291](https://gitweb.torproject.org/torspec.git/tree/proposals/291-two-guard-nodes.txt)
is turned on. This is because you will be using two Guards in a balanced way,
as opposed to using a second Guard only sometimes (as normal clients do
today). Proposal 291 is a consensus parameter change. The rest of the Tor
Project has to agree that this is a good idea, and the change will be
immediate. I am convinced that worse attacks are possible without this
consensus parameter change, but discussion and deliberation of all possible
attacks and all possible future alternatives can take a while. Sometimes
years. In the meantime, I am still convinced it is safer for onion services to
use two guards in a balanced way, even if they stand out for doing so.

With capability #2 and #3, the local adversary may **suspect** that you could be
running an onion service, and maybe even one that wants high security, but
they will not know which onion service it is.

For capability #4, if the adversary is interested in deanonymizing a small set of
specific onion service addresses, they can attempt to **confirm** that you are
running one of these specific services on their local network via a few
different attack vectors:

1. Block your connection to Tor (or disable your internet connection) to see if any onion services they care about go down.
2. Send lots of traffic to the onion service to see if you get more traffic on your internet connection.
3. Kill your TCP connections to see if any of their connections to that onion service close.
4. If you weren't using vanguards, they can confirm an onion service even
   easier (see [Proposal 291](https://gitweb.torproject.org/torspec.git/tree/proposals/291-two-guard-nodes.txt) for details).

The first two vectors of this **confirmation** attack can be mitigated by
[using OnionBalance](#using-onionbalance), and by setting
**circ_max_megabytes** in your
[vanguards.conf](https://github.com/mikeperry-tor/vanguards/blob/master/vanguards-example.conf)
to an appropriate value for your service.

Unfortunately, the third vector is not possible to fully mitigate until Tor
supports datagram transports and [conflux-style session
resumption](https://www.cypherpunks.ca/~iang/pubs/conflux-pets.pdf).

However, [monitoring your service closely](#monitor-your-service) for
connectivity loss can help you detect attempts by the adversary to **confirm**
your service location. The vanguards addon will emit NOTICE and WARN messages
related to connectivity loss, and your service will become unreachable.

## Adversaries: Global

A global adversary is an adversary that can observe large portions of the
internet. [The Five Eyes](https://en.wikipedia.org/wiki/Five_Eyes) and its
extended versions are the canonical example of this adversary. However,
adversaries that can compromise a large number of internet routers (such as
[Russia](https://nakedsecurity.sophos.com/2018/04/18/russias-grizzly-steppe-gunning-for-vulnerable-routers/)
or
[China](https://spectrum.ieee.org/tech-talk/computing/hardware/us-suspicions-of-chinas-huawei-based-partly-on-nsas-own-spy-tricks))
are also in this class.

The global adversary can perform most of the attacks that the local adversary
can, but everywhere. (It may be significantly more expensive for the global
adversary to perform **active** attacks than it is for the local adversary to
do so, but for the most part this degrades their capability only slightly).

The global adversary has the following capabilities:

1. **Determine** a list of most/all IPs that connect to the public Tor network.
2. **Suspect** which of these IPs might be running onion services.
3. **Suspect** which of these IPs might be using the vanguards addon (soon to be fixed).
4. **Suspect** that an IP might be running a specific onion service address, if it is
   running a specific service that is of interest to them.

The mitigations for these are the same as they are for the local adversary.

This same adversary can theoretically perform additional attacks to attempt to
deanonymize all Tor traffic all of the time, but [there are
limits](http://archives.seul.org/or/dev/Sep-2008/msg00016.html) to how well
those attacks scale. These limits are also the reason that the global
confirmation attack has been degraded to "**suspect**" for #4.

For capability #4, the global adversary becomes more certain in their
suspicion if they are able to induce the onion service to transmit
significantly more traffic than its baseline for a long period of time. Again,
the mitigations for this are to use [OnionBalance](#using-onionbalance), use
or run
[a bridge](#Use-Bridges-or-Run-a-relay-or-Bridge) with your
onion service, and/or set **circ_max_megabytes** in your
[vanguards.conf](https://github.com/mikeperry-tor/vanguards/blob/master/vanguards-example.conf)
to an appropriate value for your service.


# What can I do to be safer?

Quite a few things. Using the vanguards addon is a good start, but it is not
the whole picture.

There are four classes of things you can do to improve your position against
various attacks:

1. [Have Good Opsec](#have-good-opsec)
2. [Use Bridges or Run a Relay or Bridge](#use-bridges-or-run-a-relay-or-bridge)
3. [Configure OnionBalance Correctly](#using-onionbalance)
4. [Monitor Your Service](#monitor-your-service)

## Have Good Opsec

Before worrying about any of these advanced attacks on the Tor network, you
should make sure that your onion service is not leaking basic info via the
application layer, or by allowing connections outside of Tor.

For information about how to do this, you should have a look at the [Riseup Onion Services Best Practices document](https://riseup.net/en/security/network-security/tor/onionservices-best-practices).

## Use Bridges or Run a Relay or Bridge

Tor has only basic defenses against traffic analysis at the moment. We are
working on more, but in the meantime, using a bridge or running a relay or
bridge can provide some additional protection against traffic analysis
performed by local and global adversaries.

Bridges can help conceal the fact that you are connecting to the Tor network.
If you use a bridge address that is not known to the adversary, both the local
and global adversaries will have a harder time performing their attacks.

Running a relay or bridge with your service can help the traffic patterns of
your service blend in with the rest of the Tor network, but this is tricky to
set up correctly, and you must take additional steps to decorrelate your
service uptime from your relay uptime.

### The Best Way To Use Bridges

Right now, the best bridge protocol to use is obfs4, because it has additional
traffic analysis obfuscation techniques that make it harder for the local and
global adversaries to use bandwidth side channels and other traffic
characteristics.

To use obfs4, obtain two bridges from
[bridges.torproject.org](https://bridges.torproject.org/bridges?transport=obfs4)
and add them to your torrc like so:

```
UseBridges 1
Bridge obfs4 85.17.30.79:443 FC259A04A328A07FED1413E9FC6526530D9FD87A cert=RutxZlu8BtyP+y0NX7bAVD41+J/qXNhHUrKjFkRSdiBAhIHIQLhKQ2HxESAKZprn/lR3KA iat-mode=2 
Bridge obfs4 38.229.1.78:80 C8CBDB2464FC9804A69531437BCF2BE31FDD2EE4 cert=Hmyfd2ev46gGY7NoVxA9ngrPF2zCZtzskRTzoWXbxNkzeVnGFPWmrTtILRyqCTjHR+s9dg iat-mode=2 

ClientTransportPlugin obfs2,obfs3,obfs4,scramblesuit exec /usr/bin/obfs4proxy
```

Note the use of the iat-mode=2 parameter. Setting iat-mode=2 (as opposed to
iat-mode=0 or 1) causes obfs4 to inject traffic timing changes into your
outgoing traffic, which is exactly the direction you want as a service. The
bridge itself does not need to have the same setting.

You can get that obfs4proxy binary as a debian package, or from a recent Tor
Browser version, or [build it from source](https://gitweb.torproject.org/pluggable-transports/obfs4.git/).

### The Best Way to Run Tor Relays Or Bridges With Your Service

Instead of using bridges, another alternative is to use the Tor network itself
as cover traffic for your service by running a relay or bridge. If your relay
or bridge is used enough (especially by other onion service client and service
traffic), this will help obscure your service's traffic.

The seemingly obvious approach would be to use the same Tor process for your
relay as you use for your onion service. This will accomplish the traffic
blending on the same TLS connections as relayed Tor traffic. Unfortunately,
because Tor is single threaded, your onion service activity can still cause
stalls in the overall network activity of your relay. See
[Ticket #16585](https://trac.torproject.org/projects/tor/ticket/16585) for the gory
details. Worse still, if it is the same process, your Tor relay will report
your onion service history in its read/write statistics, which result in a
[noticeable asymmetry in these
statistcis](https://trac.torproject.org/projects/tor/ticket/8742).

However, if you run your Tor relay as a separate process on the same machine
as your onion service Tor process, but **also** use that relay locally as a
bridge, your onion service activity will not directly block the relay
activity, but will still share all of its outbound TLS connections to other
relays. For this, you would add something like the following to your onion
service torrc:

```
UseBridges 1
Bridge 127.0.0.1:9001                # 9001 is the relay process's OR port.
```

The story deepens, however. When you do this, **your onion service uptime will
be strongly correlated to your relay uptime, and both are now very
easily observable by client adversaries**.

[OnionBalance](#using-onionbalance) is one way to address this (ie: running
several Tor relays on different machines, each with their own OnionBalance
Backend Instance).

To look as much like a normal onion service as possible, you should use two
Tor relays, and each on different machines in different data centers. In this
way, your traffic will appear as an onion service that is using your two
guards, and your onion service as a whole won't go down unless both of your
relays are down.

## Using OnionBalance

[OnionBalance](https://onionbalance.readthedocs.io/en/latest/getting-started.html#architecture)
can help protect against some forms of traffic analysis and confirmation
attacks. It does this at the expense of more exposure to a larger number of
local adversaries, though, and if the adversary can tell that you are using
OnionBalance, they can counteract many of the benefits.

Despite exposing you to more local adversaries, OnionBalance helps protect
against local adversaries because they will no longer be able to observe all
of your onion service traffic, and it is more difficult for them to impact
your reachability for a reachability confirmation attack.

Additionally, when OnionBalance is used in combination with the addon's
bandguards component option **circ_max_megabytes**, this can help protect
against bandwidth confirmation attacks that send high volumes of traffic to
interesting onion services and watch for any evidence of results on a local
internet connection.

However, OnionBalance needs some tweaks to avoid giving an advantage to the
network adversary. Because multiple instances of the vanguards addon do not
communicate through OnionBalance, each additional instance of the vanguards
addon will choose different layer2 and layer3 guards. These additional layer2
and layer3 guards increase the overall exposure to guard discovery attacks. In
cases where it is just as bad for the adversary to discover any of your onion
service instances as it is to discover all of them, then obviously each
additional instance lowers your security a bit.

### How to OnionBalance

To attempt to conceal the fact that you are using OnionBalance, you want your
OnionBalance service to produce descriptors with similar numbers of
introduction points as normal services. Normal services typically have between
3 and 7 introduction points. This means you should set the OnionBalance
setting **MAX_INTRO_POINTS=7**, and also set **DISTINCT_DESCRIPTORS=False**,
to prevent it from generating multiple descriptors.

To keep your layer2 and layer3 vanguards in sync between your OnionBalance
Management Server and the backend instances, first run vanguards on your
Management Server.

Then, once per hour, copy the **vanguards.state** file from your OnionBalance
Management Server to each of your Backend Instances, via tor+scp or some other
secure mechanism. (The UNIX crontab program is a good way to do this copy
hourly).

When each Backend Instance gets this copied statefile (let's call it
**mgmt-vanguards.state**), it should run
```
  ./src/vanguards.py --one_shot_vanguards --state mgmt-vanguards.state
```

This will cause the Backend Instance to update its tor settings with the same
layer2 and layer3 guard information as on the management side. It does not
matter if your Backend Instances cannot write to their torrc files. The
settings will still be updated.

Then, to benefit from the other defenses, each Backend Instance should run a
separate vanguards process with a different state file, but with vanguards
itself disabled. This is done with something like:
```
  ./src/vanguards.py --disable_vanguards --state backend-vanguards.state
```

These backend instances will then still monitor and react to bandwidth side
channel attacks and Rendezvous Point overuse, while still using the same
layer2 and layer3 guards as your Management Server.

## Monitor Your Service

As we discussed above, confirmation attacks can be performed by local and
global adversaries that block your access to Tor (or kill your Tor
connections) to **confirm** if this impacts the reachability of a suspect hidden
service or not. This is a good reason to monitor your onion service reachability very
closely with monitoring software like [Nagios](https://www.nagios.org/) or
[Munin](http://munin-monitoring.org/).

If you use OnionBalance, you need to monitor the ability of each of your
Backend Instances to connect to Tor and receive connections to their unique
backend onion service addresses. If the adversary **suspects** that you are
using OnionBalance, they can perform reachability confirmation attacks against
the specific backend instances, so monitoring their uptime is a wise move.

If you use bridges or run relays, you should monitor their uptime as well, and
replace them immediately if they go down.

The vanguards addon also emits WARN messages when it detects that you have lost
connectivity to the Tor network, or when you still have connectivity to the Tor
network, but you are unable to build circuits. It also emits NOTICE messages
if any connections were forcibly closed while they had active circuits on them.

You should add the output of the vanguards addon to your monitoring
infrastructure for this reason (in addition to watching for evidence of
the other attacks the addon detects).
