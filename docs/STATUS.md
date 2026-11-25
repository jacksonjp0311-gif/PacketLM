# PacketLM Status

Last updated: 2026-11-25

## Current position

**Milestone: M0–M4 complete. General path in progress.**

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0–M4 | Original plan | Done |
| G1–G17 | Store through residual memory | Done / begun |
| G18 | Residual-aware learning | Begun |
| G19 | Gap proposals (new packets from uncovered bits) | Begun |

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
8. Persistent residual memory — begun
9. Residual-aware learning and gap proposals — begun

## Where we are
All original milestones are done. The learning loop now prefers updates on uncovered material. New packets can be proposed from residual gaps and are kept only if they cover previously uncovered bits. A new public run is triggered.

## What it can do
A packet-based system that selects and re-queries compressed binary packets, measures them against an empty baseline, raises or lowers their strength based on whether they cover the correct next segment, prefers updates on material not yet covered, proposes new packets from residual gaps and keeps them only if they reduce uncovered bits, tracks holdout accuracy across multiple passes and domains, pulls an optional domain packet from outside, offers a language packet only after a kept cross-domain pass, and trains on longer windows across language, reasoning, and planning. It runs on ordinary CPU runners and leaves receipts. It is still a proxy, not a general language model.

## Open
- Still a proxy (claim boundary)
- Gap proposals and residual-aware learning not yet confirmed on a public run

## Next
Confirm the public run. Then make a proposed packet eligible for the feed only if it reduced residual and passed the two-domain gate.
