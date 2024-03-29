# What does this addon do?

This addon uses the [Stem Tor control port
library](https://stem.torproject.org/) to connect to a Tor control port
listening on port 9051 (or on an alternate user-specified port, or UNIX file
system socket).

This addon protects against guard discovery and related traffic analysis
attacks. A guard discovery attack enables an adversary to determine the guard
node(s) that are in use by a Tor client and/or Tor onion service. Once the
guard node is known, traffic analysis attacks that can deanonymize an onion
service (or onion service user) become easier.

# Onion Service Overview

To understand these attacks as well as the rest of this document, first let's
give a quick overview of how onion services work in Tor.

Onion service addresses are announced in encrypted descriptor documents which
are uploaded to specially selected Tor relays, called HSDIRs. These
descriptors list three Introduction Points, which are another set of relays
that are used to make connection requests to a specific onion service.

Services create and hold open Introduction Circuits to their chosen
Introduction Point relays, to accept connection requests from clients. These
client connection requests specify a client-chosen relay called the Rendezvous
Point, which the client has made a circuit to, to accept connection back from
the service. When a service receives a request through their Introduction
circuit, that service makes a separate Rendezvous circuit to connect to that
client's chosen Rendezvous Point. Then, actual onion service application data
flows over this Rendezvous circuit, as a Tor Stream.


![Onion Service Connections](https://people.torproject.org/~mikeperry/images/onion-service-explainer.jpg)


# Onion Service Guard Discovery Attacks

The most basic form of the Guard discovery attack is to make many connections
to a Tor onion service, in order to force it to create circuits until one of
the adversary's relay is chosen for the middle hop next to the guard. That is
possible because middle hops for rendezvous circuits are picked from the set
of all relays:

![Current Onion Service Paths](https://raw.githubusercontent.com/asn-d6/vanguard_simulator/illustrations/illustrations/current_system.jpg)

This attack can also be performed against clients, by inducing them to create
lots of connections to different onion services, by for example, injecting
lots of onion-hosted images/elements into a page.

A traffic analysis side channel can be used to confirm that the malicious node
is in fact part of the rendezvous circuit, leading to the discovery of that
onion service's or client's guard node. From that point, the guard node can be
compromised, coerced, or surveilled to determine the actual IP address of the
onion service or client.

# Vanguards Addon Defenses

To defend against these attacks, this addon has three defense subsystems:
Vanguards, Rendguard, and Bandguards.

All three subsystems apply to both service-side and client-side onion service
activity. The Bandguards subsystem also applies to client traffic that exits the
Tor network to the normal Internet.

## The Vanguards Subsystem

The Vanguards subsystem uses the [Tor control
protocol](https://gitweb.torproject.org/torspec.git/tree/control-spec.txt) to
select nodes from the Tor consensus for use with the torrc options HSLayer2Nodes
and HSLayer3Nodes.

Each of these options is assigned its own set of nodes, which are rotated
based on the randomized selection algorithm specified in [the Mesh Vanguards
Proposal](https://gitweb.torproject.org/torspec.git/tree/proposals/292-mesh-vanguards.txt).

These options ensure that all onion service circuits are restricted to a set
of second and third layer guards, instead of sampling random ones from the
whole network every time.

The change to fixed nodes for the second and third layer guards is designed
to force the adversary to have to run many more nodes, and to execute both an
active sybil attack, as well as a node compromise attack. In particular, the
addition of second layer guard nodes means that the adversary goes from being
able to discover your guard in minutes by running just one middle node, to
requiring them to sustain the attack for weeks or even months, even if they
run 5% of the network.

The analysis behind our choice for the number of guards at each layer, and for
rotation duration parameters is [available on
GitHub](https://github.com/asn-d6/vanguard_simulator/wiki/Optimizing-vanguard-topologies).
Here is how our current vanguard 2-3-8 topology looks like:

![Vanguard Layer Topology](https://raw.githubusercontent.com/asn-d6/vanguard_simulator/illustrations/illustrations/vanguard_system.jpg)

Due to the risk of long-term information disclosure of interior guard layers,
path restrictions have been disabled for onion service circuits built when
vanguards are in use. This means that vanguards can be chosen
from the same /16 subnet and node family as earlier hops in the circuit.
Additionally, we also allow the same relay to be present in multiple positions
in the path. These changes prevent an adversary from learning which relays are
vanguards by creating many circuits and observing which relays are *not*
chosen in the rendezvous endpoint position.

Furthermore, to better protect the identity of these new pinned guard nodes,
and to avoid linkability of activity, the circuit lengths have been
altered for rendezvous point circuits, hidden service directory circuits, and
introduction point circuits. You can see them here (where L1 is the first
layer guard, L2 is second layer guard, L3 is third layer guard, M is random
middle):

![Vanguard Path
Lengths](https://raw.githubusercontent.com/asn-d6/vanguard_simulator/illustrations/illustrations/new_paths.jpg)

The number of nodes in each of these sets, as well as the ranges on rotation
times for each set, can be specified as config file parameters. The subsystem
currently uses 2 entry guards, 4 layer2 guards, and 8 layer3 guards.

## The Rendguard Subsystem

The Rendguard subsystem keeps track of how often various relays appear in the
rendezvous point position on the service side of an onion service. Since
rendezvous points are chosen by the client that connects to a service, it
is possible for clients to [choose malicious, colluding rendezvous
points](https://www.ieee-security.org/TC/SP2013/papers/4977a080.pdf) to
help them mount guard discovery and other attacks.

This subsystem emits warnings and optionally closes the circuit when a
rendezvous point is chosen too often compared to its consensus weight (the
"too often" limit is set by the **rend_use_max_use_to_bw_ratio** config
option, which defaults to 5X of a relay's consensus weight).

We assign an aggregate weight of **rend_use_max_consensus_weight_churn**
(default: 1% of consensus total) for relays that are not in our current
consensus that are used as rendezvous points. It is valid to use relays that
are not in the consensus as rendezvous points, and this can happen naturally
when a client's consensus is from a different time period as the service's
consensus. To prevent arbitrary computers from being used as rendezvous
points, we set this bound on the maximum amount of consensus churn, and use
that to limit all rendezvous requests that are not present in the service's
consensus.

When rendezvous points are overused and blocked by the addon, the effect is
that clients get connection refused responses when they attempt to use
rendezvous points that are already overused. Since the adversary gets to pick
their rendezvous point, they can trigger these limits at will, and cause
popular rendezvous points to be blocked by your service. If this happens, you
can set **rend_use_close_circuits_on_overuse** to false in your configuration
file. If you do this, rendezvous overuse messages will appear at WARN level,
but circuits will not be closed.

If you experience false positives with this system, also consider raising
**rend_use_global_start_count** and **rend_use_relay_start_count**. Please
[file a ticket](https://github.com/mikeperry-tor/vanguards/issues) if you have
to change any of these options.

## The Bandguards Subsystem

The bandguards subsystem performs accounting to watch for signs of bandwidth
sidechannel attacks on individual onion service circuits as well as exit
circuits. It then closes circuits that exceed these limits and emits log
messages. While we expect the default values to be set properly, these limits
can be tuned through configuration as well. See the [configuration
file](https://github.com/mikeperry-tor/vanguards/blob/master/vanguards-example.conf)
for more details.

These limits (along with a reason for checking them) are as follows:

1. ***Dropped Cell Limit***

   Back in 2014, the Tor network [was attacked](https://blog.torproject.org/tor-security-advisory-relay-early-traffic-confirmation-attack) by Carnegie Mellon researchers ([likely on behalf of the FBI)](https://blog.torproject.org/did-fbi-pay-university-attack-tor-users). The attack injected a side channel using a special packet type that could be recognized at both ends of a Tor circuit.

   This side channel was fixed. Unfortunately, there are many other side channels available that allow an adversary to inject traffic that is ignored by a Tor client.

   These remaining side channels are not as severe -- they cannot immediately
be recognized by colluding relays using packet information alone. Instead the
adversary must rely on packet volume and timing information in order to
recognize the signal. However, if the volume of injected traffic is large
enough or the cells are injected when traffic would not otherwise be sent, it
may still be possible to use statistical methods to recover a signal. This class
of attack is called [DropMark](https://petsymposium.org/2018/files/papers/issue2/popets-2018-0011.pdf),
and it likely works in practice.

   In fact, it may even be possible to inject so much dropped cell traffic
that this causes a change in the public [Guard relay bandwidth history or descriptor
value](https://metrics.torproject.org/rs.html#search/flag:Guard), which allows
Guard discovery.

   The Bandguards component uses [new control port features](https://gitlab.torproject.org/tpo/core/tor/-/issues/25903) and [improved connection tracking in Tor](https://gitlab.torproject.org/tpo/core/tor/-/issues/25573) to measure
the quantity of traffic that Tor decides to drop from a circuit, to protect against
all such attacks that rely on dropped cells.

   The allowed dropped cell count is 0, and cannot be configured.

   Note that if your guard is malicious, it can ignore the DESTROY cell

2. ***Total Hidden Service Descriptor Kilobytes***

   In addition to injecting relay cells that are dropped, it is also possible for relays to inject data at the end of an onion service descriptor, or in response to an onion service descriptor submission. Tor will continue reading this data prior to attempting to parse the descriptor or response, and these parsers can be convinced to discard additional data.

   The bandguards subsystem sets a limit on the total amount of traffic allowed on onion service descriptor circuits (currently 30 kilobytes). Once this limit is exceeded, the circuit is closed and a WARN log message is emitted by the bandguards subsystem.

   If your service uses OnionBalance, or has set a large number of custom
introduction points, you may need to raise this limit via the
**circ_max_hsdesc_kilobytes** setting in the [configuration
file](https://github.com/mikeperry-tor/vanguards/blob/master/vanguards-example.conf).

3. ***Total Service-Side Introduction Circuit Kilobytes***

   Introduction circuits are normally held open by services for ~18-24 hours,
regardless of traffic quantity or activity, which makes them a risk for
flood and check traffic analysis attacks. Additionally, introduction
requests are a vector for denial of service, since they cause the service to
spend considerably more resources to handle than they take to generate.

   It turns out that closing introduction circuits after too many are sent can
help with both of these cases. It does impact reachability, though, so this
option should be used with care. It is off by default. (The long-term solution
DoS solution is either [Proof of
Work](https://gitlab.torproject.org/tpo/core/torspec/-/blob/master/proposals/327-pow-over-intro.txt)
or [Introduction Tokens](https://gitlab.torproject.org/tpo/core/torspec/-/blob/master/proposals/331-res-tokens-for-anti-dos.md)).

   When **circ_max_serv_intro_kilobytes** is non-zero, the bandguards
subsystem sets a limit on the total amount of traffic allowed on onion service
introduction circuits. Once this limit is exceeded, the circuit is closed and a WARN
log message is emitted by the bandguards subsystem.

4. ***Total Circuit Megabytes***

   A final vector for injecting side channel traffic is at the application layer.

   If an attacker wants to introduce a side channel towards an onion service, they can fetch large quantities of data from that service, or make large HTTP posts towards the service, in order to generate detectable traffic patterns.

   These traffic patterns can be detected in Tor's [public relay bandwidth
statistics](https://metrics.torproject.org/rs.html#search/flag:Guard), as well
as via netflow connection volume records. The Tor Project is currently working
on various mechanisms to reduce the granularity of these
statistics (and has already reduced them to 24 hours of aggregate data), and
has also deployed padding mechanisms to limit the resolution of netflow traffic
logs, but it is not clear that these mechanisms are sufficient to obscure very
large volumes of traffic.

   Because of this, the bandguards subsystem has the ability to limit the
total number of bytes sent over a circuit before a WARN is emitted and the
circuit is closed.  This limit is currently set to 0 (which means unlimited).
If you know a reasonable bound for the amount of data your application or
service should send on a circuit, be sure to set it to that value.

   **If your service or application depends upon the ability of people to make
very very large transfers (such as OnionShare, or a SecureDrop instance), you
should keep this disabled, or at best, set it to multiple gigabytes.**

   If your service is a normal website that does not transmit large content,
100 megabytes is a reasonable value for this setting.

   We believe that using two entry guards makes closing the circuit a
worthwhile defense for applications where it is possible to use it. If the
adversary is forced to split their side channel across multiple circuits, they
won't necessarily know which guard node each circuit traversed. This should
increase the quantity of data they must inject in order to successfully mount
this attack (and by more than just a factor of two, because of this uncertainty).

   The traffic splitting done by
[Snowflake](https://gitlab.torproject.org/tpo/anti-censorship/pluggable-transports/snowflake)
and the [TurboTunnel prototype for obfs4](https://github.com/net4people/bbs/issues/14#issuecomment-544747519)
will also provide some degree of mitigation here.

   Long-term, this feature is meant to be deployed in combination with
[conflux traffic splitting](https://gitlab.torproject.org/tpo/core/torspec/-/blob/master/proposals/329-traffic-splitting.txt) so that we
can tear down one path of a circuit after over-use without loss of
connectivity, and reconnect the remaining portion to a new circuit.

   If you wish to enable this defense, change the value of
**circ_max_megabytes** in the [configuration file](https://github.com/mikeperry-tor/vanguards/blob/master/vanguards-example.conf).

   Additionally, if you notice this defense triggering, or other signs of
unexpected high load or DoS attack, consider monitoring your Guard relay
bandwidth in the [public relay bandwidth data]((https://metrics.torproject.org/rs.html#search/flag:Guard)) to check for
noticable bumps in traffic that correspond to DoS, as this is a Guard
discovery signal for the adversary. If you notice such bumps, please
[contact the Tor Project](https://anonticket.onionize.space/), as this means
that our relay bandwidth reporting is too detailed.

5. ***Max Circuit Age***

   Since Tor currently rotates to new TLS connections every week, if a circuit stays open longer than this period, then it will cause its old TLS connection to be held open. After a while, the circuit will be one of the few things using that TLS connection. This lack of multiplexing makes traffic analysis easier.

   For an example of an attack that makes use of this type of side channel, see [TorScan](https://eprint.iacr.org/2012/432.pdf). For additional discussion, see Tor Ticket [#22728](https://gitlab.torproject.org/tpo/core/tor/-/issues/22728) and [#23980](https://gitlab.torproject.org/tpo/core/tor/-/issues/23980).

   For this reason, if your onion service does not require long-lived circuits, it is wise to close any that hang around for long enough to approach this rotation time.

   The current default for maximum circuit age is 24 hours, and can be changed
via **circ_max_age_hours** in the [configuration
file](https://github.com/mikeperry-tor/vanguards/blob/master/vanguards-example.conf).
It does not make much sense to make this value significantly lower (and low
values such as 1 hour will make you stand out), but set it higher if you need
long-lived connections to your service.

6. ***Connectivity to the Tor Network***

   Reachability itself is a side-channel. An adversary can correlate your
uptime to other events to reduce your anonymity, or even actively attempt to
influence connectivity to parts of the Tor network to determine if a specific
service is using them. Because of this, we have added monitoring of connectivity
to the Tor Network. The addon will alert you if all of your guard connections
go down, or if you are unable to build circuits for a set amount of time.

   Obviously, clients may want to disable this monitoring, especially if they
are disconnected frequently. To disable these checks, change the
***circ_max_disconnected_secs*** and ***conn_max_disconnected_secs***
configuration settings to 0.

   There are additional mitigation tips for this attack vector in
[README\_SECURITY.md](https://github.com/mikeperry-tor/vanguards/blob/master/README_SECURITY.md).
In particular, the [Snowflake pluggable transport](https://gitlab.torproject.org/tpo/anti-censorship/pluggable-transports/snowflake) and
the [TurboTunnel resumption prototype](https://github.com/net4people/bbs/issues/14#issuecomment-544747519) for obfs4 will
mitigate the various forms of confirmation attacks of this side channel.

# Security Information

For additional security information, including attack vectors that
remain against onion services and potential mitigations, please see
[README\_SECURITY.md](https://github.com/mikeperry-tor/vanguards/blob/master/README_SECURITY.md).

