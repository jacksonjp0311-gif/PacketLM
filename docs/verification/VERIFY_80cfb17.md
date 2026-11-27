# Independent verification of g44-canonical-engine at 80cfb17 (G59 `--partitioned` and the qualification gate; registered at 80cda1a)

Verifier clone `/workspace/verify-80cfb17`, branch `verify-80cfb17`, made from 80cfb17, plus detached worktrees of 80cda1a
(`/tmp/w80cda1a`, hashes) and 33565b0 (`/tmp/w33565b0`, cross-tree reference). `/workspace/PacketLM*` and the builder's
worktrees were not touched. Every CPU-heavy job ran through `tools_80cfb17/guard.sh` (waits while
`/workspace/REGISTERED_RUN.lock` exists); the lock was never present during my work (12:01–12:50 EST). `packetlm/` and
`benchmarks/` are identical at 80cda1a and 80cfb17. Instrument: `/workspace/vendor/learning-amortization` at 70297af, clean.

## Verdict

**The registered verdict (gate HOLD, switch rule triggered) reproduces exactly, and nothing I found would flip it in either
direction.** No High findings. Every registered number reproduces from the registered files (64/64 instrument contrasts
byte-equal in their first line; all point values of the gate, strata, work/time split, rate ratio and part S exponents equal
to the 4th decimal). `--partitioned` exactness held in every test (0 differences in 14.7k calls × 5 arms with crashes, torn
journals and padding; 4.9k calls hash-for-hash against the 33565b0 tree; kill −9 in real processes). The math of §2a is
correct. Counts reproduce (g44 191/191, suite 11/11, G45 18/18, mutations 193/194).

Two **Medium (report-only, interpretive)** findings concern how the result is described, not the result:
**M1** the switch-rule conclusion ("the limitation is the core representation") is the rule's registered stipulation, not
something G59's evidence isolates; the evidence points first at the search/utility layer, state-carrying and maintenance
accounting. **M2** "bounded in work" / "recall no longer scans unrelated codes" is overstated: the work count is
W₀ + c·N with a large N-independent W₀, and the recall's pair-hit set still grows linearly with N. Four Low and six Info items.

Both directions, summarized: factors that made G59 look **worse** than the engine is — 4-worker co-scheduling at 64k
(≈ +0.1 on α_task, L1), the registered maintenance charge (L2), reference censoring (recorded A is a lower bound), k's
small-state overhead (I2). Factors that made it look **better** — the call-count work metric (M2), the proportional charge
omitting replay (I3). Under every variant I computed, Q1 still fails (all comp CIs < 0) and α_task stays ≥ 0.37 ≫ 0.2.

## 1. `--partitioned` exactness

**Code reading (§2a proof).** Checked line by line against `Memo.part_threshold` / `recall_partitioned` (engine.py 720–771):
- Only triples with |p ⊕ q| ≤ 16 can add a name: decoding needs p ⊕ q to equal a role-2 code, and `bits_for` sets ≤ 16 bits
  (16 draws, field.py; max observed 16).
- p = X₀ ⊕ X₁ ⊕ X₂ ⊆ X₀ ∪ X₁ ∪ X₂, so m = |p∧q| ≤ Σ|Xᵢ∧q|; the largest overlap is ≤ 16, so the second largest is
  ≥ ⌈(m − 16)/2⌉ = k with m ≥ ⌈(|p| + |q| − 16)/2⌉ and |p| ≥ SMALL_PART = 42. Correct (the largest is ≥ the second).
- `_code_pairs` splits ≤ 16 ascending bits into ⌈len/⌈len/4⌉⌉ ≤ 4 groups, so k ≥ 5 overlapping bits put two in one group:
  an indexed pair of q's bits. Correct; k < 5 falls back to the G57b filter.
