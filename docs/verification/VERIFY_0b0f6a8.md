# Independent verification of PacketLM @ 0b0f6a8

- **Verifier:** an independent Grok Bot verifier. It did not write any of this code.
- **Date:** 2026-11-26, about 22:20–22:35 America/New_York.
- **Target:** `jacksonjp0311-gif/PacketLM`, branch `g44-canonical-engine`, commit
  `0b0f6a8932828361fffa8db2c5fd6fd0264f4875`. This was the branch head and the PR #1 head at
  the time of checking.
- **Instrument:** `jacksonjp0311-gif/learning-amortization` @ `70297af`, cloned fresh.
  `diff -rq` against the builder's `/workspace/vendor/learning-amortization` showed the two
  are identical. The vendor copy has a clean `git status` and no diff from 70297af.
- **Environment:** a fresh clone at `/workspace/pl-verify`, Python 3.13.5, 8 cores.
  `GITHUB_TOKEN` and `GH_TOKEN` were unset for every git/gh call.
- **Scope:** I read docs/RESEARCH_LEDGER.md, G44.md, G45.md, G46.md, G46U.md, G46_V3.md,
  G46_V4.md, ARET.md, LA_EXPORT.md and the PR #1 description. I also read
  `benchmarks/{aret,g46,la_export}.py`, `packetlm/{suite,mutations,teach}.py` and the
  relevant parts of `engine.py`.

## Verdict

The headline numbers **reproduce**. Every test count matches exactly, the ARET decisions are
bit-identical, and the ARET cost results land within run-to-run noise. The pinned instrument
is used unmodified, and recomputing from the committed CSVs gives the committed report exactly.
No sealed-item leakage turned up, and no pre-registered threshold was edited after its results.

The **framing of the headline `A_36(A‖B) = +0.249`** needs tightening. This positive A against
an empty-state learner is real under the declared rule, but it is fragile:
1. It disappears to about +0.02/+0.03 once maintenance is charged. Its CI touches 0 in the
   committed run.
2. It comes mostly from tasks where B *failed* the accuracy target. On tasks both arms solved,
   it is about −0.04.
3. It is described as "at matched accuracy", which it is not.
4. Its "95% CI" comes from bootstrapping over only 3 seeds.

## Reproduced vs claimed

### Tests (each in a fresh process)

| command | claimed | reproduced |
|---|---|---|
| `python3 -m packetlm.suite` | 164/164 checks, 11/11 modules | **164 checks, 0 failed, 11/11 modules**; smoke 10/10 ran |
| `python3 -m packetlm.g44_test` | 77/77 | **count 77, failed []** |
| `python3 -m packetlm.g45_test` | 18/18 | **count 18, failed []** |
| `python3 -m packetlm.mutations` | 33/33 killed, 4 only by crash | **33/33 killed.** 4 by crash with no check failing: `no_backup_fallback` (StateError), `library_off` (KeyError 'great'), `activation_overprunes` (TypeError), `compose_keeps_source` (KeyError 'x1') |

Note: suite's 164 *includes* g44's 77 and G45's 18. They are not additional checks.

### ARET (all three seeds, both curricula; `python3 benchmarks/aret.py`, about 2 min wall)

- **Engine sha:** `205d0829533f…` at start and end (`unchanged: true`). This matches the
  registration. No `packetlm/*.py` file changed between the pre-registration (813697c) and
  0b0f6a8.
- **H-R1 no harm:** reproduced **PASS**. Across 6 curriculum×seed cells, I checked the
  `no_harm_tasks`, `no_harm_families`, 0 wrong-qualified and no aborts.
  - I also ran a stricter check than the harness. The harness compares only the normalized
    answer, so I compared the **full reply text plus capability status and sequence** between
    A and C.
  - Result: 0 differences over 486 (G46) and 288 (G46-U) sealed replies, in both the committed
    raw data and my rerun.
- **Deterministic quantities identical to committed:**
  - acquired counts: G46 36/36/35 (A, C) and 32/32/31 (B); G46-U 24/24/24;
  - sealed-correct counts;
  - archive bytes (383102 / 387050 / 378145 on G46; about 542 KB in 23 files on G46-U);
  - archive file counts;
  - hot bytes per task. `g46_bytes.csv` and `g46u_bytes.csv` re-export **byte-identical**.

**Instrument contrasts** (`python -m amortization <csv> --cont X --base Y --bootstrap 5000`, instrument @70297af):

