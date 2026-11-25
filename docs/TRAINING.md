# Training Focus

PacketLM trains first on language learning, understanding, reasoning, and communication. Expansion into other domains happens only after these are measurable.

## Phase 1 — Language

- Corpus: TinyStories-scale (short, clean, vocabulary-constrained).
- Goal: loss decreases, local coherence appears, next-token prediction on held-out stories beats a non-looped baseline under the same seed.
- Metric: cross-entropy or exact-match on short continuations.

## Phase 2 — Understanding

- Probes: questions whose answers are present in the training packets but require retrieval + combination.
- Sealed holdout: cold-start (no field prior) fails; field succeeds.
- Metric: accuracy on sealed understanding set.

## Phase 3 — Reasoning

- Multi-step sequences (simple chains, comparisons, short deductions).
- Residual hops must improve accuracy over single-hop.
- Metric: hop-depth ablation on sealed reasoning probes.

## Phase 4 — Communication

- Continuation, clarification, simple turn-taking that stays consistent with prior context.
- Metric: consistency score against a sealed dialogue set.

## Rules

- Every phase has a pre-registered sealed set.
- Promotion only on twin (cold vs field) certified delta.
- Receipts include seed, packet pulls, and gate result.
- No auto-promotion.