- Candidates = triples with two codes in H (s–r via by_sr, s–o, r–o), plus `small_part`. The memo's recall entry then holds
  only passing triples with |p ⊕ q| ≤ 16 (fewer than G57b's), but `ent` is used only for decoding, so replies and state are
  unaffected; `_added` still adds every passing new triple (a superset, harmless).

**Differential** (`tools_80cfb17/part_diff.py`, extending my verify-33565b0 `routed_diff.py`; independent of `g59_diff.py`).
Arms: REF (unindexed), XR64 (G58 registered config), XK (+`--partitioned`, read-only check, K from the run), XK64 (registered
config), XKP (XK64 + proportional maintenance, q = 1). After every call replies and `json.dumps(state)` byte-equal across arms;
`--deep` rebuilds every index structure from scratch, now including the code-pair index and `small_part` (exact equality);
final snapshot bytes equal across all arms; journals equal across XR64/XK/XK64 with `--routed`/`--partitioned` stripped
(XKP excluded from the journal compare: its compaction schedule differs by design; its snapshot bytes are compared).
`--codes dense` (16 draws on 96 positions: crosstalk common, ~15% of queries take the fallback) and `--codes block`
(each role on its own 40 positions) replace `bits_for`.

| run | sessions | calls | codes | K / snap | lib / pad | audit | diffs |
|---|---|---|---|---|---|---|---|
| p1 | 40 | 3,224 | real | 3/8 | mix / 0 | on | 0 |
| p2 | 40 | 3,392 | dense | 3/8 | mix / 0 | on | 0 |
| p3 | 30 | 2,508 | block | 64/64 | mix / 0 | on | 0 |
| p4 (append-only, 300 calls each; K-period fired 713×) | 12 | 3,804 | real | 64/1000 | 16 / 0 | off | 0 |
| p5 | 20 | 1,746 | real | 64/64 | mix / 0–1k | off | 0 |

Totals: 142 sessions, 14,674 calls, 58,696 deep checks, 80 crashes, 76 torn tails, 146 drops; 0 errors and 0 reply, state,
deep-index, snapshot-byte, journal or audit differences.
- **Against the 33565b0 tree** (x1, `--dump`): this tree's XK64 vs the 33565b0 checkout's XR64, 60 sessions, 4,874 calls,
  churn, lib mix: 0 per-call, snapshot or normalized-journal differences.
- **Real processes** (`serve_diff.py --crash` with `--indexed --incremental --routed --partitioned`): 30 sessions, 170 calls,
  28 kill −9 between calls and 30 in the middle of a call: 0 reply or final-byte differences.
- **Padding guard** (registered): r and k reply streams and final state bytes equal r0 (33565b0) at every (seed, N) — 105/105
  per-run files re-checked; partial rerun (§3) reproduced the same hashes.

**Power of the differential on the bound (L4).** Run on mutated copies (`mutant_diff.sh`): `g59_pair_dropped` and
`g59_small_part_dropped` are caught at call 0 by `ix_check`. But `g59_threshold_one_too_high`, `g59_hit_filter_strict` and
`g59_so_pairs_skipped` produce **0 differences** in 2,608 calls without the audit and in 3 × 1,983 calls with the audit on
(real, dense, block codes). Random sessions essentially never produce a triple at the bound's tight case. So the tight case
rests on the proof (above) and the single constructed g44 check. I added a direct property test
(`bound_property.py`: q, name code and three codes constructed so that p ⊕ q is a name code, with cancelling bits):
4.8 M samples, 839,804 eligible triples, 45 tight cases (second overlap = k), **0 violations** of (a) two overlaps ≥ k and
(b) an indexed pair of q inside each.

## 2. Counts, the five new mutations, the review-fingerprint exclusion

- g44 **191/191** (failed []), suite **11/11** modules (279 checks, 0 failed; smoke 10/10), G45 **18/18**, mutations
  **193/194**, 0 timeouts; the survivor is the documented equivalent `g57b_drop_keeps_scope`. Verdicts equal the builder's
  616d37e receipt except the five former survivors, now KILLED.
- **The five.** `g59_threshold_one_too_high` and `g59_hit_filter_strict` are killed by `g59_partition_bound_tight_case`:
  a constructed |p| = 42, |q| = 32, k = 7 triple with overlaps 16/7/6, checked behaviourally (the triple is a candidate and
  `ask` equals the non-partitioned engine's, which decodes X) — not a constant check. The three serve mutants
  (`g59_snapshot_check_skipped`, `g59_checked_flag_not_reset`, `g59_cache_check_not_in_validation`) are killed by
  `g59_periodic_checks_fire_in_serve` (a corrupted capability index caught by the call's full validation; a corrupted fact
  index caught at a proportional snapshot; close after a full-validation call still checks). Both tests are sound. Only
  `g44_test.py` changed between the full run and the re-run (diff 616d37e..80cda1a outside tests: mutation sites only).
- **Re-anchored sites** (`g57_memo_stamp_missed`, `g57b_no_small_packets`, `g57b_no_period_guard`,
  `g58_changed_stamps_ignored`): each still removes the same mechanism in the new code; all KILLED.
- **Review-fingerprint map excluded from `cache_check` (I1): the builder's position is sound.** `memo.rv` stores
  fingerprints only, and an entry may differ from the current fingerprint whenever its capability is due for a visit at the
  next review, so "rv equals a fresh build" is not an invariant. The checkable invariant ("every stale entry is in the next
  fast set", or "fingerprint-equal ⇒ evaluation not contradicted") costs a full review pass (O(L) evaluations), which is
  what the audit does in tests. My verify-33565b0 probe found `rvx` corruption self-healing (0/54). Fine as documented.

## 3. Reproduction from the registered files (instrument 70297af)

- `instrument_recompute.py`: all 64 primary, secondary and resource contrasts re-run on the registered CSVs; **64/64 first
  report lines identical**.
- `gate_recompute.py` (own code, from the raw .gz): A(Ck+maint‖Bk) comp −0.5179, comprep −0.7819, unrel −1.5003, mixed −0.8204,
  long −1.6324 (receipt identical); Q1 no, Q2 yes (0 wrong-qualified, 0 retention changes, C sealed-correct ≥ B everywhere:
  comp 1134 vs 1130, long 4536 vs 4468), Q3 no (lower −1.676 < −0.949), Q4a/b no → **HOLD**. Strata identical (comp
  −0.794 / −0.677 / −1.349 / −0.011 [−0.104, +0.068]; deepest-first holds; no stratum qualifies in any curriculum; C searched
  length 2 on every task at B-depth 5). Work/time: A_work(evals) +0.882 / ρ 12.85 (comp) … +0.912 / 29.79 (long), identity
  residual ≤ 4e−16. Rate ratio (long, 24 families): slope(y) +0.04497, s 0.0407, o 0.08568, **o/s 2.1049**, no crossover;
  comp/comprep 1.365/1.332, mixed 3.426, unrel s ≤ 0. Xk = Xr byte-identical in every role and seed.
- `scale_recompute.py` (own bootstrap, 105 per-run files): k α_task(16k→64k) **0.507 [0.397, 0.598]**, α_charged-prop
  **0.494**, α_work **0.082 [0.070, 0.096]**, α_charged-fixed 1.045; r 0.785 / 0.301; r0 (33565b0) **1.319 / work 1.246**;
  material: k ratio 2.02 vs r0 6.22. Local exponents of k rise: task 0.33 → 0.68, work 0.045 → 0.12.
- **Partial rerun** (12:35–12:42, guarded; another agent's jobs were loading the box): gate comp 301 and unrel 321, all 14
  arms: reply streams and final states byte-identical to the registered run, CPU within ±5%. Part S k, seeds 291/292 at 16k
  and 64k with **1 worker**: hashes identical; 16k task CPU 4.45 / 4.09 ms (registered 4.45 / 4.21), 64k **7.40 / 8.97 ms
  (registered 8.63 / 10.34)** — see L1. Work count for 292 at 64k: 139,682 vs registered 147,868 (see M2).

## 4. Timeline and provenance

- 80cda1a (pre-registration) committed 11:19:14 EST; lock 11:19:23–11:52:37 (`g59_lock.json`, scale_rc 0, gate_rc 0); part S
  11:19:23–11:40:10, gate 11:40:11–11:52:37; results commit 80cfb17 at 12:00:30.
- Both receipts: head 80cda1a, porcelain empty, source_unchanged true; my recompute at 80cda1a matches source ed6079c5…,
  engine 7ded3684…, harness (gate) ad021378…, harness (part S) 17e6b36d…; reference 33565b0 clean; instrument 70297af clean.
- G59.md §1–§11 are byte-identical between 80cda1a and 80cfb17 (the only removed line is "(appended after the run)"):
  thresholds (0.2 bound, Q1–Q4, −0.949 floor, strata rule) unchanged. No harness or engine change after registration.
- Not verifiable here: the push time of 80cda1a (the public events API does not list today's pushes); only
  commit-before-lock is shown (I5).

## 5. Fairness of the work metric and of the maintenance charges

**Work = `call` + `c_call` profile events in a forked copy.** Not vacuous: it separates the arms (r0 1.25, r 0.30, k 0.08)
and the fork does not disturb the timed run (the child exits before the window; same state). But see M2: it counts a
`dict.get` and a heavy call alike and counts a builtin over a growing container (`set.update(pairs[key])`) as one event, and
it depends on the hash seed of the process.

**Probe** (`work_probe.py`, k, seed 292, one process, profiler on process time): per 48 queries the pair-hit set grows
**956 → 3,824 (4.0× for 4× N)**, H stays 39, `small_part` 3 → 4; workload CPU (min of reps) 25.1 → 40.0 ms (α ≈ 0.34);
`recall_partitioned` 6.5 → 12.4 ms (≈ 40% of the growth); `_review_routed` +4 ms (the N/500 padding capabilities: an O(L)
term built into part S); profiled calls 105.7k → 116.5k, of which ~35k `dict.get` and other N-independent calls form W₀.
Seed 291 gave the same picture (995 → 3,943 hits).

**Maintenance.** Fixed charge (snapshot = full validation once per 64 journaled calls) is fair and gives α 1.04 (snapshot is
O(F)). The proportional charge (q = 1) is standard log compaction and its arithmetic is right (64k: period ≈ 50k calls,
+0.16 ms/task), but it omits the reopen replay cost (≤ q × snapshot bytes of journal) and the longer detection latency
(I3) — only favourable to k, and k fails the bound anyway. In the gate, "+maint" folds each family's correction,
transfer and retention probes and the closing snapshot into the family's last task, as in G58 (L3r used the same
definition, so Q3's floor is like-for-like) — but see L2 for how much of the negative A it carries.

## 6. Does the switch-rule conclusion follow?

The **trigger** follows: the rule was registered in G58 §8 / G59 §8 ("HOLD ⇒ evidence that the limit is the core
representation; next: an alternative mathematical approach"), and HOLD reproduces. The **interpretation** goes beyond the
data (M1):
- The one representational component G59 changed (recall over binary codes) is shown **not** to be the gate's bottleneck
  (Ck‖Cr comp −0.008 [−0.021, +0.005]).
- The deficit decomposes into: state-carrying without any library (P‖B comp −0.13, mixed −0.36, long −1.05, unrel −1.48),
  library use (C‖P comp −0.34, long −0.28), and maintenance accounting (task-only A: comp −0.41, unrel −0.30, long −1.29).
- ρ ("each evaluation costs 13–30× more") depends on the work unit: row_ops ρ 7.9–9.4, executions ρ 3.1–5.2 — a C evaluation
  composes library capabilities, so part of ρ is a bigger unit of work, not overhead per op.
- What drives the negative A — exhaustive enumeration over a primitive set that grows with the library, no utility filter
  (the classic explanation-based-learning utility problem), visited counts written into byte-exact state so that no exact
  mode may skip them, a Python implementation whose index design leaves a linear pair-hit term — all of these are
  properties of this engine's search policy, its exactness contract and its implementation. None of them is isolated from the
  sparse-binary representation by any G59 contrast.
- The "dense-bit codes whose per-op cost rises with N" part rests on the time/work gap, which M2 and L1 show is partly an
  uncounted linear term and partly co-scheduling.

A defensible wording: *"Switch rule triggered as registered. G59 shows this engine (its search policy, byte-exact state
contract and implementation) does not qualify positive amortization on these curricula; recall is not the bottleneck.
The evidence does not separate the representation from the search/utility layer; the alternative to evaluate should be
chosen with that in mind."* That is still a valid, solid negative result for the paper.

## Findings by severity

**High:** none.

**Medium (report-only)**

1. **M1. The switch-rule conclusion is stated as a finding; it is a registered assumption.** See §6. G59.md §12 ("this is
   evidence that the limitation is the core representation (byte-exact state …, on dense-bit codes …)"), the ledger and the
   roadmap map should say the rule was triggered and that G59 does not isolate representation from search policy,
   exactness contract and implementation. Not verdict-changing.
2. **M2. "Bounded in work" and "recall no longer scans unrelated codes" are overstated.** The work count is W₀ + c·N with a
   large N-independent W₀ (≈ 35k `dict.get` alone), so the 16k→64k exponent (0.08) is small by dilution while the marginal
   term is linear: local α_work rises 0.045 → 0.12, and the pair-hit set is linear in N (956 → 3,824). Under the instrument's
   Prop. 10 a linear term is what matters, whatever its constant. The metric also counts a builtin over a growing list as one
   event, and it is not deterministic across processes (hash seed: seed 292 at 64k 147,868 vs 139,682 in my rerun; the CI
   does not include this). G59's reading "time grows because each operation gets slower as the indexes grow (time/work ≈ 6)"
   is only partly supported: ≈ 40% of k's growth in my probe is work inside `recall_partitioned` (per hit), and part is the
   O(L) review of the N/500 padding capabilities. Suggest: report α_work as "small over 16k–64k, linear term present", and
   measure work as elements touched (or bytes) rather than call events. The statement relayed to James ("the algorithm now
   holds the cost of unrelated knowledge flat; what's left is code-running overhead") should be corrected the same way.

**Low**

1. **L1. Co-scheduling inflated the 64k timings.** Part S ran 4 workers with 64k jobs side by side (big heaps). Rerun of k
   with 1 worker: 64k 7.40 / 8.97 ms vs registered 8.63 / 10.34 (−14%), 16k unchanged → per-seed α_task 0.37 / 0.57 vs
   0.48 / 0.65. Also another agent's job (/workspace/nomad, 1,569 files written 11:30–11:50) shared the box during the
   registered run (the lock only binds PacketLM work; gate start load 5.87 with 4 workers). Per-seed 64k values show no clear
   step at 11:30. Direction: made k look worse by ≈ 0.1 in α; still far above 0.2. Suggest 1–2 workers for timing parts
   and recording box-wide load samples in the receipt.
2. **L2. Maintenance carries most of the unrelated penalty.** Retention probes grow linearly with the number of families
   (66, 132, … 1,512 rows per family on long) and the closing snapshot is charged to the last family: 48% of Ck+maint on
   unrel (task-only A −0.30 vs −1.50), 13% on long. Registered and like-for-like with G58's L3r, so Q3 stands as decided;
   but the "unrelated penalty" narrative should attribute it. Q1 and Q4 fail with or without maintenance.
3. **L3. Prediction scoring wording.** The ledger says every prediction held "except the part S point". The charged-prop
   point (0.36 [0.28, 0.43] → 0.49) and the work point (0.10 [0.098, 0.107] → 0.082) also fell outside their predicted
   intervals, and comp A was predicted ≈ −1.07 (observed −0.52). The direction and verdict predictions all held.
4. **L4. The bound's tight case is untestable by session differentials.** Three bound mutants give 0 differences in every
   differential I ran, with the audit on (§1). Exactness at the tight case rests on the proof and one constructed g44 check.
   Suggest adding a property test like `bound_property.py` (0 violations / 45 tight cases / 839,804 eligible) to g44.

**Info**

1. **I1.** The review-fingerprint exclusion from `cache_check` is sound (§2).
2. **I2.** k costs more than r on small states (part S N = 0: 2.70 vs 2.36 ms; unrel Ck‖Cr −0.148 [−0.194, −0.087]). Using
   r in the gate changes nothing (Cr+maint‖Br comp −0.524 [−0.616, −0.436]).
3. **I3.** The proportional charge omits replay at reopen (≤ q × snapshot of journal) and longer corruption-detection
   latency; favourable to k only; not bounded anyway.
4. **I4.** Censoring: only B is censored on comp/comprep/long, so the recorded A values are lower bounds (comp task-only
   interval [−0.406, 1], matched subset −0.414); no measured interval reaches above 0. Mixed and unrel are censored in
   both arms (sign undetermined by censoring), as reported.
5. **I5.** The prereg commit precedes the lock by 9 s; the push time could not be confirmed from public data.
6. **I6.** The comp A_n curve is positive for the first tasks (+0.29 at n = 3) and turns negative from n = 6 (trend
   −0.031 per task); savings concentrate at B-depth 5, where C always searches length 2.

## Tools and logs

`docs/verification/tools_80cfb17/`: `guard.sh`, `counts.sh`, `part_diff.py`, `run_adv.sh`, `mutant_diff.sh`,
`bound_property.py`, `serve_diff.py` + `lean_diff.py` (from verify-33565b0), `instrument_recompute.py`,
`gate_recompute.py`, `scale_recompute.py`, `work_probe.py`, `rerun.sh`; logs under `logs/` (counts, adv, mutdiff, probes,
recomputes, reruns). Working notes: `NOTES.md`.
