# PacketLM Status

Last updated: 2026-11-25

## Current position

**Milestone: M0–M4 complete. General path in progress. Not general intelligence.**

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0–M4 | Original plan | Done |
| G1–G29 | Store through identity bits | Done / begun |
| G30 | Direct token lookup (bypasses overlap proxy) | Begun |

## Goal
Turn PacketLM into a general intelligence: a system that improves its own packets under measurement, learns from language and sealed probes, and can accept and offer certified knowledge without losing the claim boundary.

## Honest distance
General intelligence would require real next-token or next-action learning that generalizes past the training windows, transfer to tasks the system was not given, sustained multi-step coherence, and a claim that survives sealed probes the cold start fails. Run #74 succeeded. A direct prompt-to-token map now measures accuracy without the overlap proxy. The claim has not moved.

## Where we are
All original milestones are done. The overlap proxy is no longer the only path. A direct table maps training prompts to their correct first token and is scored on holdout. A new public run is triggered.

## What it can do
A packet-based system that selects and re-queries compressed binary packets, measures them against an empty baseline, raises or lowers their strength based on whether they cover the correct next segment, trains a separate one-bit identity packet per vocabulary token, adds that identity bit to the residual when the token is missing, counts correct first tokens against that vocabulary, measures a direct prompt-to-token map that bypasses the overlap proxy, prefers updates on material not yet covered, proposes new packets from residual gaps and keeps them only if they reduce uncovered bits, tests whether a kept gap packet adds a sealed-probe hit the base store missed, tests a novel prompt not in the corpus against an empty store, tracks holdout accuracy across multiple passes and domains, pulls an optional domain packet from outside, and offers a kept gap packet only after a kept cross-domain pass and a residual reduction. It trains on longer windows across language, reasoning, and planning. It runs on ordinary CPU runners and leaves receipts. It is still a proxy, not a general language model.

## Open
- Still a proxy (claim boundary; will not move until measurements justify it)
- Direct lookup not yet confirmed on a public run
- Direct map does not generalize to unseen prompts
- No claim of general intelligence

## Next
Confirm the public run. If direct accuracy is higher than the overlap proxy, the limit was the proxy. The next move is to generalize the direct map beyond exact prompt match.
