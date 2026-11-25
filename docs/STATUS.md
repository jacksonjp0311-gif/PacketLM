# PacketLM Status

Last updated: 2026-11-25

## Current position

**Milestone: M0–M4 complete. General path in progress.**

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0–M4 | Original plan | Done |
| G1–G16 | Store through longer windows | Done / begun |
| G17 | Persistent residual memory | Begun |

## Goal
Turn PacketLM into a general intelligence: a system that improves its own packets under measurement, learns from language and sealed probes, and can accept and offer certified knowledge without losing the claim boundary.

## Roadmap
1. Foundation — done
2. Stronger learning signal — begun
3. Third domain — confirmed
4. Cross-domain transfer gate — begun
5. Iterative gate — begun
6. Feed exchange of gated packets — begun
7. Scale corpus and context — begun
8. Persistent residual memory that changes the next selection — begun

## Where we are
All original milestones are done. A persistent residual now accumulates covered bits across turns. The next query has those bits removed before selection. The receipt records whether the path changed because of the memory. A new public run is triggered.

## What it can do
A packet-based system that selects and re-queries compressed binary packets, measures them against an empty baseline, raises or lowers their strength based on whether they cover the correct next segment, tracks holdout accuracy across multiple passes and domains, pulls an optional domain packet from outside, offers a language packet only after a kept cross-domain pass, trains on longer windows across language, reasoning, and planning, and keeps a running residual of what has already been covered so the next selection excludes it. It runs on ordinary CPU runners and leaves receipts. It is still a proxy, not a general language model.

## Open
- Still a proxy (claim boundary)
- Memory path-change not yet confirmed on a public run

## Next
Confirm the memory receipt shows a path change. Then make the learning loop consult the residual so updates prefer uncovered material.
