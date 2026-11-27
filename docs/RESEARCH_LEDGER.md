# PacketLM research ledger

Cumulative. Newest last. Times in America/New_York.
Status words: implemented, demonstrated, qualified (pre-registered criteria
met plus controls), HOLD, failed.

## 2026-11-26 20:14 — audit of main

- main = checkpoint a560fa846ba13937b198222d7e981da78b7b250a.
- 8/8 workflow modules, 47 checks, 0 failed. 10 modules crashed: `Router.path_union`
  was removed in 6a345a5. Three weak checks were found.

## 2026-11-26 ~20:20 — G44 v1 (PR #1, b8cbe6c)

- One engine; 39 checks; 86 suite checks.
- Failure kept: `docs/evidence/g44_first_run_failed.json` (wrong test expectation).

## 2026-11-26 20:39 — G44 audit resolution (engine schema 2)

Pre-registered: `docs/G44_AUDIT.md` (commit 6e20bbe), before the run.

Changes to v1 check semantics (names kept, policy changed by the audit):
- `discovery.*`: the result is now `provisional` while the `rg` gap blocks. The old
  expectation that the result was simply "acquired" broke audit item 2.
- `fresh_process.p3/p4/p5`: answers now say `[no construction for grand]`
  (item 9). Correcting a premise on a capability's own observed path now
  **suspends** it (item 3), so `what is ann grand` answers
  `unknown (grand@1 suspended)` instead of silently recomputing `eve`.
- `memory.correction_drops_derived`: now uses a premise off the observation
  path, so the capability stays qualified and its live answer is recomputed.
- `acquisition.binary_equals_walk`: now compares against `reference.py`
  (independent), not the engine's own walk.

Results: suite 125/125 checks, 15/15 mutations killed. See G44_AUDIT.md.
Failure kept: `docs/evidence/g44_audit_run1_failed.json` (real bug, fixed).

Open: G44 qualification is up to the external auditor. Search depth is at most 3 in
tests. Hypothesis space grows as P², and P³ with the library.

## 2026-11-26 20:45 — PRE-REGISTERED: learning amortization metric (before any measurement)

Central hypothesis (docs/STANDING_DIRECTIVE.md): acquiring, abstracting and reusing
verified capabilities can make later acquisition cheaper.

**A_n = 1 − C_continual(n) / C_baseline(n)** over the first n tasks of one fixed task sequence.

- Continual learner: one persistent engine state across the sequence, library on.
- Baseline: an empty-memory learner. It gets a fresh state per task, is taught the same
  facts and the same examples for that task, and has the library off.
- Both use the same search strategy: iterative deepening, length 1, then 2, then 3,
  stopping at the first length with a unique supported candidate. Both get the same
  example budget and the same investigation budget.
- Equal accuracy is required. A_n is reported only where both reach the same accuracy
  on the same sealed evaluation queries. Otherwise the accuracy gap is reported
  instead, and A_n is marked not comparable.
- C counts everything the learner does for the task: process CPU time for load,
  schema validation, teaching, acquisition (candidate generation and evaluation),
  qualification (blocking-alternative checks), investigation, evaluation queries,
  and the atomic save. That covers storage, retrieval, maintenance and execution.
  CPU time is the primary cost. Secondary costs, reported alongside: engine
  operation counts (hypothesis evaluations, program executions, bit-row ops,
  asks), saved state bytes, and examples plus questions used.
- Controls reported with A_n: frozen learner (library frozen after the first
  phase), shuffled-evidence learner, geometry-disabled learner (`--no-geometry`),
  and the reference learner (`reference.learn`).
- Sign convention: A_n > 0 means the continual learner was cheaper. Negative values
  are reported as they are. No threshold is tuned after observation.
- Developer changes vs acquired improvement: the engine source sha256 is
  recorded and frozen for every A_n run. Any change between runs is a developer
  improvement, not a learned one.

