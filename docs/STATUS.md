# PacketLM Status

Last updated: 2026-11-25

## Current position

**Milestone: M0–M4 complete. General path begun.**

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0 | Stub router + dummy packet | Done |
| M1 | First language training job that produces a receipt artifact | Done |
| M2 | Eval gate that can reject a run | Done |
| M3 | Residual loop improves multi-step holdout | Done |
| M4 | Public demo of a receipted loop on a communication task | Done |
| G1 | Packet store with strength and provenance | Begun |
| G2 | Strength raised only when packet helps a sealed probe | Begun |
| G3 | Next-token objective | Not started |
| G4 | Pull certified packets from NOMAD feed | Not started |

## Where we are
All original milestones are complete. The first self-improvement step is in: packets are addressable units with strength. Strength rises only when a packet helps a sealed probe more than an empty store. The receipt records the changes.

## What it is
A small language model that does not store one dense set of weights. It holds many compressed binary packets. When a question or a continuation is asked, a router selects which packets are relevant for that step, removes what they already covered, and asks again. Later selections can cover parts the first packet missed. Packets now have strength and provenance. Strength increases only when the packet improves a sealed probe over the empty baseline. A short public demonstration produces a two-turn continuation that stays consistent with the first. It runs on ordinary CPU runners. It is still a proxy on a few short stories, not a general language model.

## Open
- Still a proxy on a few short stories
- No real next-token objective yet
- No feed connection to NOMAD yet

## Next
Confirm the strength-update receipt on a public run. Then add a simple next-token measurement on held-out windows.
