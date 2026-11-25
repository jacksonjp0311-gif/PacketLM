# PacketLM Status

Last updated: 2026-11-25

## Current position

**Milestone: M0–M4 complete. General path in progress. Not general intelligence.**

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0–M4 | Original plan | Done |
| G1–G26 | Store through token vocabulary | Done / begun |
| G27 | Token-identity training | Begun |

## Goal
Turn PacketLM into a general intelligence: a system that improves its own packets under measurement, learns from language and sealed probes, and can accept and offer certified knowledge without losing the claim boundary.

## Honest distance
General intelligence would require real next-token or next-action learning that generalizes past the training windows, transfer to tasks the system was not given, sustained multi-step coherence, and a claim that survives sealed probes the cold start fails. Run #69 succeeded. Vocabulary packets are now trained on token identity. The claim has not moved.

## Where we are
All original milestones are done. Each vocabulary token is its own packet. Strength of the correct token packet is raised on a miss. Holdout first-token accuracy is measured before and after. A new public run is triggered.

## What it can do
A packet-based system that selects and re-queries compressed binary packets, measures them against an empty baseline, raises or lowers their strength based on whether they cover the correct next segment, trains a separate packet per vocabulary token on token identity, counts correct first tokens against that vocabulary, prefers updates on material not yet covered, proposes new packets from residual gaps and keeps them only if they reduce uncovered bits, tests whether a kept gap packet adds a sealed-probe hit the base store missed, tests a novel prompt not in the corpus against an empty store, tracks holdout accuracy across multiple passes and domains, pulls an optional domain packet from outside, and offers a kept gap packet only after a kept cross-domain pass and a residual reduction. It trains on longer windows across language, reasoning, and planning. It runs on ordinary CPU runners and leaves receipts. It is still a proxy, not a general language model.

## Open
- Still a proxy (claim boundary; will not move until measurements justify it)
- Token-identity improvement not yet confirmed on a public run
- No sustained multi-step coherence past the proxy
- No claim of general intelligence

## Next
Confirm the public run. If first-token accuracy still does not rise, the next move is to stop updating strength and instead add the correct token packet to the residual path when it is missing.
