# Independent verification of g44-canonical-engine at 33565b0 (G58 `--routed`; registered at f1adcfb)

Verifier clone `/workspace/verify-33565b0`, branch `verify-33565b0`, made from 33565b0, plus a detached worktree of
8994490 (`/workspace/verify-33565b0-j0`) as the G57b reference. `/workspace/PacketLM` and the builder's worktrees were not
touched. Every CPU-heavy job ran through `tools_33565b0/guard.sh`, which waits while `/workspace/REGISTERED_RUN.lock` exists;
the lock was never present during my jobs. Times are EST (UTC−5). My work began at 09:54, after the registered run
(lock 09:48:41–09:52:00). `packetlm/` and `benchmarks/` are identical at f1adcfb and 33565b0.

## Verdict

No High findings. One **Medium (report-only)**: the stop rule's "material" verdict on the L = 64 form depends on leaving
validation overhead out, and G58.md's own report-only snapshot paragraph leaves out half of it (M1). The registered
decision itself (task-CPU form, registered before the run) reproduces exactly. `--routed` exactness held everywhere:
56.8k-call four-arm differential with crashes, torn journals, entity-set changes and capability churn; 13.9k calls
compared hash-by-hash against the 8994490 tree; kill −9 and fault-point runs; 0 differences, 0 audit violations. Every
count reproduced, the four removed "equivalent" mutants are equivalent, and dropping the hanging mutant is legitimate (it
is detected by non-termination). The Low 1 fix works: injected divergence in **any** G57b index structure is now detected
(300/300, previously 0/60 for by_sr, by_rel and candidates). There are three Low findings and several Info items.

## 1. `--routed` exactness

**Tool:** `tools_33565b0/routed_diff.py`, adapted from verify-8994490's `incr_diff.py` (independent of `g58_diff.py`).
Arms per session, in-process `serve.Server`s:
- **REF:** unindexed (every re-ask executed);
- **XJ64:** `--indexed --incremental`, K = 64 (the 8994490 configuration, this tree);
- **XR:** `+ --routed`, read-only check on, K from the run;
- **XR64:** `+ --routed`, registered configuration.

After every call: replies equal and `json.dumps(state)` byte-equal across all arms; with `--deep`, every persistent-index
structure of XJ64/XR/XR64 rebuilt from scratch and compared. At the end: snapshot bytes equal across all arms, journal bytes
equal across XJ64/XR/XR64 after removing `--routed` from each record's flags (the only allowed difference; journals record
flags). With `--audit`, `engine.G58_AUDIT` is on and any audit entry stops the run.

**Workload added for G58** (`churn`): `complete` at observed subjects; observations at unknown entities, then the entity made
known through an unrelated relation and later unknown again (every fact retracted); compositions `k<a><b>` over two
capabilities (dependency closures); requalify/revoke/learn/investigate, including on library capabilities;
contradicting, re-confirming or asking a library capability and retracting its middle facts; new facts on a library
capability's first relation plus a new composition on it; corrected examples; capabilities/show/why. Library padding of
0, 4, 16 or 64 unrelated capabilities (the `g58_libscale` construction), fact padding (0 or 1k), crashes between calls
(journal replay), torn journal tails, memo drops, append-only streams (the K-period fires).

| run | sessions | calls | K / snap | lib | audit | diffs |
|---|---|---|---|---|---|---|
| r101 | 150 | 12,654 | 3/8 | mix | on | 0 |
| r102 | 150 | 13,746 | 64/64 | mix | off | 0 |
| r103 | 40 | 5,310 | 64/200 | 64 | off | 0 |
| r401 (append-only, 400 calls each; the K-period fired 324 times) | 40 | 16,680 | 64/1000 | 16 | off | 0 |
| r402 (fact padding 0 or 1k) | 100 | 8,441 | 64/64 | mix | off | 0 |

Totals: 480 sessions, 56,831 calls (16,044 read-only), 170k deep index checks, 308 crashes, 303 torn tails and 456 drops. There were 0 errors and 0 reply, state, deep-index, snapshot-byte, journal or audit differences (`totals.py`).

**Against the 8994490 tree** (same generator, `--dump`): this tree's XR64 vs the 8994490 checkout's `--indexed --incremental`,
per-call hashes of replies and state, final snapshot hash and normalized journal hash.
- x201: 120 sessions, 10,591 calls, churn, lib mix: 0 per-call, snapshot or journal differences.
- x202: 40 sessions, 3,260 calls, churn, lib 16, fact padding mix: 0 differences.

