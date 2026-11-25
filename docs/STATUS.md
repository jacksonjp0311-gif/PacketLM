# PacketLM Status

Last updated: 2026-11-25

## Current position

**Milestone: M0–M4 complete. General path in progress.**

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0–M4 | Original plan | Done |
| G1 | Packet store with strength and provenance | Done |
| G2 | Strength raised only when packet helps a sealed probe | Done |
| G3 | Next-token objective | Begun |
| G4 | Pull certified packets from NOMAD feed | Begun |
| G5 | Closed learning loop (prediction-error updates strength) | Begun |

## Goal
Turn PacketLM into a general intelligence: a system that improves its own packets under measurement, learns from language and sealed probes, and can accept and offer certified knowledge without losing the claim boundary.

## Where we are
All original milestones are complete. Packets have strength that rises when they help a sealed probe or cover a correct next segment after a miss. Next-segment prediction is measured on held-out windows. One optional domain packet is pulled from the NOMAD feed. A closed learning loop now runs on the public runner.

## Capabilities
- Stores weights as many small binary packets instead of one big dense set
- Picks relevant packets for a question, removes what they already covered, and looks again
- Later looks can cover parts the first packet missed
- Checks every test against an empty start and against the single best packet
- Records whether the multi-step look covered at least as much as the first packet
- Records whether a sealed question was answered only when the packets were present
- Produces a two-turn continuation where the second turn keeps content from the first
- Raises a packet’s strength only when it improves a sealed probe over the empty baseline
- Raises strength of packets that cover the correct next segment after a miss
- Measures next-segment prediction accuracy on held-out windows
- Pulls one optional domain packet from the NOMAD feed
- Runs on ordinary CPU runners and leaves a receipt you can open
- Still a proxy on a few short stories, not a general language model

## Open
- Still a proxy on a few short stories
- Learning loop is one pass; not yet iterative
- Feed pull is one-way
- No general capability beyond the small story slice

## Next
Confirm the learn receipt on the public run. Then make the learning loop iterative so a second pass can improve on the first.
