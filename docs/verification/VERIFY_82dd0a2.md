# Independent verification of PacketLM @ 82dd0a2

- **Verifier:** an independent Grok Bot verifier. It did not write this code. Same method as
  `VERIFY_0b0f6a8.md`.
- **Date:** 2026-11-26, about 22:48–23:10 America/New_York.
- **Target:** `g44-canonical-engine` @ `82dd0a2`. By the time of writing, the PR #1 head had
  moved on to `0cf4a9c`, which is not covered here.
- **Commits in scope:**
  - `db5ef90`: crash-to-named-check;
  - `9f2c957`: seed-33 analysis;
  - `6d01612`: the response to verify-0b0f6a8;
  - `8fa5c7b`: G48 and G47-AR pre-registration, plus the grammar;
  - `82dd0a2`: results, plus the post-run tie-break fix.
- **Engines:**
  - The registered engine (8fa5c7b) has `source_sha256 6a61c9d64bf0…`, which matches both
    receipts.
  - 82dd0a2, after the fix, is `42e8d94c6a5d…`.
  - The registered benchmarks were reproduced in a separate worktree at 8fa5c7b. Counts and
    post-fix checks were run at 82dd0a2.
- **Instrument:** learning-amortization @ 70297af, unmodified (fresh clone, as before).
- **Environment:** `GITHUB_TOKEN` and `GH_TOKEN` were unset. `/workspace/PacketLM` was not
  touched.

## Verdict

**What reproduced:**
- Every claimed count.
- **G48 on all 7 seeds:** all 28 seed×arm reply hashes are byte-identical to the committed raw
  data, including H6 failing on 481 and 487.
- **G47-AR on seeds 44 and 55:** decisions are identical, and the cost ratios are within noise.
- The recorded results come from the registered engine, unaltered by the post-run fix.
- The 0b0f6a8 findings are mostly addressed.

**Three new medium findings:**
- **N1. The post-run fix doesn't fix H6.** At 82dd0a2, A still differs from P on 481 and 487.
  The diagnosed mechanism is incomplete.
- **N2. All 14 "qualified" T3 tasks** rely on an open-world scan only as long as the candidate.
  That is the short horizon the G44 audit's P0 removed from the base engine. One token more
  makes every one of them provisional.
- **N3. Six of 14 T4 tasks** were taught one example that is also a sealed evaluated item. The
  effect on reported numbers is nil, since P is 1.000 either way.

## Reproduced vs claimed

### Counts (82dd0a2, fresh processes)

| command | claimed | reproduced |
|---|---|---|
| `python3 -m packetlm.g44_test` | 102 | **102, failed []** |
| `python3 -m packetlm.suite` | 189 | **189 checks, 0 failed, 11/11 modules**; smoke 10/10 ran; 13 smoke false self-reports now listed |
| `python3 -m packetlm.g45_test` | 18/18 | **18, failed []** (t7b now strict) |
| `python3 -m packetlm.mutations` | 40/40, none crash-only | **40/40 killed, 0 crash-only** |

The 4 formerly crash-killed mutations now also fail real named checks:
- `no_backup_fallback`: `fresh_process.p6_recovery_reported`;
- `library_off`: `acquisition.library_reuse` and 4 more;
- `activation_overprunes`: 2;
- `compose_keeps_source`: 18.

`prog_order_dependent_ties` is killed by `programs.prog_question_independent_of_fact_order`.

### G48 (registered engine 8fa5c7b; `python3 benchmarks/g48.py`, all 7 seeds, about 1 min)

