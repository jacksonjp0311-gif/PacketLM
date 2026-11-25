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
| G1 | Packet store with strength and provenance | Done (strength rises on probe help) |
| G2 | Strength raised only when packet helps a sealed probe | Done (local run showed positive deltas) |
| G3 | Next-token objective | Begun (holdout next-segment measurement added) |
| G4 | Pull certified packets from NOMAD feed | Not started |

## Where we are
All original milestones are complete. Packets have strength that rises only when they help a sealed probe. A next-segment prediction measurement on held-out windows is now in the public runner.

## What it is
A small language model that does not store one dense set of weights. It holds many compressed binary packets. When a question or a continuation is asked, a router selects which packets are relevant for that step, removes what they already covered, and asks again. Later selections can cover parts the first packet missed. Packets have strength and provenance. Strength increases only when the packet improves a sealed probe over the empty baseline. A next-segment prediction is measured on held-out windows. A short public demonstration produces a two-turn continuation that stays consistent with the first. It runs on ordinary CPU runners. It is still a proxy on a few short stories, not a general language model.

## Open
- Still a proxy on a few short stories
- Next-token accuracy not yet confirmed on a public run
- No feed connection to NOMAD yet

## Next
Confirm the next-token accuracy on the public receipt. Then pull one certified packet from the NOMAD feed as an optional domain packet.
