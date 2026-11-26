# PacketLM Status

Last updated: 2026-11-25

## Current position

**Milestone: M0–M4 complete. Real next-token model begun. Not general intelligence.**

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0–M4 | Original plan | Done |
| G1–G34 | Proxy path through grown corpus | Done / begun |
| G35 | Tiny next-token model (embeddings + one attention layer) | Begun |

## Goal
Turn PacketLM into a general intelligence: a system that improves its own packets under measurement, learns from language and sealed probes, and can accept and offer certified knowledge without losing the claim boundary.

## What formed
A real next-token model. Pure Python. Token embeddings, one causal attention layer, a next-token head. Trained by prediction error on the corpus windows. Generates by argmax. Receipt records loss and a sample.

## Honest distance
This is an LLM in the narrow sense: it maps context to a next-token distribution and is trained on that objective. It is tiny. It is not a general language model. The claim has not moved past that.

## Where we are
All original milestones are done. The proxy path remains. The real model is now first on the runner. A new public run is triggered.

## What it can do
A packet-based system that also trains a tiny next-token model with embeddings and one attention layer, generates from that model, and leaves a receipt of the loss and the sample. The packet store, residual, gates, and continuation scoring remain. It runs on ordinary CPU runners. It is still tiny, not a general language model.

## Open
- Tiny model not yet confirmed on a public run
- One attention layer, small dimension, short training
- Not a general language model

## Next
Confirm the public run. Then train longer and score the model's continuation against the holdout, not only a sample.
