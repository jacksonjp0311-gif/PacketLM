# PacketLM Status

Last updated: 2026-11-25

## Current position

**Milestone: M0–M4 complete. General path in progress.**

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0 | Stub router + dummy packet | Done |
| M1 | First language training job that produces a receipt artifact | Done |
| M2 | Eval gate that can reject a run | Done |
| M3 | Residual loop improves multi-step holdout | Done |
| M4 | Public demo of a receipted loop on a communication task | Done |
| G1 | Packet store with strength and provenance | Done |
| G2 | Strength raised only when packet helps a sealed probe | Done |
| G3 | Next-token objective | Begun (public run succeeded) |
| G4 | Pull certified packets from NOMAD feed | Begun (one optional domain packet) |

## Where we are
All original milestones are complete. Packets have strength that rises only when they help a sealed probe. Next-segment prediction is measured on held-out windows. One optional domain packet is pulled from the NOMAD feed. No write-back.

## Capabilities
- Stores weights as many small binary packets instead of one big dense set
- Picks relevant packets for a question, removes what they already covered, and looks again
- Later looks can cover parts the first packet missed
- Checks every test against an empty start and against the single best packet
- Records whether the multi-step look covered at least as much as the first packet
- Records whether a sealed question was answered only when the packets were present
- Produces a two-turn continuation where the second turn keeps content from the first
- Raises a packet’s strength only when it improves a sealed probe over the empty baseline
- Measures next-segment prediction accuracy on held-out windows
- Pulls one optional domain packet from the NOMAD feed
- Runs on ordinary CPU runners and leaves a receipt you can open
- Still a proxy on a few short stories, not a general language model

## Open
- Still a proxy on a few short stories
- Next-token accuracy not yet inspected on the public artifact
- Feed pull is one-way and optional

## Next
Confirm the feed-pull receipt on the public run. Then decide whether to offer a language packet back to the feed.