- teaching `001_kinship.txt` 2026-11-26T20:45:28-05:00: facts 0→13, capabilities 0→3 {'qualified': 3}, constructions 0→5; retention 0/0, new probes 7/7; cpu 0.005s; engine abc472f0c03b

- teaching `002_geography.txt` 2026-11-26T20:45:28-05:00: facts 13→25, capabilities 3→5 {'qualified': 5}, constructions 5→7; retention 7/7, new probes 3/4; cpu 0.009s; engine abc472f0c03b

- teaching `003_mechanism.txt` 2026-11-26T20:45:28-05:00: facts 25→34, capabilities 5→7 {'qualified': 7}, constructions 7→8; retention 10/11, new probes 3/3; cpu 0.014s; engine abc472f0c03b

- teaching `004_change.txt` 2026-11-26T20:45:28-05:00: facts 34→34, capabilities 7→7 {'qualified': 7}, constructions 8→8; retention 9/11, new probes 5/5; cpu 0.011s; engine abc472f0c03b

- teaching `005_probe_fixes.txt` 2026-11-26T20:45:46-05:00: facts 34→34, capabilities 7→7 {'qualified': 7}, constructions 8→8; retention 14/14, new probes 2/2; cpu 0.01s; engine 082297186215

## 2026-11-26 20:55 — G45 interactive learning (pre-registered in docs/G45.md, commit 04463b9)

- chat.py now runs on Engine.turn. Its old discover/acquire/turn are removed, with the
  pre-migration copy at docs/evidence/chat_pre_g45.py.txt. The 5 historical chat checks pass.
- Policy change, recorded: a correction to a premise on an example's proof path
  **retires** that example (dependent evidence) instead of suspending the procedure.
  A new contradicting or corrected **example** still suspends it. G44 fresh-process
  expectations p4/p5 were updated to match. See G44 test `audit.example_correction_invalidates`.
- G45 result: 18/18 thresholds. 6/6 domains in every seed. Shuffled 0/6. No-library 0/3.
  Full table in docs/G45.md.
- Negative observation: search cost grows with accumulated primitives (20 → 696 evaluations).
- Suite: 11/11 modules, 144 checks, 0 failed. Mutations: 15/15 killed.

### Trained state (data/trained/, separate from all test fixtures)

The trained state is taught only through `python -m packetlm.teach <session>`, which runs
Engine.turn. Sessions 001–005 (kinship, geography, mechanism, change, probe fixes).
After 005 it holds 7 qualified capabilities, 3 retired examples, and 16 live probes,
of which 16 pass. Two probes were mis-specified by the teacher, not failed by the
engine: `texas country` and `shaft3 spins` after a correction. Their failures
stay in data/trained/sessions.jsonl and are superseded in 005.

### Reproduce

```bash
python -m packetlm.suite          # every module in fresh processes, counts
python -m packetlm.g44_test       # 57 checks at the time (86 at 2026-11-26 22:45)
python -m packetlm.mutations      # 15 mutations at the time (33 at 22:45), each must be killed
python -m packetlm.g45_test       # 18 pre-registered checks (~15 s)
python -m packetlm.chat --interactive   # talk to the same engine
# replay the trained state from scratch into a scratch copy:
#   rm data/trained/*; for f in data/teaching/*.txt; do python -m packetlm.teach $f; done
```

## 2026-11-26 21:05 — developer improvement: bitset activation in hypothesis search (not learned)

- Cause: in G45, candidate evaluations grew 20 → 696 as accumulated relations
  entered the primitive set.
- Change: a candidate is enumerated only while its image of the observed
  subjects stays non-empty. The image is one bit-row composition per step
  (`Engine._image`). Pruned candidates predict nothing on any observation
  (undetermined, zero support). They are kept as a counted complement
  (`hypotheses[name].pruned`), not stored one by one. This is exact: the
  `audit.activation_same_decision` check compares against `activation=False`.
  Standard bitset reachability pruning; no novelty is claimed.
