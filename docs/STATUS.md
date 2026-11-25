# PacketLM Status

Last updated: 2026-11-25

## Current position

**Milestone: M0–M4 complete. General path in progress.**

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0–M4 | Original plan | Done |
| G1–G11 | Store through cross-domain gate | Done / begun |
| G12 | Iterative loop uses two-domain gate | Begun |
| G13 | Offer only if gate kept a pass | Begun |

## Goal
Turn PacketLM into a general intelligence: a system that improves its own packets under measurement, learns from language and sealed probes, and can accept and offer certified knowledge without losing the claim boundary.

## Roadmap
1. Foundation — done
2. Stronger learning signal — begun
3. Third domain — confirmed
4. Cross-domain transfer gate — begun
5. Iterative gate that keeps a pass only if two domains improve — begun
6. Feed exchange of packets that passed the gate — begun
7. Scale corpus and context

## Where we are
All original milestones are done. The iterative loop now keeps a pass only if at least two domains improve; otherwise strengths are reverted. A language packet is offered only if the gate kept a pass. A new public run is triggered.

## What it can do
A packet-based system that selects and re-queries compressed binary packets, measures them against an empty baseline, raises or lowers their strength based on whether they cover the correct next segment, tracks holdout accuracy across multiple passes and domains, pulls an optional domain packet from outside, offers a language packet only after a kept cross-domain pass, and trains on language, reasoning, and planning windows. It runs on ordinary CPU runners and leaves receipts. It is still a proxy, not a general language model.

## Open
- Still a proxy (claim boundary)
- Gated iterative loop and gated offer not yet confirmed on a public run

## Next
Confirm the public run. Then scale the corpus.
