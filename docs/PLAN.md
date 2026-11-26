# PacketLM plan: intelligence and self-edit

## Goal
A system that learns next-token, improves under measurement, and can edit itself only when a sealed score rises. Claim stays at what the receipts show.

## What is true now
- Packet store, residual, gates, and continuation scoring exist.
- A real tiny next-token model trains on the runner (embeddings, two attention layers, next-token head).
- Population self-edit is live: 4 mutated copies, score all, keep the best only if it beats the parent.
- It is tiny. It is not intelligent.

## Path to intelligence
1. Real next-token model — done at toy scale.
2. Score every change on a held-out continuation — done.
3. Grow the corpus and the context so the model has something to learn.
4. Self-edit by selection — first population loop landed.
5. Repeat. Intelligence is the accumulation of kept improvements, not a claim.

## Self-edit rules
- Make a small population of mutated copies.
- Score each on the same holdout continuation.
- Keep the best only if it beats the parent. Otherwise discard all.
- Every population and decision is a receipt.
- No edit is kept on vibes.

## What we will not do
- Call the current system intelligent.
- Auto-promote an edit that does not raise a sealed score.
- Hide a failed edit.

## Immediate next
Confirm the public run. Then shrink the mutation size when nothing improves.
