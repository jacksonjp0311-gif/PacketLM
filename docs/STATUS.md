# PacketLM Status

Last updated: 2026-11-25

## Current position

**Milestone: M0–M4 complete. General path in progress. Not general intelligence.**

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0–M4 | Original plan | Done |
| G1–G32 | Store through multi-token generation | Done / begun |
| G33 | Learned update from continuation score | Begun |

## Goal
Turn PacketLM into a general intelligence: a system that improves its own packets under measurement, learns from language and sealed probes, and can accept and offer certified knowledge without losing the claim boundary.

## Faster plan
1. Stop polishing the overlap proxy — done for now
2. Generate multiple tokens — done
3. Score a full continuation — done
4. Update from the continuation score — begun
5. Grow the corpus and the context

## Last push
Learned next-token step: on a miss, write the correct next token into the table and re-score the continuation.

## Honest distance
General intelligence would require real next-token or next-action learning that generalizes past the training windows, transfer to tasks the system was not given, sustained multi-step coherence, and a claim that survives sealed probes the cold start fails. Run #79 succeeded. Generation now updates from the continuation score. The claim has not moved.

## Where we are
All original milestones are done. Multi-token generation is live. On a miss, the correct next token is written into the table and the continuation is re-scored. A new public run is triggered.

## What it can do
A packet-based system that selects and re-queries compressed binary packets, measures them against an empty baseline, raises or lowers their strength based on whether they cover the correct next segment, trains a separate one-bit identity packet per vocabulary token, adds that identity bit to the residual when the token is missing, counts correct first tokens against that vocabulary, measures a direct prompt-to-token map and a nearest-prompt fallback by shared tokens, generates a multi-token continuation, scores it against the target, and updates the map from misses so the next continuation prefers the correct token. It prefers updates on material not yet covered, proposes new packets from residual gaps and keeps them only if they reduce uncovered bits, tests whether a kept gap packet adds a sealed-probe hit the base store missed, tests a novel prompt not in the corpus against an empty store, tracks holdout accuracy across multiple passes and domains, pulls an optional domain packet from outside, and offers a kept gap packet only after a kept cross-domain pass and a residual reduction. It trains on longer windows across language, reasoning, and planning. It runs on ordinary CPU runners and leaves receipts. It is still a proxy, not a general language model.

## Open
- Still a proxy (claim boundary; will not move until measurements justify it)
- Learned continuation update not yet confirmed on a public run
- Update is table rewrite, not a gradient on a model
- No claim of general intelligence

## Next
Confirm the public run. Then grow the corpus so the learned map has more to generalize from.