- Measured (G45 rerun, same seeds, `docs/evidence/g45_receipt_activation.json`):
  evaluations per domain are 20, 20, 20, 20, 29, 20, against 20…696 before. Engine CPU
  per seed is 1.16–1.26 s, against 1.30–1.56 s. State is 0.93 MB, against 1.06 MB; it is
  now dominated by stored 4096-bit fact packets, not hypotheses. G45 is still 18/18.
- Audit-item-1 check rewritten. Stored + pruned = reference live (81). Zero-support
  stored + pruned = reference (72). With activation off, all 81 are stored.
- Suite 11/11, 145 checks. Mutations 16/16 killed, including the new `activation_overprunes`.
- Ablation flag: `--no-activation`.

## 2026-11-26 21:40 — response to independent audit of 283f526 (docs/audits/AUDIT_283f526.md)

James clarified that the audit is analysis to weigh, not a list of commands. Each item below gives
my judgement and what I did. G46 had not been run when these changes were made. Its
protocol (docs/G46.md) is unchanged, and the engine is frozen from the commit after this entry.

Evidence found before the audit arrived (dev seed 999, not a registered seed). In a G46 phase-B
family, `ef` was **qualified as `cap:ab`**: both programs gave the same value on the 2 examples.
Iterative deepening stopped at length 1, so the length-2 truth was never considered as an
alternative. This produced 6 wrong qualified transfer answers. It is a concrete instance of audit
items 1–3.

- **Item 1 (P0): pruning vs elimination. Agree.**
  - Activation pruning during candidate search drops only programs with an empty image of the
    observed subjects. Such programs have zero support, so they cannot be the supported
    candidate. That use was sound for selection.
  - It was not sound as an argument that they could not block. They are logically
    undetermined, not false.
  - Change: qualification now runs a separate scan, `Engine._scan`, over all programs up to the
    horizon. It is pruned on the *candidate's domain*, not on the evidence.
  - A pruned subtree is recorded as `pruned_compatible`: proved unable to give a defined
    value different from the candidate's anywhere on current knowledge. Nothing is
    recorded as eliminated.
- **Item 2 (P0): zero-support alternatives. Agree, with a stated assumption.**
  - Every non-contradicted program up to the horizon is an alternative, whatever its support.
  - It blocks if it **conflicts**: some entity where both programs give a defined, different
    value. It also blocks under the old G44 rule (support ≥1 and differs anywhere), so no
    previous blocking condition was removed.
  - The assumption is recorded verbatim in every scan (`Engine.ASSUMPTION`): open world over
    *current knowledge*, horizon H. Not counting None-vs-value as a disagreement for
    zero-support programs is the open-world reading: undefined is not a claim.
  - Limitation: new facts can create conflicts later, and qualification is not re-scanned
    automatically (`requalify NAME` does it).
  - Check `audit.zero_support_conflict_blocks`; mutations `open_world_off` and
    `prune_on_evidence_only` are both KILLED.
- **Item 3 (P1): shortest vs unique. Agree.**
  - Selection is still the shortest supported program; deepening stops at the first depth with a
    supported program, since deeper levels cannot remove it.
  - Identification is now separate: the scan covers *every* length up to the horizon
    (`--deepen`, or the fixed max length), and any conflicting longer program blocks.
  - Qualified now means "unique up to agreement on current knowledge within horizon H". It does
    not mean unique over all programs. The horizon is recorded in each version's evidence.
  - Several supported programs at the stopping depth still give `ambiguous`.
  - Check `audit.open_world_blocks_longer_alternative`; mutation `scan_short_horizon` is KILLED.
    Also new: `audit.deepen_stops_at_ambiguity` and mutation `deepen_past_ambiguity`.
