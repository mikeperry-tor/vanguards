# Accepted Tor receive behavior

Bandguards protects tracked circuits by comparing Tor's `CIRC_BW` received
bytes with the credit Tor assigns to delivered data and protocol overhead.
Treat the deficit as a count of uncredited relay cells. Tor can credit a
cell whose contents it discards. The control event aggregates bytes for a
circuit and carries no per-cell disposition or source hop. The decisions
below apply to C Tor 0.4.9 and guide future reviews of changes to that
accounting. [Tor control specification](https://spec.torproject.org/control-spec/replies.html#bandwidth-used-by-all-streams-attached-to-a-circuit)

## Half-closed streams

Tor accepts some in-flight cells after a stream closes locally and credits
them in circuit accounting. With congestion control, a deadline controls
this acceptance. The legacy stream window uses a remaining-cell allowance.
Bandguards cannot distinguish credited in-flight cells that Tor discards
from other credited traffic, including on onion-service rendezvous circuits.
We accept this limit in the addon. An `END_ACK` relay command could let Tor
end the grace period sooner when the peer acknowledges closure. Tor still
needs a timer because a peer can withhold that acknowledgement.
[Tor specification issue #196](https://gitlab.torproject.org/tpo/core/torspec/-/work_items/196)

## Conflux

Conflux can delay credit for legitimate traffic while Tor reorders it across
legs. Bandguards skips the dropped-cell check on linked Conflux exit
circuits and keeps its other circuit limits active. Tor owns
`ConfluxEnabled`. A complete fix belongs upstream, where Tor can distinguish
receive disposition from delayed delivery. We accept the exemption because
the addon's primary purpose is onion-service security and C Tor uses Conflux
for ordinary exit circuits. [Operator guidance](../README_TECHNICAL.md#the-bandguards-subsystem)

## First-hop and second-hop padding

Link padding terminates on the first-hop connection. The built-in Tor
0.4.9 circuit-padding machines negotiate with the second hop, and Tor gives
received padding credit when it comes from the negotiated hop. These are
accepted cover traffic. Evaluate end-to-end relay acceptance separately
from the timing or volume of early-hop padding. Unexpected circuit padding
can still appear as an uncredited cell in Bandguards accounting.
[Tor circuit padding specification](https://spec.torproject.org/padding-spec/circuit-level-padding.html)
