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