| threshold | claimed | reproduced |
|---|---|---|
| H1 P per class | T1 1.000 (434), T2 1.000 (168), T3 1.000 (126), T4 1.000 (434) | identical |
| H2 P T1 depth ≥ 3 | 1.000 (378); depths 6–7: 1.000 (42) | identical |
| H3 P wrong-qualified | 0; 14 qualified tasks (all T3), 126 qualified answers | identical (but see N2) |
| H4 X T1–T3 | 0.000 (728) | identical |
| H5 S overall | 0.0009 (1/1162) | identical |
| H6 A ≡ P | FAIL on 481, 487 | **FAIL on 481, 487**. Only round-1 T4 `asked` differs; seq, status and every evaluated reply are identical |
| source unchanged | pass | pass (6a61c9d…) |
| status mix / questions | T1, T2, T4 provisional ×14 each; T3 qualified ×14; 168 questions; T4 library uses 14 | identical |
| `cpu_total_s` P / A / X / S | 19.69 / 16.91 / 10.61 / 139.28 | 19.67 / 16.97 / 11.18 / 134.59 |

### G47-AR (registered engine 8fa5c7b; `python3 benchmarks/g47ar.py --seeds 44,55`)

| | claimed | reproduced |
|---|---|---|
| H-AR1 no harm | PASS | **PASS**. Stricter check: full reply text, status, seq and `asked` give W ≡ K and Y ≡ L, with 0 diffs over 648 replies (my run) and 1620 (committed, 5 seeds) |
| acquired / sealed correct, every arm | e.g. K 36/162, Q 15/81, M 23/118 (seed 44) | identical on both seeds, all 6 arms; archive files 5 |
| W/K ratio, seeds 44 / 55 | 0.719 / 0.696 | **0.708 / 0.723** |
| Y/L ratio, seeds 44 / 55 | 0.726 / 0.724 | **0.727 / 0.729** |
| H-AR2 (≥ 4/5 lower) | 5/5 and 5/5 | 2/2 and 2/2 on the seeds run |
| L / Y / M CPU per acquired, depth 3 | 0.343–0.354 / 0.248–0.260 / 0.400–0.448 | 0.338, 0.340 / 0.246, 0.248 / 0.432, 0.411 |
| `A_36(W+maint‖K+maint)` / `A_36(Y+maint‖L+maint)` | +0.288 / +0.271 | from the committed CSV: **+0.2876 [+0.2771, +0.2981] / +0.2709 [+0.2672, +0.2746]**, S = 5, p = 0.0625 |

`la_export.py --total` on the committed raw data reproduces `g47ar_costs_total.csv`
byte-identical.

## Findings by severity

### High: none

Nothing was fabricated or failed to reproduce, and no threshold moved. On the pre-registration
docs, between 8fa5c7b and 82dd0a2 the only removed line in G48.md and G47_AR.md is the
placeholder "(Written after the registered run.)". `benchmarks/` is unchanged.

### Medium

**N1. The post-run tie-break fix doesn't make H6 hold. The diagnosis in G48.md is incomplete.**

I ran `python3 benchmarks/g48.py --seeds 481,487` at 82dd0a2, the fixed engine:
- H6 is still **FALSE** on both seeds.
- Again only round-1 T4 `asked` differs:
  - 481: P asks `acwbyi, agjngl, aingzy, akktqc`; A asks `anktea, aobqsi, bcipzi, cakdcc`;
  - 487: P asks `ahergm, ailwyx, akamxz, akmoht`; A asks `ahergm, akmoht, arrrpj, awrhxe`.
- All 4 of P's questions came back `unanswered`.

The second cause:
- Programs-mode `investigate` ranks **every entity in the hot index** (`self.entities()`), not
  just the observation component.
- Under adaptive retention, archived components are absent from that index, so the candidate
  set differs, not only its order.
- Sorting fixes the order but not the set.

The new check `prog_question_independent_of_fact_order` and the mutation
`prog_order_dependent_ties` test the order only.

The fix also changes the registered P arm's behaviour on those seeds. Replies differ from the
registered P in `asked`, while seq, status and answers are unchanged. So the current engine's
question policy is no longer the one that was measured.

