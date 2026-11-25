# PacketLM Status

Last updated: 2026-11-25

## Current position

**Milestone: M0–M4 complete. General path in progress. Not general intelligence.**

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0–M4 | Original plan | Done |
| G1–G22 | Store through gap capability test | Done / begun |
| G23 | Next-token updates strength from prediction error | Begun |
| G24 | Transfer test on a novel prompt | Begun |

## Goal
Turn PacketLM into a general intelligence: a system that improves its own packets under measurement, learns from language and sealed probes, and can accept and offer certified knowledge without losing the claim boundary.

## Honest distance
General intelligence would require real next-token or next-action learning that generalizes past the training windows, transfer to tasks the system was not given, sustained multi-step coherence, and a claim that survives sealed probes the cold start fails. The first two are now measured. Neither has been shown to succeed. The claim has not moved.

## Where we are
All original milestones are done. Next-token now updates packet strength from prediction misses and measures holdout before and after. A transfer test runs a novel prompt not in the corpus and compares field against empty. A new public run is triggered.

## What it can do
A packet-based system that selects and re-queries compressed binary packets, measures them against an empty baseline, raises or lowers their strength based on whether they cover the correct next segment, updates strength from next-segment misses and measures holdout before and after, prefers updates on material not yet covered, proposes new packets from residual gaps and keeps them only if they reduce uncovered bits, tests whether a kept gap packet adds a sealed-probe hit the base store missed, tests a novel prompt not in the corpus against an empty store, tracks holdout accuracy across multiple passes and domains, pulls an optional domain packet from outside, and offers a kept gap packet only after a kept cross-domain pass and a residual reduction. It trains on longer windows across language, reasoning, and planning. It runs on ordinary CPU runners and leaves receipts. It is still a proxy, not a general language model.

## Open
- Still a proxy (claim boundary; will not move until measurements justify it)
- Next-token improvement and transfer not yet confirmed on a public run
- No sustained multi-step coherence past the proxy
- No claim of general intelligence

## Next
Confirm the public run. If transfer fails and next-token does not improve holdout, the next move is a larger held-out set and a real token-level objective, not another overlap proxy.
