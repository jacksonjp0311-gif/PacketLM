# PacketLM Status

Last updated: 2026-11-25

## Current position

**Milestone: M0–M4 complete. Real next-token model begun. Not general intelligence.**

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0–M4 | Original plan | Done |
| G35 | Tiny next-token model | Fixed after run #82 failed |
| G36 | Longer training and holdout continuation score | Begun |

## Goal
Turn PacketLM into a general intelligence: a system that improves its own packets under measurement, learns from language and sealed probes, and can accept and offer certified knowledge without losing the claim boundary.

## Last push
Fix output matrix index. Train longer. Score the model's continuation against the holdout.

## Honest distance
Run #82 failed because the output matrix was indexed by vocab size but stored by dimension. That is fixed. The model is still tiny. It is an LLM in the narrow sense. It is not a general language model. The claim has not moved.

## Where we are
All original milestones are done. The real model is fixed and now trains longer. Holdout continuation overlap is measured before and after training. A new public run is triggered.

## What it can do
A packet-based system that also trains a tiny next-token model with embeddings and one attention layer, generates from that model, and scores the continuation against held-out windows. The packet store, residual, gates, and continuation scoring remain. It runs on ordinary CPU runners. It is still tiny, not a general language model.

## Open
- Fixed model not yet confirmed on a public run
- One attention layer, small dimension
- Not a general language model

## Next
Confirm the public run. If it succeeds and holdout does not rise, train more steps or add a second attention layer.