- **Item 4 (P1): requalify on retirement. Agree.**
  - After a correction or retraction retires examples, the capability is requalified on the
    examples that remain. With none left, or with only unsupporting ones, it becomes provisional;
    otherwise the scan decides.
  - Earlier qualification is kept apart from the current status, in `qualified_at` and `history`.
  - This changes three previously expected replies:
    - G44 `p4`/`p5`: grand@1 is now provisional after both its examples are retired.
    - chat `tail`: still `orion hastail red`, now marked `[provisional]`.
  - In each case the old expectation was updated. The value checked is unchanged and the marker
    was added. Check `audit.retirement_requalifies`; mutation `no_requalify` is KILLED.
- **Item 5: the geography failure. Agree that it is real.** Scheduled after G46.
- **Items 6–8: richer programs, unfamiliar graphs, acquired abstractions.** I agree with the direction.
  The order is still correctness first, then G46, then this. The key standard is the audit's own
  item 8: the operators must be acquired from observations, not supplied as domain solvers.

**Results on the fixed engine**
- Suite: 11/11 modules, 149 checks, 0 failed; 10/10 smoke modules.
- Mutations: 21/21 killed. Three are killed only by a crash: `library_off`,
  `compose_keeps_source` and `no_backup_fallback`. Each of those raises from a test path rather
  than failing a named check, which is a weaker kill and still to be tightened.
- **G45 rerun: same outcome.** 18/18 thresholds; every domain decision, example count and
  evaluation score is identical in all 3 seeds. Shuffled control identical: seed 101 still
  qualifies one wrong program from shuffled evidence, because the shuffled examples are
  consistent with a single program and nothing conflicts with it.
- Cost of the scan: candidate evaluations per domain rose from 20 to 58–85. Engine CPU per
  seed rose from 1.16–1.26 s to 1.21–1.41 s.
- Evidence: `docs/evidence/g45_receipt_audit283.json`, `g44_receipt_audit283.json`,
  `g44_audit_mutations.json`.

## 2026-11-26 21:40 — G46 longitudinal benchmark: registered run (docs/G46.md § Results)

- **Protocol:** pre-registered in 283f526, with clarifications and the example-pool fix
  committed before any engine run. The engine changed (audit 283f526 fixes, 9c5315f) before
  the registered run; it was frozen at sha256 `cab85669629f…` for the run.
- **Aborted first attempt** (21:12–21:21): arm N spent more than 300 s per call. Nothing was
  read. Amendment 1 made the harness resumable and gave N a 120 s per-call budget.
- **Outcome: 26 of 27 seed-thresholds hold, so G46 is NOT passed.** Seed 33 threshold 6 fails:
  3 of 4 ambiguous-truth queries answered `ambiguous`, against the required ≥95%. The 4th
  was `unknown`, because its capability was itself ambiguous and nothing was adopted.
- **What held:**
  - retention 1.0 over 378 rechecks per seed;
  - plasticity 36/36, 36/36 and 35/36;
  - transfer 1.0, 1.0 and 0.972;
  - 0 wrong qualified answers;
  - corrections propagated 5/5;
  - 0 spurious answers on 86 undefined queries;
  - controls: frozen arm 0 phase-B acquisitions, shuffled arm 0 matches, geometry-off decisions identical.
- **H1 false:** `A_36(C‖B)` = −7.00 [−7.19, −6.85] on the pinned learning-amortization
  instrument. The continual learner costs about 8× the empty-memory learner, and the gap
  widens (log-ratio trend −0.069 per task). This is the utility problem.
- **H2:** `A^reuse_36(C‖P)` = +0.225 [+0.210, +0.254], break-even at task 28. P is censored on
  11 tasks against C's 1, so this is a lower bound. The receipt's strict equal-accuracy rule
  reports no value for H2, because C was more accurate.
