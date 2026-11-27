# OPS-1: acquiring bounded, predicate-terminated iteration on unfamiliar graphs (pre-registered)

This responds to audit 283f526, items 5–8: the geography failure, type-constrained
variable-depth traversal, and abstractions acquired from observations.
It was written before `benchmarks/ops1.py` ran on any registered seed.

## What is new, and what is not

- **New program step:** `op:until:R:Q:T`. Follow R from each node for 1 to 8 steps,
  stop at the first level holding a node x with fact `x Q T`, and answer those nodes.
  This gives bounded iteration, a predicate and a termination condition in one step.
- **Implementation:**
  - geometric: per-start bit-row compositions masked by the predicate row;
  - symbolic: sets;
  - independent check: `reference.first_with`.
- **Designed by hand:** the control structure (the grammar of `until`) is supplied,
  just as sequential composition was. The claim is not that PacketLM invented iteration.
- **Acquired from observations:** which relation is iterated, which predicate stops the
  iteration, and that a procedure is an iteration rather than a fixed path. Candidates
  (Q, T) are the properties that every observed answer shares; R ranges over told relations.
  Nothing names a domain.
- **Default:** off (`operators=False`, CLI `--operators`), so G44–G46 behaviour is unchanged.

## Protocol (seeds 41, 42, 43; 3 graphs per seed; every engine call is a new process)

- **Graph:** random names throughout, including the relations.
  - Relations: up-relation U, type relation K, distractor relation D.
  - Types: top, target and low.
  - Structure: 3 roots of type top. Under each root, 3 target nodes. Under each target node,
    chains of untyped or low nodes ending in leaves at depths 1–4 below the target.
    D links each leaf to a random node.
- **Hidden procedure:** leaf → its nearest target-typed ancestor, i.e. `until:U:K:target`.
- **Teaching:** facts, then 3 examples at depths 1 and 2 only, then at most 4
  `investigate` rounds answered by the harness. The harness refuses questions about
  sealed nodes (`unanswered`).
- **Sealed evaluation:** leaves at depths 3 and 4 (depths never shown), plus
  intermediate nodes. Afterwards a new subtree with depths 5–6 is taught, and its leaves
  are asked (transfer within the graph).
- **Arms:**
  - O: operators on;
  - X: operators off (control);
  - S: operators on, with each example's answer replaced by another graph node of the target type (shuffled).

## Thresholds (all must hold)

1. O acquires `until:U:K:target` (expanded base equal) in at least 8 of 9 graphs.
2. O gives 0 wrong qualified answers on sealed and transfer queries.
3. O, sealed plus transfer: accuracy among all answered queries (qualified or provisional) ≥ 0.95, and coverage ≥ 0.9.
4. X gives 0 wrong qualified answers and acquires nothing equal to the hidden procedure.
5. S matches in at most 1 of 9 graphs.
6. Regression: with operators off, suite and G45 are unchanged.
   With operators on, G45 is reported as it falls (not a threshold).

Provisional answers are counted and reported separately. Under open-world qualification
(audit item 2), a less-defined alternative such as `U ∘ until` cannot be excluded by
any answer, so provisional status is expected. It is not a failure of threshold 3.

## Results

**Registered run** on ops-dev `82d0410` (engine sha in receipt), seeds 41/42/43:
`docs/evidence/ops1/ops1_receipt_registered_82d0410.json` plus raw data.
- O acquired `until:U:K:target` in **9/9** unfamiliar graphs.
- **0** wrong qualified answers.
- Accuracy among answered **1.0**, coverage **1.0**, over 249 sealed and transfer queries per seed.
  These include depths 3–6, which were never shown in examples.
- All 9 capabilities are **provisional**: 747 provisional answers. Open-world blockers
  remain, for example the type relation itself conflicting on low-typed intermediate nodes,
  and questions about sealed nodes are refused.
- X (operators off): 0 acquisitions and 0 answers. In every graph a fixed path qualified
  first and was suspended by the mixed-depth examples.
- S (shuffled): 0 matches, 0 wrong qualified answers.
- **All 5 thresholds held, and the source was unchanged.**

**Confirmation** on the merged engine (after the exact efficiency change):
`ops1_receipt_merged.json`. Metrics are identical.

**Regression:**
- Operators off: suite 150/150 and G45 decisions identical.
- Operators on: G45 still 18/18 with no domain outcome changed
  (`docs/evidence/g45_receipt_operators_on.json`).

**Geography (audit item 5):** teaching sessions 006–007 (`data/teaching/`).
- `country` is re-acquired as `op:until:in:isa:country`.
  - texas → usa, dallas (3 hops) → usa, nice (1 hop) → france, all `[provisional]`.
  - The old `in+in` was suspended by the texas example.
- `continent`, pinned to country@1, was suspended with it. That cost 2 of 14 probes in session 006.
  The teacher requalified it in 007 as `op:until:in:isa:continent`, and retention went back to 16/16.

**Limits:**
- The `until` grammar is designed by hand. What is acquired is which relation, which
  predicate and that a procedure iterates.
- Not yet acquired: conditionals (if-then-else) and predicates used as filters outside `until`.
- Qualification stays provisional for these programs. A less-defined alternative
  (`in ∘ until`) cannot be refuted by any answer under the open-world rule. A teacher statement
  that closes the world (e.g. "nothing contains europe") would be needed; it is not implemented.