**Real processes:** `serve_diff.py --crash` (subprocess serve with `--indexed --incremental --routed`, reference = per-process
engine): 60 sessions, 400 calls, 83 kill −9 between calls and 82 in the middle of a call: 0 reply or final-byte
differences. `serve_faults.py`: 20 sessions, 548 runs, 447 crash points at fsync/replace/link: 0 differences.

**Builder's checks re-run** (inside the mutant runs, unmutated paths identical): `g58_diff` 72 sessions / 1,487 calls and
`contract_fuzz` 84 sessions / 1,524 reviews / 594 forced status transitions: ok, 0 audit violations.

**Code reading.** The review fingerprint covers what `evaluate` reads (version, closure statuses, expanded base and the
stamps of its relations, per-observation subject/value/known/closed). Candidate sets are supersets: observation writes
(`observe`, and `correct_example` through `observe`), stamps, `rv_dirty` with the dependency maps, closed-set and entity-set
deltas, new names; a status change mid-pass falls back to visiting every later capability and invalidates `rvx`.
`_flush_growth_routed` takes candidates in name order and re-derives them after each re-acquisition, as the full loop does.

## 2. Counts and the mutation set

- g44: **174/174**, failed [].
- Suite: **262/262**, 11/11 modules (smoke 10/10).
- G45: **18/18**.
- Mutations: **169/170**, 0 crash kills, every verdict equal to `docs/evidence/g58/mutations_receipt.json`. The only survivor is
  `g57b_drop_keeps_scope` (equivalent, verify-8994490 §2).

**The four mutants removed as equivalent** (`tools_33565b0/mutant_check.sh`: apply in a /tmp copy, run g44, the builder's
`g58_diff` + `contract_fuzz`, and my `routed_diff` with the audit, 60 sessions):
- `g58_new_version_lib_gen_kept` (no `lib_gen` bump on a new version): g44 passes, g58_diff/contract_fuzz ok, routed_diff
  5,093 calls 0 diffs, 0 audit violations. The argument holds: every cache keyed by `lib_gen` also keys on the primitive
  list, whose entries carry the version (`cap:n@v`), and the capability index is synced through `cx_dirty`. (`_lib_key`, the
  only key without the list, is now dead code; Info 3.)
- `g58_sx_domain_not_dirty`: g44 passes, g58_diff/contract_fuzz ok, routed_diff 5,093 calls 0 diffs, 0 audit violations. The argument holds by code reading: `_requalify` is reached only from
  `_requalify_retired` inside `retract`/`correct`, after `_retire` set `memo.sx = None`, and `_sx()` is called only by
  `_flush_growth_routed`, which cannot run in between.
- `g58_correction_not_recorded` and `g58_fp_kept_on_contradiction` are not mutants of the registered code but lines the
  builder removed (ff673fb). The current code is the "mutant"; its exactness is what §1 tests (0 diffs, audit on, including
  corrected examples and suspensions). `correct_example` always ends in `observe`, which records `rv_obs`, `sx_dirty` and the
  scope; a fingerprint kept after a contradiction belongs to a non-contradicted evaluation of the same inputs.

**The dropped infinite-loop mutant.** I reconstructed the likely mutant (`_flush_growth_routed` without `last = hit_at`):
g44 does not terminate (killed by my 400 s timeout). Under standard practice a non-terminating mutant counts as killed; dropping
it removes one kill from numerator and denominator (169/170 instead of 170/171), so it does not flatter the score. It is
legitimate, but the runner should record it rather than drop it (Info 4).

## 3. Low 1 fix: re-injected corruption (`corrupt_probe.py`, 60 sessions, K = 64)

Same probe as verify-8994490, now on XJ (this tree, `--incremental`) and XR (`--routed`), sessions with churn.

| | index kinds (by_sr, told_rel, small+codebits, ref, by_rel) | detected at a call | at close | never | wrong replies before detection | reopen failed | wrong state persisted undetected |
|---|---|---|---|---|---|---|---|
| verify-8994490 (K=64) | 5 × 60 | — | — | by_sr, by_rel, candidates: 60/60 each | 2–11/60 per kind | — | ref 10/60, by_sr 3/60, by_rel 7/60 |
| **XJ, 33565b0** | 300 | 285 | 15 | **0** | 14 | 7 | **0** |
| **XR, 33565b0** | 300 | 285 | 15 | **0** | 17 | 9 | **0** |