- **Cause, from profiling:**
  - 93% of a phase-B acquisition is the open-world qualification scan (audit fix 9c5315f);
  - per-entity work runs over all 534 retained entities;
  - library capabilities widen the scan.
  Making qualification honest made it expensive. This is the first target for G48 and for the
  adaptive-retention experiment.
- **Learning-to-learn:** not claimed, and not supported.
- **Failure evidence kept:** the seed-33 receipt, the aborted-attempt note, and N's partial
  results in raw.
- **Reproduce:**
  - `python3 benchmarks/g46.py --seeds 11,22,33 --jobs 8` (about 6 min on 8 cores);
  - `python3 benchmarks/la_export.py artifacts/g46/g46_raw.json costs.csv`;
  - `PYTHONPATH=<learning-amortization@70297af> python3 -m amortization costs.csv --cont C --base B`.

## 2026-11-26 21:45 — G47 and G46-U (frozen engine `cab85669629f…`)

- **G47 (docs/G47.md):**
  - H3 (reach) true: library at depth 2 acquires 35–36 tasks against 15.
  - H4 true on the instrument: `A^reuse_36` = +0.225.
  - H5 false: the library costs more per acquired task at depth 3. The primitive arm is heavily
    censored, so the instrument's `A(L‖M)` = −0.82 is a lower bound.
  - 0 wrong qualified answers with the library.
- **G46-U (docs/G46U.md):** unrelated curriculum; 0 library uses; `A_24(C‖B)` = −23.1;
  `A_24(C‖P)` = −0.03. The predicted utility problem is confirmed and comes from retained
  knowledge, not the library.
- **Learning-amortization feedback (FEEDBACK_LA_integration.txt). I agree with:**
  - an external, unmodified instrument;
  - raw lifecycle CSVs (published for G46, G47 and G46-U);
  - censoring, read with the instrument's own direction notes;
  - both curricula, now run.
  Adaptive retention is pre-registered next, as its own experiment (G51-prep), after the exact
  efficiency work. The efficiency work is a developer improvement and changes no decision. It is
  measured and kept separate, so that G51 compares retention policies on the same engine.

- teaching `006_types.txt` 2026-11-26T21:20:28-05:00: facts 34→44, capabilities 7→7 {'qualified': 5, 'provisional': 1, 'suspended': 1}, constructions 8→8; retention 12/14, new probes 4/4; cpu 0.015s; engine f73a3e6cf9da

- teaching `007_requalify_continent.txt` 2026-11-26T21:20:37-05:00: facts 44→44, capabilities 7→7 {'qualified': 5, 'provisional': 2}, constructions 8→8; retention 16/16, new probes 3/3; cpu 0.016s; engine f73a3e6cf9da

## 2026-11-26 21:55 — audit 283f526 items 5–8; exact efficiency (G48-prep); merged ops-dev

- **Items 5–8.** I agree, and acted on them:
  - **until operator**, acquired from observations (docs/OPS1.md):
    - OPS-1 pre-registered and passed 5/5 thresholds;
    - 9/9 unfamiliar graphs, 0 wrong qualified answers, depths 3–6 generalised from examples at
      depths 1–2;
    - all results provisional under the open-world rule.
  - **Geography:** re-taught in sessions 006–007. Texas now gives usa.
  - **Partial disagreement on item 8.** The control structure itself is still designed, not
    acquired. I record that rather than claim it.
- **Considered and reverted** (no commit kept it): narrowing the G44 blocking rule so that a
  less-defined alternative does not block. It made the geography procedure qualify, but it broke
  two discovery checks that encode the open-world gap semantics. It would also have weakened a
  standing criterion. Kept: provisional.
- **Exact efficiency** (developer improvement, not learning):
  - the qualification scan walks distinct base sequences breadth-first;
  - it stops at 64 blockers (status already decided; counts flagged as lower bounds);
  - predictions and differences are computed only where a program can be defined.
  - Checks:
    - new `audit.scan_matches_bruteforce`, against the independent reference;
    - 23/23 mutations killed (new: `dedupe_by_last_step`, `domain_too_narrow`);
    - suite 150/150, G45 decisions identical.
  - Measured on G46 C's final state, for the same phase-B acquisition plus investigation:
    15.1 s → 0.65 s.