The recorded results are **not** altered: they come from engine 6a61c9d and reproduce byte for
byte. But the G48.md text "Cause: … fact storage order" and "Fix, after the run" need
correcting. A new H6 run would fail as things stand.

**N2. T3 "qualified" depends on a horizon equal to the candidate's size, which the G44 audit removed for the base engine.**
- `_acquire_programs` scans with `horizon=progs.size(cand)`, which is 2 for T3.
- G48.md says this horizon "is the same as the engine's deepening". It isn't. The base engine
  uses `horizon = self.deepen`, the full budget (audit 283f526 P0 item 1). The mutation
  `scan_short_horizon` kills exactly `horizon = searched` there.
- I loaded each final registered P state (8fa5c7b run) and rescanned all 14 qualified T3
  candidates (`/workspace/t3real.py`):
  - at horizon 2: 0 blockers, reproduced;
  - at horizon 3: **4–5 blockers in all 14**, e.g. `is:K:T|rel:R>is:K:T`. These support every
    observation and differ on the T-typed objects in the domain, where the candidate is undefined.
- Under the engine's own G44 rule, all 14 would be **provisional**. H3 then has 0 qualified
  tasks and nothing to test.
- The horizon rule was stated in the pre-registration ("up to the candidate's size"), so this is
  a disclosed but weakened rule, not a post-hoc change. Still, the "something to bite on"
  framing of H3 overstates what it shows.

**N3. Leakage: sealed T4 items were used as teaching examples (immaterial to the numbers).**
- `ex4` samples examples from `info` at depths 1 and 2 *after* `info` has been extended with the
  T1 transfer chains. The depth-1/2 transfer nodes are in `sealed1`, so they are also
  evaluated T4 items.
- G48.md says T4's sealed items include the transfer chains.
- Affected P tasks: 482 r0 `emsrpk`, 482 r1 `irvbji`, 484 r1 `kwcczx`, 485 r1 `amxesj`, 486 r0
  `weocza`, 486 r1 `uuvzfe`. That is 6 of 14 T4 tasks and 6 of 434 T4 items. The same
  happens in every arm.
- P is 1.000 on all T4 items, so excluding these doesn't change H1. The guard needs fixing
  before the next run.
- No other overlap was found: across all 224 task records, no example or observation subject is
  an evaluated item outside T4. The investigate refusal for sealed subjects works.

### Low

- **L1. "Traversal to any depth"** (G48.md, under Acquired) is bounded by `MAX_DEPTH = 8`. The
  T1 program returns the root up to depth 9 and **nothing at depth ≥ 10** (checked with
  `programs.run`). The tested maximum is 7.
- **L2. The sealed-token registry** (`benchmarks/sealed_tokens*.json`, 2745 tokens) covers
  G46/G46-U seeds 11/22/33 only. It does not cover the G47-AR seeds 44/55 (243 sealed tokens
  each, 0 in the registry) or the G48 items. I found none of them, nor any of the 728 evaluated
  G48 item tokens, under `data/`.
- **L3. g44's 102 includes 10 `<section>.completed` pseudo-checks** from db5ef90. If a section
  raises, its other checks drop out of the count instead of each failing.
- **L4. The G48 dev receipt reports `source_sha256 f7932ad5…`, not the registered `6a61c9d…`.**
  `source_hash` also covers `g44_test.py` and `mutations.py`, so this may be test-only.
  Which source changed after "Dev 3" can't be determined from the repo. The G47-AR dev receipt
  does match the registered engine.
- **L5. The 0b0f6a8 M4 finding is only partly carried into the PR body.** Line 83 still says
  "Unrelated knowledge still costs about 6–10× an empty state per task" with no cost-boundary
  qualifier. With startup included it is about 1.5–1.9×. ARET.md and the ledger are corrected.
- **L6. Wording:** a recursive second clause (`c2 + self`) need not contain a step, though G48.md
  says the second clause "contains a step".

### Info: designed vs acquired, checked in code

