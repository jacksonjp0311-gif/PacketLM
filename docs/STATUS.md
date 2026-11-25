# PacketLM Status

Last updated: 2026-11-25

## Current position

**Milestone: M0–M4 complete. General path in progress.**

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0–M4 | Original plan | Done |
| G1–G7 | Store, strength, next-token, feed, learning, offer, corpus | Done / begun |
| G8 | Second domain (reasoning windows) | Begun |

## Goal
Turn PacketLM into a general intelligence: a system that improves its own packets under measurement, learns from language and sealed probes, and can accept and offer certified knowledge without losing the claim boundary.

## Where we are
All original milestones are complete. Language and simple reasoning windows are now loaded together. Iterative learning and a local language-packet offer run on the public runner.

## What it can do
A packet-based system that selects and re-queries compressed binary packets, measures them against an empty baseline, raises their strength when they help sealed probes or correct next segments, tracks holdout accuracy across multiple passes, pulls an optional domain packet from outside, offers a language packet back, and now trains on both language and simple reasoning windows. It runs on ordinary CPU runners and leaves receipts. It is still a proxy, not a general language model.

## Open
- Still a proxy
- Reasoning domain not yet confirmed to improve holdout
- Feed connection is one-way plus a local offer
- No general capability beyond short windows

## Next
Confirm the public run on the combined corpus. Then add a third domain or a stronger next-token objective.