So `ix_check` now covers every G57b structure and the check before a removal stops the rebuild from healing a divergence:
the Low 1 fix is effective. What remains is Low 2 of verify-8994490 (detection is deferred past kept calls, so up to K − 1
mutating and any number of read-only calls can be served from a divergent index, and a reopen can then fail with `journal
replay diverged`): documented, fails closed. State corruptions behave as before on both engines.

**New: the G58 memo structures have no runtime guard** (Low 1 below). Injected into XR's memo:
- the offered list of the capability index (`cx.order`) with one capability dropped: 33/59 sessions persisted a different final
  state with no detection (different `pruned` counts in `hypotheses`, a different `basis` in a version's evidence: the dropped
  capability silently left the search space);
- the seeds index (`sx.by_ent`) cleared: 1/52 persisted a different state undetected;
- `rvx` relation or subject maps cleared: 0/54 differences (healed by full review passes).

Also: `S7` (a capability's `current` pointer corrupted) was caught at the next call on XJ (latency 1) but only after up to 6
mutating and 21 read-only calls on XR, because `--routed` scopes capability validation to the capabilities a call wrote
(serve.py `_valid_scoped(..., caps, obs)`). Still caught at the period, a removal or the snapshot (Info 5).

## 4. Library-scaling stop rule, L1r/L2r/L3r/Mr

**From the registered files** (`libscale_recompute.py`, independent bootstrap, 84 per-run files):

| arm | L=0 | 64 | 256 | 1024 (ms) | R64_1024 | R0_1024 |
|---|---|---|---|---|---|---|
| j0 (8994490) | 3.02 | 9.49 | 28.3 | 136.2 | 14.74 [13.01, 15.89] | 45.15 [44.52, 45.85] |
| j | 2.69 | 8.89 | 29.9 | 137.2 | 15.45 [14.75, 16.29] | 51.14 [48.75, 54.04] |
| **r** | 2.41 | 3.57 | 3.54 | 6.30 | **1.99 [1.55, 2.31]** | **2.62 [2.39, 2.85]** |

Thresholds 7.37 and 22.58: material on both forms; flat no (2.31 > 1.25). All guards true (replies and state of j and r equal
j0's at every seed and L, answered counts constant, no snapshot in the window, j0 a clean 8994490). Everything equals the
receipt exactly.

**Instrument 70297af** (clean, 5000 resamples) on the registered CSVs: **18/18** primary and secondary contrasts match the
receipt exactly, e.g. L1r −0.7444 [−0.8641, −0.6283], L2r −0.4830 [−0.5819, −0.3936], Mr comp +0.0103 [−0.0005, +0.0226]
(not claimed, correct), L3r −1.8979 [−2.0895, −1.7254], Mr unrel +0.0939 [+0.0709, +0.1168] (claimed, correct). Both CSVs
regenerate byte-identically from `*_raw.json.gz`; every Xr/Xj pair has identical reply and state hashes; 0 wrong-qualified.

**Re-runs** (lock absent, 10:14–10:19):
- Library scaling, seeds 261 and 264, all L and arms (`G58_REF_ROOT` = my 8994490 worktree): all 24 runs hash-identical to the
  registered ones; guards true; r R64_1024 2.42 [2.03, 2.81] vs j0 18.98: material, not flat. The decision reproduces.
- L1/L3 on comp 271 and 275 and unrel 281 and 286: 28 arm runs hash-identical; CPU 0.98–1.24× the registered.
- Because L1/L3 is cheap (about 100 s), also the full registered seed set (7 + 7): 98 runs hash-identical, all guards true.

| contrast | registered | full re-run |
|---|---|---|
| L1r comp | −0.744 [−0.864, −0.628] | −0.763 [−0.891, −0.651] |
| L2r comp | −0.483 [−0.582, −0.394] | −0.499 [−0.572, −0.430] |
| Mr comp | +0.010 [−0.001, +0.023] (not claimed) | +0.034 [+0.010, +0.059] |
| L3r unrel | −1.898 [−2.090, −1.725] | −1.908 [−2.175, −1.700] |
| L2r unrel | +0.007 [−0.024, +0.038] | −0.017 [−0.060, +0.018] |
| Mr unrel | +0.094 [+0.071, +0.117] (claimed) | +0.059 [+0.010, +0.102] |

No-claim decisions on L1r/L2r/L3r reproduce. Mr unrel stays positive but its size is timing-sensitive (+0.024 on the 2-seed
re-run vs +0.098 registered on the same seeds). Mr comp would cross into "claimed" on my re-run: the registered "not claimed" is
the conservative side of a borderline effect (Info 6).

## 5. Timeline and receipts

| commit | time | what |
|---|---|---|
| e3cbec6 | 09:07:46 | capability and seeds index; dev Part L r ≈ 2.0 vs j ≈ 12.4 |
| 2520395 | 09:10:33 | Low 1 fix folded in |
| bb62256 | 09:12:36 | harnesses |
| 2b6405e | 09:13:55 | pre-registration draft: stop rule and flatness threshold |
| f1adcfb | 09:48:32 | pre-registration final (tests at registration) |
| — | 09:48:41–09:52:00 | lock (`g58_lock.json`); libscale 09:48:41–09:51:05, L1/L3 09:51:05–09:52:00 |
| 33565b0 | 09:53:07 | results |

- G58.md §§1–11 are unchanged from the draft except additions (the only removed line is a placeholder); f1adcfb→33565b0 only
  appends §12 and evidence. The stop rule and flatness text are identical at 2b6405e, f1adcfb and 33565b0.
- Code between draft and final: only the unused `_offered` helper removed (and tests/mutations). Registered source hash
  `ac136654…` and engine hash `4564cc06…` equal my recomputation at 33565b0; both harness hashes equal the files.
- Both receipts: head f1adcfb, clean porcelain at start and end, lock text present at start and end naming f1adcfb, source
  unchanged, instrument 70297af pinned and clean.
- Load 0.62 at the start of the run; the library-scaling harness itself runs `Pool(8)` on 8 cores and L1/L3 starts at load 6.3
  from it (Info 7).
- The commit times are local; I could not confirm push times (the GitHub events feed did not list these pushes).

## 6. Snapshot cost and charging the stop rule with it (report-only)

**The claim holds** (`snap_profile.py`, seed 261, L = 1024, 6,204 facts, 1,034 capabilities): snapshot j0 67 ms, j 300 ms,
r 312 ms. With `Memo.ix_check` stubbed: j0 60, j 57, r 54 ms. ix_check + fresh build: j0 13.5 ms, j 249 ms, r 251 ms. The
increase is the extended O(F) check (each check recomputes `geom.bits` for every code; 12,458 calls).

**But the period still runs it twice** (`period_dup.py`): with the registered defaults (snapshot every 64, K = 64), every 64th
call does a full validation in `_validate` *and* the snapshot's `ix_check` (2 ix_checks per period call, observed at calls 62,
126, 190). This is Low 3 of verify-8994490, stated in G57b.md but not fixed, and the extended check makes it about 17× more
expensive. Measured directly on the libscale states (`dup_measure.py`, all 7 seeds): the duplicate costs j0 1.0 / 16.5 ms
and r 18.6 / 285 ms at L = 64 / 1024.

Stop rule with these charged at 1/64 per journaled call (each arm its own costs):

| form | r R64_1024 | j0 R64_1024 | material (L64) | r R0_1024 | material (L0) |
|---|---|---|---|---|---|
| registered (task CPU) | 1.99 [1.55, 2.31] | 14.74 | yes (≤ 7.37) | 2.62 [2.39, 2.85] | yes |
| + snapshot (G58.md's report-only form) | 5.48 [4.46, 6.19] | 14.64 | yes (≤ 7.32) | 9.75 [9.07, 10.38] | yes |
| + snapshot + duplicate period validation | **7.48 [6.12, 8.39]** | 14.65 | **no** (> 7.33) | 16.44 [15.47, 17.39] | yes |

Should it have been charged this way? The registered form (task CPU, snapshot outside the window) was registered before the
run, applied equally to j0, and is a legitimate pre-registered choice, so the registered verdict stands. But under the
paper's own equal-charging lesson the honest reading is that "material vs L = 64" holds only when per-snapshot validation is
excluded; in absolute terms r is still about 3.2× cheaper than j0 per task at L = 1024 with everything charged (about 44 vs 142 ms).
Most of r's extra overhead is the guard verify-8994490 asked for, which j0 does not have.

## Findings by severity

**High:** none.

**Medium (report-only)**

1. **The "material" verdict on the L = 64 form is not robust to charging validation overhead, and G58.md's report-only
   statement is incomplete.**
   - G58.md §12 says that with snapshots charged, r's amortized R64_1024 is 5.48, "still below half of j0's (7.3)". That form
     leaves out the duplicate full validation in the same period call (Low 3 of verify-8994490, still present; 285 ms at
     L = 1024).
   - Charged too, r's R64_1024 becomes 7.48 [6.12, 8.39], above the 7.33 threshold. The R0 form stays material.
   - No registered decision changes: the rule was registered on task CPU. Suggest:
     - correct the §12 paragraph;
     - fix Low 3 (skip the `_validate` full pass when the same call snapshots, or skip the snapshot's `ix_check` right after a
       full validation);
     - make `ix_check` cheaper (cache each code's bits), or register G59's cost with snapshots and validation charged.

**Low**

1. **The G58 memo structures are unguarded at run time.** `ix_check` covers the fact index only. The capability index (`cx`),
   seeds index (`sx`), review maps (`rvx`) and fingerprints (`rv`) are checked only by `G58_AUDIT`, which is off in production
   and registered runs. With one capability injected out of the offered list, 33/59 sessions persisted a different final
   state with no detection (the capability silently left the search space; `pruned` and `basis` differ). No organic
   divergence was found (§1: 0 diffs with the audit on). Suggest a periodic cheap check, at the K-period or snapshot, comparing
   `cx`'s offered list and `sx` against fresh builds (both O(L), small next to the O(F) check).
2. **The mutation runner cannot record a hang.** `subprocess.run(..., timeout=600)` raises `TimeoutExpired` inside a worker,
   which aborts the whole parallel run. So the growth-routing mutant that hangs had to be dropped rather than counted
   KILLED (timeout). Catch the timeout and record it.
3. **Library-scaling timing noise at the L = 64 baseline.** Seed 261's L = 64 runs are outliers in both arms (j0 13.9 vs
   about 8.8 ms; r 7.63 vs about 2.9 ms), giving r a per-seed R64_1024 of 0.82 and j0 9.92. Without that seed: r about 2.18,
   j0 about 15.5. The decision is unchanged (wide margin). But at about 3 ms per task with `Pool(8)` on 8 cores (j0
   subprocesses alongside), the R64 point estimate is noise-sensitive. Suggest more tasks per run or fewer parallel workers in
   G59.

**Info**

1. Exactness: 0 differences in every configuration (§1), including against the 8994490 tree itself.
2. The Low 1 fix of verify-8994490 is effective (§3).
3. `Engine._lib_key` is dead code after the capability index (no callers).
4. The dropped infinite-loop mutant is legitimate to drop (it is detected by non-termination). It should be counted as
   killed by timeout (Low 2).
5. `--routed` scopes capability and observation validation to what a call wrote. A corrupted record of an untouched
   capability is now caught at the period, a removal or the snapshot, not at the next call (XR: up to 6 mutating and 21
   read-only calls). This is the same documented scope as G57b's facts. G58.md mentions the scoped validation only in the
   8b2fa0e commit message, so it is worth a sentence in §2.
6. Mr is timing-sensitive. Mr unrel stays claimed on the full re-run (+0.059 [+0.010, +0.102]). Mr comp is borderline
   (registered +0.010 [−0.0005, +0.023] not claimed; re-run +0.034 [+0.010, +0.059]). Br‖Bj unrel −0.019 [−0.038, −0.003]
   registered (routing costs fresh small states a little) reads −0.007 [−0.042, +0.025] on the re-run, so it is noise-level.
7. The library-scaling harness runs 8 processes on 8 cores. CPU time is per process, but contention affects it (see Low 3).
8. G58.md §12 "No prediction failed" is accurate. The flatness threshold (1.25) was set after the dev result (r ≈ 2.0), but
   at a level the dev result already failed, so it cannot have helped the outcome. The "halve" stop rule was set by the
   orchestrator before the G58 dev numbers.

## Files

`tools_33565b0/`:
- `routed_diff.py` (four-arm differential, churn, library padding, audit, cross-tree dump), `corrupt_probe.py` (index,
  state and G58 memo corruptions), `mutant_check.sh`, `totals.py`;
- `libscale_recompute.py`, `instrument_recompute.py`, `snap_profile.py`, `period_dup.py`, `dup_measure.py`, `amort_snap.py`;
- reused from verify-8994490 / d6cbcf3: `serve_diff.py`, `serve_faults.py`, `lean_diff.py`, `guard.sh`.

`logs/`:
- the g44, suite, G45 and mutation logs;
- `adv/` (differential, cross-tree dumps `x20*.json.gz`, corruption, serve and fault runs);
- `mutchk/`, `reruns/` (libscale 2 seeds; L1/L3 2+2 and `full/` 7+7: receipts and CSVs);
- `libscale_recompute.log`, `instrument_registered.log`, `snap_profile_*.log`, `period_dup.log`, `dup_measure.jsonl`,
  `amort_snap.log`, `amort_dup_direct.log`.