- **Teaching:** sessions 006 (types; retention 12/14 because of the dependency suspension) and
  007 (requalify continent; 16/16). Both are logged in sessions.jsonl and the lines above.

## 2026-11-26 21:57 — v3 re-measurement results (docs/G46_V3.md; evidence docs/evidence/v3/)

- **Decisions:** unchanged in every engine arm and seed. G46 stays **not passed (26/27)**:
  seed 33 threshold 6 fails at the same task.
- **G46 `A_36(C‖B)`:** −7.00 → **−2.15** [−2.17, −2.14].
- **`A^reuse_36(C‖P)`:** +0.225 → **+0.115** [+0.106, +0.132]; break-even 28 → 24.
- **G46-U:** `A_24(C‖B)` −23.1 → −19.3; `A(C‖P)` ≈ 0.
- **G47:**
  - H3 still true. **H5 flips to true**: at depth 3 the library arm is cheaper per acquired task.
  - `A(K‖Q)` = −0.41 and `A(L‖M)` = −0.25 (replicate). Both are lower bounds, because the
    primitive arms are censored.
- **Host stall in the first G47 v3 run:** five ~34 s outliers, all at about the same time.
  - A deterministic replay of one of them gave identical work in 2.7 s.
  - I ran **one declared replicate** in isolation, with no outliers.
  - Both runs are kept and reported. I did not rerun again to get a better number.
- **Interpretation:** about two thirds of the v2 penalty was implementation. The rest is the
  utility problem. Per-call cost scales with state size: load re-checks each fact's binding,
  and save runs two more full validations.
- **Next:**
  1. v4: exact persistence work, in progress on ops-dev.
  2. The ARET adaptive-retention experiment, pre-registered before any run.

- teaching `008_schema3_migration.txt` 2026-11-26T22:20:17-05:00: facts 44→44, capabilities 7→7 {'qualified': 5, 'provisional': 2}, constructions 8→8; retention 19/19, new probes 0/0; cpu 0.06s; engine 205d0829533f

## 2026-11-26 22:20 — v4 re-measurement and ARET adaptive retention (registered runs; docs/G46_V4.md, docs/ARET.md)

- **Engine v4** (schema 3, 205d0829…):
  - Packets are derived on demand and never stored. A schema-2 state is checked in full,
    migrated explicitly and reported.
  - Checks: g44 77/77, suite 164/164, 33/33 mutations killed, G45 18/18 with decisions
    identical.
- **v4 results:** decisions are identical to v3 everywhere, so G46 is still **not passed
  (26/27)**.
  - G46 `A_36(C‖B)`: −7.00 (v2) → −2.15 (v3) → **−0.448**.
  - `A^reuse(C‖P)` = **+0.280**.
  - G46-U `A_24(C‖B)` = −9.78.
  - G47: H3 and H5 still true; the H5 margin is small.
