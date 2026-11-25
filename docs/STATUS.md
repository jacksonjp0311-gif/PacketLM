# PacketLM Status

Last updated: 2026-11-25

## Current position

**Milestone: M0–M4 complete. General path in progress.**

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0–M4 | Original plan | Done |
| G1–G9 | Store through stronger learning signal | Done / begun |
| G10 | Third domain (planning windows) | Begun |

## Goal
Turn PacketLM into a general intelligence: a system that improves its own packets under measurement, learns from language and sealed probes, and can accept and offer certified knowledge without losing the claim boundary.

## Roadmap
1. Foundation — done
2. Stronger learning signal — begun
3. Third domain — begun (planning windows)
4. Cross-domain transfer gate
5. Iterative gate that keeps a pass only if two domains improve
6. Feed exchange of packets that passed the gate
7. Scale corpus and context

## Where we are
All original milestones are done. Language, reasoning, and planning windows are now loaded. The learning loop gains on correct covers and loses a little on misses. A new public run is triggered.

## What it can do
A packet-based system that selects and re-queries compressed binary packets, measures them against an empty baseline, raises or lowers their strength based on whether they cover the correct next segment, tracks holdout accuracy across multiple passes, pulls an optional domain packet from outside, offers a language packet back, and trains on language, simple reasoning, and short planning windows. It runs on ordinary CPU runners and leaves receipts. It is still a proxy, not a general language model.

## Open
- Still a proxy
- Third domain not yet confirmed on a public run
- No cross-domain gate yet

## Next
Confirm the public run on three domains. Then add the cross-domain transfer gate.
