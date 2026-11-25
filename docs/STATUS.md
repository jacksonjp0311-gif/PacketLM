# PacketLM Status

Last updated: 2026-11-25

## Current position

**Milestone: M0–M4 complete. General path in progress.**

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0–M4 | Original plan | Done |
| G1–G13 | Store through gated offer | Done / begun |
| G14 | Corpus scaled | Done |

## Goal
Turn PacketLM into a general intelligence: a system that improves its own packets under measurement, learns from language and sealed probes, and can accept and offer certified knowledge without losing the claim boundary.

## Roadmap
1. Foundation — done
2. Stronger learning signal — begun
3. Third domain — confirmed
4. Cross-domain transfer gate — begun
5. Iterative gate — begun
6. Feed exchange of gated packets — begun
7. Scale corpus and context — begun (language stories expanded)

## Where we are
All original milestones are done. Run #52 finished successfully. The language corpus is now larger. The iterative loop keeps a pass only if two domains improve. The offer is gated.

## What it can do
A packet-based system that selects and re-queries compressed binary packets, measures them against an empty baseline, raises or lowers their strength based on whether they cover the correct next segment, tracks holdout accuracy across multiple passes and domains, pulls an optional domain packet from outside, offers a language packet only after a kept cross-domain pass, and trains on a larger set of language, reasoning, and planning windows. It runs on ordinary CPU runners and leaves receipts. It is still a proxy, not a general language model.

## Open
- Still a proxy (claim boundary)
- Scaled corpus not yet measured on a public run

## Next
Confirm the public run on the larger corpus. Then lengthen the context windows.
