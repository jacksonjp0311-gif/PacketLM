# PacketLM Status

Last updated: 2026-11-25

## Current position

**Milestone: M0–M4 complete. General path in progress.**

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0–M4 | Original plan | Done |
| G1–G10 | Store through third domain | Done / begun |
| G11 | Cross-domain transfer gate | Begun |

## Goal
Turn PacketLM into a general intelligence: a system that improves its own packets under measurement, learns from language and sealed probes, and can accept and offer certified knowledge without losing the claim boundary.

## Roadmap
1. Foundation — done
2. Stronger learning signal — begun
3. Third domain — confirmed (run #48 succeeded)
4. Cross-domain transfer gate — begun
5. Iterative gate that keeps a pass only if two domains improve
6. Feed exchange of packets that passed the gate
7. Scale corpus and context

## Where we are
All original milestones are done. Run #48 confirmed the three-domain load. A cross-domain gate is now in: a learning pass is kept only if at least two domains improve. The public runner executes it.

## What it can do
A packet-based system that selects and re-queries compressed binary packets, measures them against an empty baseline, raises or lowers their strength based on whether they cover the correct next segment, tracks holdout accuracy across multiple passes, pulls an optional domain packet from outside, offers a language packet back, trains on language, reasoning, and planning windows, and keeps a learning pass only if at least two domains improve. It runs on ordinary CPU runners and leaves receipts. It is still a proxy, not a general language model.

## Open
- Still a proxy (claim boundary; stays until measurements justify more)
- Cross-domain gate not yet confirmed on a public run

## Next
Confirm the cross-domain receipt. Then make the iterative loop use the two-domain gate.
