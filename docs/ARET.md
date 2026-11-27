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
- Archives and restores actually happen (17 and 13), so the check is not vacuous.
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