| contrast | claimed | recomputed from committed CSV | **my fresh rerun** |
|---|---|---|---|
| G46 `A(A‖C)` | +0.484 [+0.481, +0.490], BE 8 | +0.4841 [+0.4806, +0.4903] | **+0.4919 [+0.4757, +0.5187]**, BE 8 |
| G46 `A(A+maint‖C+maint)` | +0.452 | +0.4516 | **+0.4547** |
| G46 `A(A‖B)` | +0.249 [+0.208, +0.295], BE 24 | +0.2485 [+0.2083, +0.2948] | **+0.2395 [+0.2294, +0.2520]**, BE 24 |
| G46 `A(C‖B)` | −0.457 | −0.4565 | **−0.4967** |
| G46-U `A(A‖C)` | +0.394 [+0.369, +0.439] | +0.3937 [+0.3693, +0.4387] | **+0.3849 [+0.3633, +0.4053]** |
| G46-U `A(A+maint‖C+maint)` | +0.276 | +0.2762 | **+0.2535** |
| G46-U `A(A‖B)` | −5.74 | −5.7406 | **−5.5215** |
| G46-U `A(C‖B)` | −10.12 | −10.1176 | **−9.6021** |
| *not reported:* G46 `A(A+maint‖B)` | — | **+0.0313 [−0.0053, +0.0707]**, BE 30 | **+0.0178 [+0.0061, +0.0251]**, BE 36 |
| *not reported:* G46-U `A(A+maint‖B)` | — | −25.79 | −24.89 |

- **H-R2** (G46-U lower bound > 0) and **H-R3** (G46 lower bound > −0.05) both reproduce
  PASS on my rerun, with lower bounds of +0.363 and +0.476.
- **Raw task CPU** in my rerun was 5–20% higher than committed in every arm. g45_test was
  running alongside it, under the harness's own Pool(6). The ratios hold up.
- **Exporter:** `benchmarks/la_export.py` on the committed raw data reproduces
  `g46_costs.csv` and `g46u_costs.csv` **byte-identical**. Running the instrument on those
  CSVs reproduces `la_report.txt` exactly.
- **v4 numbers** (recomputed from the committed v4 CSVs): `A_36(C‖B)` −0.4476 (claimed −0.448),
  `A^reuse(C‖P)` +0.2800 (claimed +0.280), G46-U `A_24(C‖B)` −9.784 (claimed −9.78).

## Findings by severity

### High: none

I found no fabricated or non-reproducible number, no leakage, and no post-hoc threshold edit.

### Medium

**M1. `A_36(A‖B)` = +0.249 does not survive charging maintenance, and that contrast isn't reported.**
- The ARET, ledger and PR report `A+maint` only against C. They do not report it against B.
- With the family-end correction, transfer and retention calls charged to A:
  - committed data: `A(A+maint‖B)` = **+0.031 [−0.005, +0.071]**, sign-flip p = 0.5;
  - my rerun: +0.018.
- docs/LA_EXPORT.md declared "`C+maint` vs `B`: conservative" as a standard report, and the
  ledger's 20:45 pre-registration says C "counts everything the learner does … maintenance".
- Those calls are partly measurement probes that B never makes, so excluding them from the
  primary metric is defensible and was declared. But the restore and re-archive work forced by
  the family-end probes lands *in* maintenance. That means the excluded bucket holds part of
  the adaptive mechanism's own cost.
- **Fix:** report `A(A+maint‖B)` next to +0.249. State that once maintenance is charged, A is
  roughly break-even with B.

**M2. The positive `A(A‖B)` comes from B's censored (failed) tasks. "At matched accuracy" is inaccurate.**
- B fails the accuracy target on 11 of 108 task instances. These are mostly `cdabc`
  (length-5) and some `efab`/`abc` tasks that end `ambiguous`.
- On those tasks B spends its full investigation budget: 1.28 / 2.01 / 1.82 s of its
  4.80 / 4.62 / 4.70 s totals.
- Restricted to tasks *both* A and B solved, A against B is +0.096 / −0.203 / −0.002, a mean
  of **−0.036**. My rerun gives a mean of −0.046. This is my own descriptive sensitivity
  check, not the registered metric.
- The instrument's rule that B censored makes A a lower bound is applied correctly. But it
  rests on the untested assumption that B would cost more if it had to succeed.
- The ARET "Reading" and the PR say A costs less "at matched accuracy". The pre-registered
  definition in the ledger at 20:45 actually says A_n is *not comparable* when accuracies differ.
  LA_EXPORT (21:25, before results) switched to the instrument's censoring rule.
