# PacketLM Status

Last updated: 2026-11-25

## Current position

**Milestone: M0–M4 complete. General path in progress.**

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0–M4 | Original plan | Done |
| G1–G8 | Store through second domain | Done / begun |
| G9 | Stronger learning signal (gain on correct, loss on miss) | Begun |

## Goal
Turn PacketLM into a general intelligence: a system that improves its own packets under measurement, learns from language and sealed probes, and can accept and offer certified knowledge without losing the claim boundary.

## Roadmap
1. Foundation — done
2. Stronger learning signal — begun
3. Third domain (tool-use / planning windows)
4. Cross-domain transfer gate
5. Iterative self-improvement that keeps a pass only if two domains improve
6. Feed exchange of packets that passed the gate
7. Scale corpus and context

## Where we are
All original milestones are complete. Language and reasoning windows are loaded. The learning loop now gains strength on correct covers and loses a little on misses. Holdout accuracy is tracked per pass.

## What it can do
A packet-based system that selects and re-queries compressed binary packets, measures them against an empty baseline, raises or lowers their strength based on whether they cover the correct next segment, tracks holdout accuracy across multiple passes, pulls an optional domain packet from outside, offers a language packet back, and trains on language and simple reasoning windows. It runs on ordinary CPU runners and leaves receipts. It is still a proxy, not a general language model.

## Open
- Still a proxy
- Stronger signal not yet confirmed on a public run
- No third domain yet
- No cross-domain gate yet

## Next
Confirm the public run. Then add a third domain of short planning windows.
