# PacketLM Status

Last updated: 2026-11-25

## Current position

**Milestone: M0–M4 complete. General path in progress. Not general intelligence.**

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0–M4 | Original plan | Done |
| G1–G31 | Store through nearest-prompt | Done / begun |
| G32 | Multi-token generation | Begun |

## Goal
Turn PacketLM into a general intelligence: a system that improves its own packets under measurement, learns from language and sealed probes, and can accept and offer certified knowledge without losing the claim boundary.

## Faster plan
1. Stop polishing the overlap proxy — done for now
2. Generate multiple tokens, not one — begun
3. Score a full continuation, not a single first token — begun
4. Keep the packet store and the gates as the memory and the claim boundary
5. Then grow the corpus and the context

## Last push
Multi-token generation: chain nearest-prompt predictions and score the continuation against the target tokens.

## Honest distance
General intelligence would require real next-token or next-action learning that generalizes past the training windows, transfer to tasks the system was not given, sustained multi-step coherence, and a claim that survives sealed probes the cold start fails. The system can now produce a multi-token continuation and score it. That is still a proxy. The claim has not moved.

## Where we are
All original milestones are done. Generation now chains several nearest-prompt steps and records how many target tokens appear in the output. A new public run is triggered.

## What it can do
A packet-based system that selects and re-queries compressed binary packets, measures them against an empty baseline, raises or lowers their strength based on whether they cover the correct next segment, trains a separate one-bit identity packet per vocabulary token, adds that identity bit to the residual when the token is missing, counts correct first tokens against that vocabulary, measures a direct prompt-to-token map and a nearest-prompt fallback by shared tokens, generates a multi-token continuation and scores it against the target, prefers updates on material not yet covered, proposes new packets from residual gaps and keeps them only if they reduce uncovered bits, tests whether a kept gap packet adds a sealed-probe hit the base store missed, tests a novel prompt not in the corpus against an empty store, tracks holdout accuracy across multiple passes and domains, pulls an optional domain packet from outside, and offers a kept gap packet only after a kept cross-domain pass and a residual reduction. It trains on longer windows across language, reasoning, and planning. It runs on ordinary CPU runners and leaves receipts. It is still a proxy, not a general language model.

## Open
- Still a proxy (claim boundary; will not move until measurements justify it)
- Multi-token continuation not yet confirmed on a public run
- Continuation is nearest-prompt chaining, not learned next-token
- No claim of general intelligence

## Next
Confirm the public run. Then grow the corpus and replace nearest-prompt chaining with a learned next-token step that updates from the continuation score.