- **Fix:** replace "at matched accuracy" with "with censoring (B misses the target on 11/108
  tasks)". Report the jointly-uncensored figure.

**M3. "95% CI" over S = 3 seeds.**
- Every instrument line reports `sign-flip p=0.25`, the smallest p achievable with 3 seeds.
  A paired bootstrap over 3 units has only 10 distinct resamples, so the "95% CI" is
  essentially the range of the seeds.
- So H-R2 and H-R3 really amount to "all 3 seeds exceed the bar".
- My rerun's point estimates moved by up to 0.04 on G46 and 0.5 on G46-U. Two of them fall
  outside the committed intervals:
  - G46 `A(A‖C)`: +0.4919 against [+0.4806, +0.4903];
  - G46-U `A(C‖B)`: −9.60 against [−10.65, −9.62].
  The intervals don't capture run-to-run timing noise.
- **Fix:** label these intervals as seed bootstrap with S = 3, cite p = 0.25, and avoid
  "significant"-style readings. More seeds, or repeated timings per seed, would make them
  meaningful.

**M4. Per-process interpreter and import CPU is left out of every cost log.**
- `engine.main` starts `process_time()` *after* Python startup and module import. I measured
  about **0.033 s per process** unreported, against a median reported `cpu_s` of 0.0007 s for
  a tiny call.
- Each arm runs about 178 task processes on G46, so roughly 5.8 s of unreported CPU per arm.
  That is more than the reported task total.
- I added 0.0328 s × processes to every call and reran the unmodified instrument:
  - G46 `A(A‖C)` +0.484 → **+0.257**;
  - G46 `A(A‖B)` +0.249 → **+0.112**;
  - G46 `A(A+maint‖B)` → **−0.056**;
  - G46-U `A(A‖B)` −5.74 → **−0.52**;
  - G46-U `A(C‖B)` −10.1 → −0.91.
- The signs of the primary contrasts hold, but magnitudes depend heavily on this boundary.
  The PR line "Unrelated knowledge still costs about 6–10× an empty state per task" is
  specific to it. With process cost included, the figure is about 1.5–1.9×.
- This boundary is a harness design choice (one process per call) and is arguably not a
  learner cost. It should be stated wherever magnitudes are quoted.

### Low

- **L1. ARET development history isn't public.**
  - The mechanism commit b69793a (22:10:35) and the pre-registration 813697c (22:11:09) are
    34 s apart. ops-dev isn't on the remote, and no commit records the dev-seed-999 runs or
    the GUARD 2→1 change.
  - The claim that registered seeds were never used for tuning **cannot be verified** from
    the repo. Nothing contradicts it, and the decisions are seed-independent by construction.
  - The run time is consistent with the timeline: the full ARET took about 2 min for me, and
    there are 9 min between the pre-registration and results commits.
- **L2. G45 threshold 7b is weaker than its wording.** The doc says `--no-library` "fails to
  acquire D5". The code passes when D5 is acquired as `provisional`. The actual outcome
  (status `none`, not acquired, on all 3 seeds) satisfies the strict reading, so the result
  stands.
- **L3. The sealed-token guard only covers G46 worlds.** `benchmarks/sealed_tokens.json` holds
  the 243 G46 sealed tokens for seeds 11/22/33. It holds none of the 672 G46-U sealed tokens,
  so `teach.py` wouldn't refuse G46-U sealed tokens. I checked everything under `data/`
  against all G46 and G46-U sealed tokens for seeds 11/22/33: **0 occurrences.** I also
  checked that no task example subject is a sealed subject (0 in all worlds), and that
  investigate answers about sealed subjects are refused by the harness (`g46.py` line 255).
- **L4. Small documentation drift.**
  - ARET.md says the g44 retention differential has "17 and 13" archives and restores. The
    receipt at 0b0f6a8 shows 18 and 14 over 111 calls, with no diffs.
  - The ledger's 20:55 reproduce block still says "g44 57 checks / 15 mutations". It is
    historical, but it is the only reproduce block in the ledger.
- **L5. Smoke modules' negative self-reports are invisible in the suite.** Smoke only requires
  exit 0. Their own receipts report False claims that the suite never surfaces: `learn.any_kept`,
  `gaptest.any_new_capability`, `demo.multi_step` and `consistent`, `feedoffer.offered` and
  `gate_kept`, `memory.path_changed`, `nexttoken.*_improved`, `crossdomain.kept`. These are
  legacy demos and aren't claimed as results, but "smoke 10/10" shouldn't be read as them working.

