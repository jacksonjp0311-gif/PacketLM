# ARET: evidence-gated adaptive retention vs static retention (pre-registered before any registered run)

**Engine:** commit 6d29b75, `source_hash` 205d0829533f…. The engine is frozen for these runs.

**Question:** the utility problem. Retained knowledge raises the cost of every later call
(docs/G46_V3.md). Can the system decide, from its own use evidence, what to keep hot, and
lower that cost without changing any answer? Requested in the LA feedback ("archive, never
delete").

## Mechanism (packetlm/retention.py, `--adaptive-retention`)

**Knowledge component:** a union-find over hot knowledge.
- A fact joins its subject, relation and object, the facts it was derived from, and any
  capability in its proofs.
- A capability, observation, hypothesis or retired-example record joins every relation,
  capability and entity it references.
- Every reply reads within one component, or within the components named on its line.

**Use evidence:** a per-token record of the first call that touched it and its last 4 touches.
A line touches the following:
- every word on the line;
- what the lexicon maps those words to;
- the meaning of any construction whose word appears on the line.

**Gate** (run at save; constants fixed here; bytes are the cost proxy, because load,
validation and save scale with bytes):
- `n_c = min(64, call − first_touch_c)`
- `u_c` = the number of distinct calls among the last `n_c` that touched component c
- `q_c = (u_c + 1)/(n_c + 2)`
- **Archive iff** `q_c · (b_c + 4096) < b_c`, `n_c ≥ 8`, and c was not touched in the current call.

**Archive:**
- A component is written as an immutable, content-addressed file, `<state>.archive/<sha256>.json`,
  and removed from the hot state.
- Its tokens stay in a hot index.
- Archive files are never deleted or rewritten. An append-only `events.jsonl` logs every
  archive and restore.

**Restore:**
- Before a line is processed, every archived component naming one of the line's tokens is
  read, checked against its address and schema, and merged back.
- A collision, a missing file or a mismatch raises an error. Nothing is reconstructed silently.
- `capabilities` (a full listing) restores everything.
- Opening an adaptive state with static retention restores everything and reports it.

**Checks** (g44 `retention.*`):
- Differential against static: replies are identical over 111 calls that include
  archive/restore of unrelated families, a correction in an archived family, a relation shared
  across entity-disjoint families, a construction sentence and a full listing.
- Archives and restores actually happen (17 and 13 when written with GUARD = 2; 18 and 14 in the receipt at 0b0f6a8 with GUARD = 1; verification L4), so the check is not vacuous.
- No archive file is ever deleted, and re-archiving reuses the same file.
- Recently touched components are never archived.
- A static open restores everything.
- Mutations killed: `restore_off`, `gate_ignores_recent`, `archive_deleted_on_restore`,
  `static_ignores_archive`.

**Development:** only dev seed 999 was used, to set GUARD. GUARD = 2 left G46-U unchanged,
because each family-end retention probe restores everything; GUARD = 1 was chosen. Seeds
11/22/33 have not been run with this mechanism.

## Experiment

**Arms**, all on the same frozen engine:
- **C**: static retention;
- **A**: adaptive retention;
- **B**: empty state per task.

**Curricula:**
- G46 (compositional, 36 tasks, 6 families);
- G46-U (unrelated, 24 tasks).

Same teacher, worlds, budgets and cost accounting as docs/G46.md and docs/G46U.md. Seeds
11, 22, 33. Run with `python3 benchmarks/aret.py`.

**Cost measure:** task CPU, exported to the learning-amortization CSV with
`benchmarks/la_export.py`. The instrument is pinned at 70297af and unmodified, run with 5000
bootstrap draws. Maintenance (family-end correction, transfer and retention calls) is
reported as the `+maint` variant.

### Hypotheses and thresholds (fixed now)

- **H-R1, no harm (must hold).** In every curriculum and seed, arm A matches arm C exactly on:
  - per-task acquisition, sealed correctness and every sealed reply;
  - every family record (correction, transfer, retention, post-correction);
  - 0 wrong-qualified answers and no aborted arm.

  Any difference fails H-R1 and is reported with the differing rows.
- **H-R2 (unrelated curriculum).** `A_24(A‖C)` on G46-U has a 95% CI lower bound > 0.
- **H-R3 (compositional curriculum).** `A_36(A‖C)` on G46 has a 95% CI lower bound > −0.05.
  This is a no-meaningful-loss bar.
  - Prediction: a gain, because each family's retention probe touches older families only once
    per family.

**Reported without a threshold:**
- `A(A+maint‖C+maint)`;
- `A(A‖B)` against `A(C‖B)` (how much of the utility problem remains);
- hot bytes per task;
- archive bytes and file counts;
- archive and restore counts.

**Not claimed in any outcome:**
- that the byte proxy is the true cost model. The CPU per call against hot bytes is reported
  so the proxy can be judged;
- any result beyond these two curricula and this harness.

**Pre-registered limitation.** The harness's own retention measurement touches every earlier
family at each family end. That counts as real use, and it forces restores. The result is
therefore specific to this usage pattern.

## Results (registered seeds 11/22/33, engine 205d0829…, unchanged during the run; evidence in docs/evidence/aret/)

**H-R1, no harm: PASS.** In both curricula and all seeds, arm A matches arm C exactly:
- per-task acquisition, sealed correctness and every sealed reply;
- every family record;
- 0 wrong-qualified answers and no aborts.

### Task CPU in seconds (seeds 11 / 22 / 33)

| | C (static) | A (adaptive) | B (empty) |
|---|---|---|---|
| G46 | 7.01 / 7.18 / 6.38 | **3.64 / 3.66 / 3.32** | 4.80 / 4.62 / 4.70 |
| G46-U | 2.10 / 1.98 / 2.05 | **1.18 / 1.25 / 1.29** | 0.19 / 0.17 / 0.19 |
| G46 maintenance | 1.38 / 1.41 / 1.59 | 1.03 / 0.99 / 1.05 | n/a |
| G46-U maintenance | 4.91 / 4.62 / 4.73 | 3.69 / 3.72 / 3.63 | n/a |

### Instrument results (pinned 70297af, unmodified, 5000 bootstrap draws)

| contrast | G46 (36 tasks) | G46-U (24 tasks) |
|---|---|---|
| `A(A‖C)` | **+0.484 [+0.481, +0.490]**, break-even 8 | **+0.394 [+0.369, +0.439]**, break-even 4 |
| `A(A+maint‖C+maint)` | +0.452 [+0.443, +0.459] | +0.276 [+0.247, +0.305] |
| `A(A‖B)` | **+0.249 [+0.208, +0.295]**, break-even 24 | −5.74 [−6.35, −5.26] |
| `A(C‖B)`, same run | −0.457 [−0.553, −0.358] | −10.12 [−10.65, −9.62] |

- **H-R2** (G46-U, lower bound > 0): **PASS**, with lower bound +0.369.
- **H-R3** (G46, lower bound > −0.05): **PASS**, with lower bound +0.481.
- **Censoring.** G46: A and C are censored on 1 task each, B on 11. B's censoring makes
  `A(A‖B)` a lower bound, by the instrument's rule. G46-U has no censoring.

**State sizes:**
- Mean hot state at task time: G46 211 KB (C) vs 57.5 KB (A); G46-U 284 KB vs 54 KB.
- The archive holds 378–387 KB in 5 files (G46) and about 542 KB in 23 files (G46-U). It is
  never deleted, and re-archiving reused files.
- The final hot state of A is about the size of C's. The last family-end retention probe
  restores everything, and A also carries its use records (+3% on G46, +6% on G46-U).

**Byte proxy:** per-process task CPU against hot bytes at task time gives Pearson r = 0.854
(G46) and 0.822 (G46-U), with slopes of about 0.10 ms per KB. Bytes are a reasonable proxy
here, but not the whole cost.

### Reading

- On the compositional curriculum, `A_36(A‖B)` = +0.25 on task CPU **with censoring, not at
  matched accuracy**. (Corrected after verification M2; the original sentence said "at matched
  accuracy".) The caveats belong in the same sentence:
  - it falls to +0.031 [−0.005, +0.071] when maintenance is charged (M1);
  - it comes from the 11/108 task instances where B misses the accuracy target; on tasks both
    arms solved it is about −0.04 (M2);
  - the interval is a 3-seed bootstrap, so p is at least 0.25 (M3);
  - process startup is excluded; including it gives +0.112, or −0.056 with maintenance (M4).

  A does solve 36/36/35 tasks against B's 32/32/31. Read this as roughly break-even with an
  empty-state learner, not as a demonstrated saving.
- On the unrelated curriculum, retention halves the gap but does not close it.
  - With nothing to reuse, any retained state is overhead.
  - Every family-end retention probe touches all history, which forces a restore each time.
- The utility problem is reduced by a measured, evidence-gated policy with no change to any
  answer. It is not solved:
  - G46-U `A(A‖B)` is still −5.7;
  - the gate's constants were chosen once, on dev seed 999, and were not tuned on these seeds.

## Verification of 0b0f6a8 (branch verify-0b0f6a8, d931dc2): response

The verifier reproduced every count, the no-harm result bit for bit, and the instrument output
from the committed CSVs. It found no leakage and no moved threshold. My responses, all
accepted:

- **M1.** `A(A+maint‖B)` is now reported, above.
- **M2.** "At matched accuracy" is removed. The jointly-solved figure is reported.
- **M3.** Every interval in this document is a **seed bootstrap with S = 3** (sign-flip p is at
  least 0.25), not a confidence interval that covers timing noise.
  - H-R2 and H-R3 should be read as "all 3 seeds exceed the bar".
  - The verifier's rerun moved point estimates by up to 0.04 on G46 and 0.5 on G46-U.
- **M4.** The cost boundary excludes interpreter startup and imports, about 0.033 s per process.
  - A(A‖C) remains strongly positive under every boundary: +0.26 with startup included.
  - The empty-state comparisons depend on the boundary.
  - From G48 on, the CLI also reports `cpu_total_s` (whole-process CPU), and
    `la_export.py --total` exports it. The primary cost for new runs is whole-process CPU with
    maintenance charged.
- **L1.** The dev-seed history (GUARD 2 → 1 on seed 999) was not pushed before registration. The
  claim that registered seeds were not used for tuning cannot be checked from the repo. From
  now on, dev runs are committed before the pre-registration.
- **No rerun of ARET to improve the number.** Any new retention measurement will be
  pre-registered with more seeds.
