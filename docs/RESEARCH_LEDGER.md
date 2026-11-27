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
python -m packetlm.g44_test       # 57 checks
python -m packetlm.mutations      # 15 mutations, each must be killed
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