- **ARET** (pre-registered at 813697c before any registered run):
  - **H-R1 (no harm): pass.** Every reply and every family record is identical to the static arm.
  - **H-R2: pass.** G46-U `A_24(A‖C)` = +0.394 [+0.369, +0.439].
  - **H-R3: pass.** G46 `A_36(A‖C)` = +0.484 [+0.481, +0.490].
  - G46 `A_36(A‖B)` = +0.249 [+0.208, +0.295] (3-seed bootstrap), corrected after
    verification. It comes from the 11 tasks where B misses the target; on jointly solved tasks
    it is about −0.04. With maintenance charged it is +0.031 [−0.005, +0.071]. With process
    startup included it is +0.112, or −0.056 with maintenance. That is roughly break-even with
    an empty-state learner, not a demonstrated saving. (The earlier headline "first positive A
    … at matched accuracy" is withdrawn.)
  - G46-U `A(A‖B)` is still −5.74: on unrelated knowledge, retention halves the overhead
    but cannot remove it.
  - Byte proxy against CPU: r = 0.85 / 0.82.
- **Audit and LA response:** this is the "evidence-gated adaptive retention vs static" experiment
  the LA feedback asked for: archive, never delete, measured with the unmodified instrument.
  Gate constants were set on dev seed 999 only (GUARD 2 → 1, recorded in ARET.md) and not tuned
  on the registered seeds.
- **Teaching session 008** (schema-3 migration, no new teaching): the load report records
  "44 stored packets checked and dropped". Retention is 19/19. The v2 file is kept as
  state.json.bak.

## 2026-11-26 22:45 — Independent verification of 0b0f6a8 (branch verify-0b0f6a8, d931dc2): response

The verifier reproduced all counts, H-R1 bit for bit, and the instrument output from the
committed CSVs. It found no leakage and no moved thresholds. I did not modify that branch.

Every finding was weighed and every finding was accepted.

**M1–M4: the G46 `A(A‖B)` headline was overstated.**
- It now carries its caveats in the same sentence, in ARET.md, here and in the PR.
- "At matched accuracy" is removed.
- Intervals are labelled as 3-seed bootstraps with p ≥ 0.25.
- **Decision:** I am not rerunning ARET to get a better number. Any new retention or cost
  measurement will be pre-registered with S ≥ 5 seeds.

**Future cost logs include startup and maintenance (M4).**
- The engine CLI now reports `cpu_total_s`, getrusage over the whole process.
- The G45 and G46 teachers log it, and G46 task records store `eval_cpu_total_s`.
- `la_export.py --total` exports it. The default export is byte-identical to the committed
  ARET CSVs, which I checked.
- LA_EXPORT.md declares the primary cost from G48 on: whole-process CPU with maintenance
  charged.

**L1.** Dev runs will be committed before the pre-registration that relies on them.

**L2.** G45 threshold 7b is tightened to its registered wording ("not acquired at any
status"). This makes it stricter, not weaker. Rerun: 18/18, with no-library status `none` on
all 3 seeds.

**L3.** `teach.py` now refuses tokens from every `benchmarks/sealed_tokens*.json`.
- Added `sealed_tokens_g46u.json`, generated by `benchmarks/sealed_extra.py`, with 2016 tokens.
  This is a superset of the verifier's 672 sealed subjects because it uses `g46.sealed_tokens`.
- `data/` has 0 occurrences across all 2745 tokens.

**L4.** ARET.md now shows 17/13 → 18/14. The ledger reproduce block is annotated as
historical.

**L5.** The suite now lists each smoke demo's own False self-reports: 13 across 7 demos. These
are legacy demos and are not claimed as working.

## 2026-11-26 23:05 — G48 program acquisition and G47-AR: implementation and pre-registration (docs/G48.md, docs/G47_AR.md)

**`packetlm/programs.py`, a designed program grammar.**
- Tokens: `rel`, `cap`, `is`/`not` guards, and tail-recursive `self`.
- Programs: 1–2 clauses with ordered choice, at most 5 tokens.
- Integrated behind `--programs`; the base engine behaviour is unchanged without it.
- Tests:
  - g44 has a new `programs` section with 14 checks: memoized vs independent interpreter
    (6216 comparisons), provenance trace, ordered choice, until/conditional/filter/composition
    acquisition, dependency tracking through program strings, reload, and one-sided investigate.
  - 6 new mutations, all killed by named checks: **39/39 killed, 0 crash kills**.
- **The control structures are designed; their use is acquired.** The designed part is stated
  precisely in G48.md, including two narrowing assumptions:
  - relevance to the component of the observations;
  - qualification only when the open-world scan completes within 200k programs.

**Dev runs (seeds 998, 999), committed before registration (L1).**
1. T1 examples were unstratified. Fixed so that both depths 1 and 2 are always present.
2. A one-sided ambiguity reproduced the seed-33 mechanism. The programs-mode investigate now
   also asks where a hypothesis predicts nothing.
3. After both fixes, every threshold held on the dev seeds.

**G47-AR dev (seed 999).** No harm; whole-run whole-process CPU ratio 0.72 for both adaptive
arms.

**Registration.** Both runs use the post-verification cost rules (whole-process CPU, all
calls, maintenance included) and more seeds: G48 has 7, G47-AR has 5.

## 2026-11-26 23:15 — G48 and G47-AR registered results (docs/G48.md, docs/G47_AR.md)

**G48 (seeds 481–487): NOT passed as registered, 6 of 7 checks.**
- **Passes.** P accuracy is 1.000 in every class: T1 n 434, T2 168, T3 126, T4 434.
  - Depth ≥ 3 is 1.000 (n 378), including depths 6–7 (n 42).
  - Wrong-qualified: 0, with 14 qualified tasks (all T3) and 126 qualified answers.
  - Controls: X T1–3 is 0.000; S is 0.0009.
- **H6 FAILS.** On seeds 481 and 487, the adaptive arm asked different investigate questions in
  round-2 T4. The programs and every sealed answer were identical.
  - **Mechanism:** investigate breaks ties in fact-storage order, and a retention restore
    appends facts, which changes that order.
  - **Fix, after the run:** programs mode iterates entities sorted by name, with a new check
    and mutation (40/40 killed). The registered FAIL stays; confirming the fix needs a new
    registered run.
- **Base-engine hazard, not changed so G44–G47 stay comparable:** base investigate has the same
  order dependence. ARET H-R1 did not trigger it, but a future registered retention run on the
  base engine should either fix it under pre-registration or compare at the same strictness.

**G47-AR (seeds 11–55, S = 5): H-AR1 no harm PASS, H-AR2 PASS.**
- Whole-run, whole-process CPU, maintenance and startup included: W/K is 0.70–0.73 and Y/L is
  0.72–0.74. Each is lower on 5/5 seeds.
- Descriptive LA instrument: `A(W+maint‖K+maint)` = +0.288 and `A(Y+maint‖L+maint)` = +0.271,
  S = 5 with p = 0.0625.
- G47 H3 holds on 5/5 seeds.
- Per acquired capability at depth 3: Y 0.25 < L 0.35 < M 0.40–0.45 s.

**Leakage.** 0 of 1214 new item and sealed tokens occur in `data/`.

**Status.** g44 102/102; suite 189/189 across 11/11 modules; mutations 40/40 with 0 crash
kills; G45 18/18.

**Next.**
- A pre-registered G48 replication with the order-independent investigate, on new seeds, to
  settle H6.
- Then the teacher protocol extension (`-> none` / `-> several`), so the one-sided ambiguity
  can be answered for sealed-adjacent items.

## 2026-11-26 23:00 — G48R registered (docs/G48R.md): 6/7, H6 FAILS again; second cause found; not repeated

**Result.** G48 replicates on new seeds 491–497 for H1–H5:
- P is 1.000 in every class, including depths 3–7;
- 0 wrong-qualified, with 14 qualified tasks;
- X 0.000 and S 0.0017.

**H6 failure.** H6 failed on 3 seeds. With the tie-order fix in place, the remaining cause is
that programs-mode investigate scored entities of **other worlds**: in P they are hot; in A
they are archived.
- Of P's 12 differing questions, 9 lie outside the task's component, and all were refused.

**Decision (two failures, one root cause: investigate depends on hot state outside the task).**
- No third replication.
- Investigate now scores only the observations' component (check plus mutation; 41/41 killed).
- The no-harm property is re-tested in the next pre-registered experiment (PX, arm RA).
