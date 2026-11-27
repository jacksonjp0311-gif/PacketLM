# PX: teacher statements of "no value" and "several values" (pre-registered)

This was written and committed before `python3 benchmarks/px.py --out px` ran on any registered
seed. The dev run (G48 worlds on seeds 998/999, G46 on seed 999) is committed in
`docs/evidence/px/dev/`, together with the code it ran.

## What is new

**The statements.** The teacher can now say `example NAME: s -> !none` (s has no value) or
`-> !several` (s has more than one value). Both mean "not withheld"; `unanswered` still means
withheld.

**How the engine judges them** (`engine.judge_set`, `programs.judge_set`):
- `!none` contradicts any prediction that has a value, and supports an empty prediction.
- `!several` contradicts a single value, supports two or more values, and is undetermined
  where the prediction is empty.
- Value answers are judged exactly as before. **The open-world rule is unchanged:** a program
  that predicts nothing where the truth is a value is still undetermined, never contradicted.

**Where they apply**
- in evaluation;
- in the base engine's open-world scan, where subjects with a negative statement join the
  scanned domain;
- in program search and its scan.

**Investigate (`--answers`).** Every answer class (a value, `!none` or `!several`) can split the
hypotheses. The engine asks where the worst-case elimination is largest. This is the
seed-33 mechanism (docs/G46_SEED33.md): one-sided splits become answerable.

**Tests**
- New g44 section `px` with 6 checks (95 → 101 checks).
- 4 new mutations; 46/46 killed with a clean baseline.
- One redundancy was found and recorded in mutations.py: a mutation of either half of the
  investigate change alone survives, because each half is enough on its own.

## What this can and cannot do (stated in advance)

**It can** eliminate alternatives that are **more defined** than the truth.

**It cannot** eliminate alternatives that are **less defined** than the truth. That would need
closed-world evidence, which the open-world rule refuses.

**It cannot** make the G48 program scan complete. Qualification also requires the MAX_SIZE scan
to finish within 200k programs, which it does not in G48 worlds. So no G48 task is expected to
qualify (dev: 0).

**Dev finding (G48 worlds), named as a mechanism before the run.**
- With `!none` stated at a T1 root, the reflexive recursive program that P acquires,
  `is:K:tgt|rel:U>self`, is correctly contradicted: it answers the root itself, where the truth
  has no value.
- At the next size, the recursive program and the depth-bounded `…|rel:U>rel:U` both remain
  supported. They differ only at depth ≥ 3, which is sealed, so the task is non-identifiable and
  ends unadopted.
- So R loses T1/T4 accuracy on sealed items while answering far fewer items whose truth has no
  value:

  | dev metric | P | R |
  |---|---|---|
  | T1 accuracy | 1.000 | 0.048 |
  | T4 accuracy | 1.000 | 0.750 |
  | spurious answers on no-value items | 6.0% | 1.0% |

- P's G48 T1 "1.000" was therefore partly carried by a program that is wrong on the roots.
  G48 never evaluated items without a value (verification Info of 82dd0a2).

## Protocol

**Part A, G48 worlds**
- Harness `benchmarks/g48.py`, unchanged except for the teacher and evaluation switches below.
- Seeds 521–527 (S = 7). Arms:
  - **P:** `--programs`, standard teacher;
  - **R:** `--programs --answers`; the teacher states `!none`/`!several` for non-sealed questions
    with no single value;
  - **V:** R + `--adaptive-retention`.
- **Abstention items (new, all arms):** after each task, every world entity whose truth has no
  single value (questions asked are excluded) is queried. A reply with a value is spurious.

**Part B, G46 curriculum**
- Harness `benchmarks/g46.py`. Seeds 11, 22, 33, 44 and 55.
- Arms:
  - **C:** as registered;
  - **E:** C + `--answers`; the teacher states `!none`/`!several` for non-sealed questions whose
    truth is undefined or ambiguous.
- G46 thresholds 1–6 are computed per arm exactly as `g46.evaluate` computes them for C.
  Thresholds 7–8 need the other G46 arms and are not part of PX.

Engine: the commit of this file. Cost is reported as whole-process CPU (`cpu_total_s`).

## Thresholds (all must hold)

| id | statement |
|---|---|
| PXA1 | R has 0 wrong-qualified answers |
| PXA2 | V's replies are byte-identical to R's on every seed |
| PXA3 | R's spurious-answer rate on no-value items is below P's, pooled |
| PXB1 | **E passes G46 threshold 6 on seed 33** (the registered failure, task `bbtwyr`) |
| PXB2 | E passes every G46 threshold 1–6 that C passes, on every seed, and has 0 wrong-qualified answers |
| — | source unchanged |

**Reported, not thresholds:**
- per-class accuracy on defined items for P, R and V (dev predicts R's T1/T4 drop, for the reason above);
- status mixes, with qualified counts for P and R and for C and E;
- negative statements given, and questions asked;
- the seed-33 task record for C and E;
- cost.

## Results

(Written after the registered run.)
