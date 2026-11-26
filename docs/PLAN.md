# PacketLM plan: intelligence and self-edit

## Goal
A system that learns next-token, improves under measurement, and can edit itself only when a sealed score rises. Claim stays at what the receipts show.

## What is true now
- Packet store, residual, gates, and continuation scoring exist.
- A real tiny next-token model trains on the runner (embeddings, two attention layers, next-token head).
- It is tiny. It is not intelligent.

## Path to intelligence
1. Real next-token model — done at toy scale.
2. Score every change on a held-out continuation, not a sample.
3. Grow the corpus and the context so the model has something to learn.
4. Self-edit: propose a change, measure, keep only if holdout rises.
5. Repeat. Intelligence is the accumulation of kept improvements, not a claim.

## Self-edit rules
- The model may propose a change to its own weights or training settings.
- The change is applied on a copy.
- Holdout continuation is scored before and after.
- Keep only if the score rises. Otherwise discard.
- Every proposal and decision is a receipt.
- No edit is kept on vibes.

## What we will not do
- Call the current system intelligent.
- Auto-promote an edit that does not raise a sealed score.
- Hide a failed edit.

## Immediate next
Implement the first self-edit loop: propose a learning-rate or weight nudge, measure holdout, keep only on improvement.
