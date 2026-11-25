# PacketLM Status

Last updated: 2026-11-25

## Current position

**Milestone: M0–M4 complete. General path in progress.**

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0–M4 | Original plan | Done |
| G1–G14 | Store through scaled corpus | Done / begun |
| G15 | Longer context windows | Begun |
| G16 | Reasoning and planning expanded | Done |

## Goal
Turn PacketLM into a general intelligence: a system that improves its own packets under measurement, learns from language and sealed probes, and can accept and offer certified knowledge without losing the claim boundary.

## Roadmap
1. Foundation — done
2. Stronger learning signal — begun
3. Third domain — confirmed
4. Cross-domain transfer gate — begun
5. Iterative gate — begun
6. Feed exchange of gated packets — begun
7. Scale corpus and context — begun (longer windows, expanded domains)

## Where we are
All original milestones are done. Context windows are longer. Reasoning and planning domains are expanded to match the larger language set. The iterative loop keeps a pass only if two domains improve. The offer is gated. A new public run is triggered.

## What it can do
A packet-based system that selects and re-queries compressed binary packets, measures them against an empty baseline, raises or lowers their strength based on whether they cover the correct next segment, tracks holdout accuracy across multiple passes and domains, pulls an optional domain packet from outside, offers a language packet only after a kept cross-domain pass, and trains on longer windows across language, reasoning, and planning. It runs on ordinary CPU runners and leaves receipts. It is still a proxy, not a general language model.

## Open
- Still a proxy (claim boundary)
- Longer windows not yet confirmed on a public run

## Next
Confirm the public run. Then add a simple memory of recent packets so the next selection can use what was just used.