### Info and checks that passed

- **Thresholds versus git history:**
  - ARET.md: the pre-registration text (813697c) is byte-identical in 0b0f6a8. Only a Results
    section was appended.
  - G46.md: there were edits after 283f526, namely the clarifications at 9c5315f and
    Amendment 1 at 7d2eea1 (21:21). Both came before the results commit 3267eb9 (21:35) and
    changed no threshold. Amendment 1 only adds resumability and a budget for arm N, which has
    no threshold, and it is disclosed.
  - G45.md: one wording addition (`unanswered` command) came before the run. Code thresholds
    t1–t7 match the doc.
- **Harness code** (`aret.py`, `g46.py`, `g46u.py`, `la_export.py`) wasn't changed after the
  respective pre-registrations. Note that `source_hash()` covers only `packetlm/*.py`, not
  `benchmarks/`, so harness freezing relies on git history.
- **Pinned instrument:** used unmodified, from outside the repo via `PYTHONPATH`. Identical to
  a fresh clone at 70297af.
- **Mutation kills look non-vacuous:** 29 of 33 fail at least one named check, and the 4
  crash-kills are disclosed.
- **Positive mechanism evidence:** adaptive retention changes no answer, status or sequence,
  and A against C is a large, reproducible saving on both curricula under every cost boundary
  I tried (+0.21 to +0.49).

## Are the claims proportional?

- **Proportional:**
  - G46 "NOT passed (26/27)";
  - "utility problem reduced, not solved";
  - "control structures designed, not acquired";
  - the H-R1/H-R2/H-R3 PASS statements;
  - the disclosure that gate constants came from one dev seed;
  - "B is censored, so this is a lower bound".
- **Overstated:** the bold "first positive A against an empty-state learner" in the PR and
  ledger. It should carry, in the same sentence: (a) task costs only, and +0.02–0.03 with
  maintenance (M1); (b) B misses the target on 11/108 tasks and the jointly-solved tasks are
  about break-even (M2); (c) S = 3 (M3); (d) process startup excluded (M4). "At matched
  accuracy" in ARET.md's Reading should be removed.

## Exact commands

```bash
cd /workspace && env -u GITHUB_TOKEN -u GH_TOKEN git clone https://github.com/jacksonjp0311-gif/PacketLM pl-verify
cd pl-verify && git checkout 0b0f6a8
python3 -m packetlm.suite        > suite.log
python3 -m packetlm.g44_test     > g44.log
python3 -m packetlm.g45_test     > g45.log
python3 -m packetlm.mutations    > mut.log
python3 benchmarks/aret.py       > aret.log          # all seeds 11,22,33, both curricula

# instrument
cd /workspace && env -u GITHUB_TOKEN -u GH_TOKEN git clone https://github.com/jacksonjp0311-gif/learning-amortization la-verify
cd la-verify && git checkout 70297af
diff -rq --exclude=.git --exclude=__pycache__ /workspace/la-verify /workspace/vendor/learning-amortization   # identical

# committed evidence -> CSV -> instrument
gunzip -k docs/evidence/aret/g46_raw.json.gz docs/evidence/aret/g46u_raw.json.gz
python3 benchmarks/la_export.py <raw.json> costs.csv bytes.csv     # cmp against committed: identical
python3 benchmarks/la_export.py artifacts/aret/g46_raw.json my_g46_costs.csv my_g46_bytes.csv   # fresh rerun
PYTHONPATH=/workspace/la-verify python3 -m amortization costs.csv --cont A --base B --bootstrap 5000
#   contrasts run: A/C, A+maint/C+maint, A/B, C/B, A+maint/B, C+maint/B on g46 and g46u
PYTHONPATH=/workspace/la-verify python3 -m amortization docs/evidence/v4/g46_costs.csv --cont C --base B --bootstrap 5000
```

The sensitivity analyses (inline Python, reproducible from the raw JSON) were:
- **Jointly uncensored A‖B:** sum the task `cost.cpu_s` over tasks where both A and B have
  `correct == n_sealed`, then compute `1 − ΣA/ΣB` per seed.
- **Startup-inclusive:** add `0.0328 × cost.processes` to every task and family `cpu_s`,
  re-export with `la_export.py`, and run the unmodified instrument. The 0.0328 s figure is the
  median over 20 calls of `getrusage(RUSAGE_CHILDREN)` CPU minus the reported `cpu_s`, for
  `python3 -m packetlm.engine STATE 'fact a parent b' 'what is a parent'`.