- **No `until` and no domain logic in the qualified path:**
  - `_acquire_programs` builds its vocabulary only from told relations and `cap:` library tokens
    in the component, and its guards from `programs.proposals`, a generic (Q, T) co-occurrence rule.
  - `op:until` is produced only by `_until_proposals`, under `operators=True`. No G48 arm passes
    `--operators`.
  - `programs.py` has no world-specific names.
  - Truth comes from the independent `run_naive`.
- **Designed bias, as stated:**
  - The 2-clause guard-first form and tail-`self` match the hidden shapes of T1, T2 and T4.
  - The guard proposal "(Q, T) shared by every observed answer" hands T1 its `is:K:tgt` guard.
  - Both are disclosed as designed. No out-of-grammar target was tested.
- **H4 (X ≤ 0.5) holds by construction:** sequences can't express guards.
- **G48 tests no abstention:** items with undefined truth are dropped from evaluation.
- **Timeline:** pre-registration 8fa5c7b at 22:42:56, results 82dd0a2 at 22:47:22. The
  registered run is quick (G48 about 1 min, G47-AR about 2 min for 2 seeds on 8 cores), so
  4.5 minutes is plausible. Dev receipts (seeds 998/999 and 999) are committed in the
  pre-registration commit.

## Earlier findings (verify-0b0f6a8)

| finding | status |
|---|---|
| M1 maintenance vs B unreported | **Addressed**: ARET.md, ledger and PR report +0.031 [−0.005, +0.071] |
| M2 "matched accuracy" | **Addressed**: withdrawn; jointly-solved ≈ −0.04 reported |
| M3 S = 3 intervals | **Addressed**: labelled as seed bootstrap; G48 uses S = 7 and G47-AR S = 5 |
| M4 startup excluded | **Addressed in code**: `cpu_total_s` from `getrusage(RUSAGE_SELF)`, `la_export --total`, used as primary in G48 and G47-AR. **Partly in docs** (L5) |
| L1 dev history | **Addressed going forward**: dev receipts committed with the pre-registration (see L4) |
| L2 G45 7b | **Addressed**: strict |
| L3 sealed guard G46-U | **Addressed** for G46-U; not extended to G47-AR seeds or G48 (L2 here) |
| L4 doc drift | **Addressed** |
| L5 smoke self-reports | **Addressed**: listed in the suite output (13) |

## Commands

```bash
cd /workspace/pl-verify && env -u GITHUB_TOKEN -u GH_TOKEN git fetch origin && git checkout 82dd0a2
python3 -m packetlm.g44_test; python3 -m packetlm.suite; python3 -m packetlm.g45_test; python3 -m packetlm.mutations
git worktree add --detach /workspace/pl-verify-8fa 8fa5c7b      # registered engine 6a61c9d
cd /workspace/pl-verify-8fa && python3 benchmarks/g48.py && python3 benchmarks/g47ar.py --seeds 44,55
cd /workspace/pl-verify && python3 benchmarks/g48.py --seeds 481,487          # post-fix engine 42e8d94 (N1)
python3 benchmarks/la_export.py docs/evidence/g47ar/g47ar_raw.json /tmp/g47ar_total.csv --total   # == committed CSV
PYTHONPATH=/workspace/la-verify python3 -m amortization /tmp/g47ar_total.csv --cont W+maint --base K+maint --bootstrap 5000
```

The N2 rescan (`/workspace/t3real.py`) works as follows:
1. Copy each `artifacts/g48/P_<seed>.json` (8fa5c7b run) and open it with `programs=True`.
2. Rebuild the component, the relations, the guards and the domain exactly as
   `_acquire_programs` does.
3. Run `Inducer.scan(cand, cand_pred, horizon=2)` and then `horizon=3` for every qualified T3 task.

N3 compared, for every task in `g48_raw.json`, the example and observation subjects against the
evaluated row subjects. N1 compared the round-1 T4 `asked` lists of A and P in the post-fix raw data.
