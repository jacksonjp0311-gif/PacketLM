# Independent verification of PacketLM @ e944840

- **Verifier:** an independent Grok Bot verifier, using the same method as `VERIFY_0b0f6a8.md`
  (branch verify-0b0f6a8) and `VERIFY_82dd0a2.md` (branch verify-82dd0a2).
- **Date:** 2026-11-26, about 23:12–23:30 America/New_York.
- **Target:** `g44-canonical-engine` @ `e944840`, which is also the PR #1 head at the time of
  checking.
- **Commits in scope:**
  - `0cf4a9c` / `69239f5`: G48R pre-registration and results;
  - `a1c977c`: baseline-first mutation driver;
  - `264d082`: the response to verify-82dd0a2, with the G48R2 pre-registration;
  - `60b1614`: G48R2 results;
  - `ae1f92d`: PX mechanism and pre-registration;
  - `e944840`: PX results.
- **How each run was reproduced:**
  - G48R2 was rerun at its registered commit 264d082, in a separate worktree. Its engine-only
    hash is `e30c08437fe9`, matching the receipt.
  - PX and the counts were rerun at e944840. `packetlm/` and the harness are identical to
    ae1f92d, and the engine hash `9f9a71390c2f` matches the receipt.
- **Environment:** `GITHUB_TOKEN` and `GH_TOKEN` were unset. `/workspace/PacketLM` was not touched.

## Verdict

**What reproduced:**
- Every count.
- **G48R2 on all 7 seeds:** 28/28 reply hashes are byte-identical to the committed data, and
  all 8 checks pass. 0 tasks qualified, so H3 is vacuous, as stated in advance.
- **All of PX:** both parts, every seed and every threshold. The G48-world reply hashes match
  21/21, and every G46 metric matches.
- **The N1, N2 and N3 fixes are real.** Each is covered by a check, and N1 and N2 also by a
  mutation that kills them.
- The leakage guards now cover every registered curriculum, and nothing leaks.

**Findings:** no high-severity issues, and three medium ones.
- **P1.** In programs mode, a `!none` statement alone, with no value example, can produce an
  adopted capability that then gives values. "Only contradicts, never supplies values" doesn't
  hold as stated. It does hold for the registered runs, which always teach value examples first.
- **P2.** PX's spurious-answer gain (5.79% → 2.39%) comes almost entirely from R giving up on T1.
  Without T1 it is 3.09% → 2.72%.
- **P3.** PX.md blames the missing qualification in G48 worlds on the 200k scan budget. In fact
  every scan stops early, after at most 982 programs, because it has found 16 genuine blockers.

## Reproduced vs claimed

### Counts (e944840, fresh processes)

| command | claimed | reproduced |
|---|---|---|
| `python3 -m packetlm.g44_test` | 101 | **101, failed []**. There are no `.completed` pseudo-checks any more: they appear only when a section raises (82dd0a2 L3 addressed) |
| `python3 -m packetlm.suite` | 188 | **188, 0 failed, 11/11** |
| `python3 -m packetlm.g45_test` | 18/18 | **18, failed []** |
| `python3 -m packetlm.mutations` | 46/46 | **46/46, baseline_failed [], 0 crash-only** |

### G48R2 (264d082; `python3 benchmarks/g48.py --seeds 511,…,517 --out g48r2`, all 7 seeds, under 1 min)

| check | claimed | reproduced |
|---|---|---|
| H1 | P 1.000 on T1 (434), T2 (168), T3 (126), T4 (434) | identical |
| H2 | depth ≥ 3: 1.000 (378); depths 6–7: 1.000 (42) | identical |
| H3 | 0 wrong-qualified, 0 qualified (vacuous) | identical. All 56 P tasks are provisional, with a horizon-5 scan that hits 16 blockers |
| H4 | X on T1–T3 0.000; T4 0.065 | identical (T4 0.0645) |
| H5 | S 0.000 | identical (0/1162) |
| H6 | A ≡ P on 7/7 | **7/7** |
| `no_example_is_evaluated` | 0 leaks | 0. My broader check (examples plus all final-state observations against evaluated rows) also gives **0** |
| `cpu_total_s` P / A / X / S | 24.81 / 20.29 / 10.45 / 140.56 | 25.24 / 21.19 / 10.77 / 137.39 |

### PX (e944840 = ae1f92d engine; `python3 benchmarks/px.py --out px`, all seeds, about 2 min)

| item | claimed | reproduced |
|---|---|---|
| PXA1 R wrong-qualified | 0 | 0 |
| PXA2 V ≡ R | 7/7 | 7/7 |
| **PXA3 spurious rate on no-value items** | **P 5.79% (78/1346) vs R 2.39% (33/1383)** | **identical** |
| PXB1 seed 33, threshold 6 | E passes; C fails | identical. **C:** `bbtwyr` ambiguous, asked `ozvihs` and `lumuyl` (both unanswered), 3/4. **E:** asked `kypodt` → `!several` and `vngduk` → `!several`; `epwzki` and `bpapsg` withheld; adopted `cap:dditje@1 + cap:vomvnu@1`, provisional, **4/4** |
| PXB2 | E passes every threshold 1–6 that C passes on 11–55, with 0 wrong-qualified | identical. Per-seed metrics, statuses, question and statement counts are all equal |
| **R's T1 accuracy** | **0.000**, 14 suspended | **0.000**, `{'suspended': 14}` in both R and V |
| T2 / T3 / T4 (R) | 1.000 | 1.000 |
| `cpu_total_s` P / R / V | 27.2 / 73.8 / 72.1 | 27.85 / 74.01 / 72.39 |
| G46 E/C cost | 1.35–1.45× | 1.35–1.46× |

For the seed-33 statements, I recomputed the truth independently. `kypodt` and `vngduk` both
have an ambiguous truth (2 values each), and neither is sealed. `epwzki` (undefined) and
`bpapsg` (ambiguous) *are* sealed and were correctly withheld. So the teacher stated `!several`
only for non-sealed items where it was true.

## Are N1, N2 and N3 really fixed?

**N1 (question pool, as a set):**
- `_question_pool` in programs mode is now `sorted(e for e in entities() if e in component(observations))`.
- `prog_question_pool_same_set_under_retention` is a genuine check. It builds a static engine
  and an adaptive one over two token-disjoint worlds, archives **every** component in the
  adaptive one (`archived_all`), runs `investigate` through `turn` (which restores), and
  requires identical replies.
- It is killed by `restore_off` and `prog_investigate_outside_component`.
- Empirically, G48R2 H6 passes 7/7 and PX PXA2 passes 7/7.
- **Fixed.**

**N2 (full-horizon scan):**
- `_acquire_programs` now scans with `horizon = progs.MAX_SIZE`.
- `prog_filter_full_horizon_blocks` requires `provisional` with horizon 5. It is killed by
  `prog_scan_short_horizon` and `prog_scan_ignored`.
- In G48R2, 0 of 56 P tasks qualify. All T3 tasks now have ≥ 16 blockers, consistent with my
  82dd0a2 rescan.
- **Fixed.**

**N3 (T4 examples):**
- `ex4` now excludes `sealed1`.
- `no_example_is_evaluated` is a registered threshold, and it passes in G48R2.
- The check only compares the *initial* examples with evaluated rows (L5 below). My broader
  check over final-state observations found 0.
- **Fixed.**

**The 82dd0a2 lows:**
- L1 (depth wording): fixed in G48.md.
- L2 (registry coverage): fixed. The registry has 6143 tokens and covers the G47-AR seeds plus
  all 728 evaluated G48R2 and PX items. None of the registered tokens appear under `data/`.
- L3 (pseudo-checks): fixed.
- L4 (engine hash): `engine_hash()` now excludes tests, mutations and suite.
- L5 (PR "6–10×"): now qualified with "in-call CPU … with startup about 1.5–1.9×".
- L6 (wording): fixed.

## Findings by severity

### High: none

### Medium

**P1. "`!none`/`!several` only contradict and never supply values" doesn't hold in programs mode.**

What holds, in code and by test:
- No statement is ever stored as a fact. Observations keep `[s, "!none"]`, and the fact list is
  unchanged.
- No statement is ever returned as an answer.
- `programs.proposals` skips statements as answer entities, and the mutation
  `px_statement_as_answer_entity` is killed.
- A value answer is judged exactly as before. The open-world rule is unchanged.

What doesn't hold:
- **"Only contradicts":** `judge_set` makes `!none` *support* an empty prediction, and
  `!several` support any prediction with two or more values. PX.md states this.
- That support counts towards a program being "supported on every observation", and towards
  the blocker rule "support ≥ 1 and differs".

**Consequence (reproducible):**

```
python3 -m packetlm.engine S.json --programs --answers 'fact a p b' 'fact b p c' 'example k: c -> !none' 'what is a k'
→ provisional k prog:rel:p ;  a k b [no construction for k] [provisional]
```

- In programs mode, a single `!none`, with **no value example at all**, yields an adopted
  capability that answers `a k b`.
- The base engine refuses only because activation pruning removes candidates whose image of the
  observed subjects is empty. With `--no-activation` the same input gives `ambiguous k`, meaning
  candidates supported only by negative evidence exist there too.
- The registered PX runs aren't affected, because every task starts with ≥ 2 value examples.
- **Suggested fix:** a capability is adopted only if at least one observation is a value, plus a
  check and a mutation.

**P2. PXA3's improvement comes from the T1 collapse, not from better abstention in general.**

| class | P spurious | R spurious |
|---|---|---|
| T1 | 42/182 | 0/168 |
| T4 | 36/170 | 33/179 |
| T2, T3 | 0 | 0 |

- **Without T1, the rates are P 3.09% (36/1164) and R 2.72% (33/1215).**
- R's T1 abstains perfectly *because R adopted nothing there*: all 14 tasks are suspended and
  defined-item accuracy is 0.000.
- PX.md does show the per-class tables, and the PR states the T1 drop. But Reading item 2
  ("they improve abstention") and the PR headline "Spurious answers 5.8% → 2.4%" present this
  as a gain.
- **Suggested wording:** "on G48 worlds the overall spurious rate fell 5.8% → 2.4%, almost all
  from T1, where R adopts nothing (accuracy 0.000). Without T1 it is 3.1% → 2.7%."

**P3. PX.md misdiagnoses why nothing qualifies in G48 worlds.**
- PX.md says qualification "requires the MAX_SIZE scan to finish within 200k programs, which it
  does not in G48 worlds". Reading item 5 proposes "a scan that completes: an exact pruned
  program scan".
- In both the PX and the G48R2 raw data, **every** programs-mode scan has `complete = False`
  because it reached `BLOCK_KEEP = 16` blockers. The largest number scanned is 982 (G48R2 T3);
  no scan comes near 200,000.
- The obstacle is genuine open-world blockers, mostly less-defined alternatives such as
  `is:K:T|…`, as G48R2.md correctly says. Scan cost is not the obstacle.
- An exact pruned scan would find the same blockers. Only closed-world evidence, the second
  route in Reading item 5, addresses them.

### Low

- **L1. The commit timeline can't prove that the pre-registration came before the run.**
  - G48R2: pre-registration 22:59:01, results 22:59:59, a 58 s gap.
  - PX: 23:09:26 → 23:11:40, 2 min 14 s.
  - My runs: G48R2 took under 1 min, and PX about 2 min, with both running at the same time.
  - The gaps are just long enough to run them, but too short to also write up results unless
    that was done in advance. Commit times alone can't rule out a run that started before its
    pre-registration commit.
  - Against that: the engine hashes in the receipts equal the pre-registration commits; the
    pre-registration texts are unchanged apart from the removed placeholder line; nothing in
    `packetlm/` or the harness changed between pre-registration and results (only regenerated
    `sealed_tokens_g48.json` and `sealed_extra.py`); and nothing suggests manipulation.
  - **Suggestion:** record the run start time (wall clock) and the HEAD SHA in each receipt.
- **L2. The base-engine question pool is still in storage order.**
  - `_question_pool` returns `entities()` unsorted when `programs=False`, and that includes
    `--answers` in G46.
  - The latent retention hazard noted in the ledger remains for base-engine plus
    adaptive-retention runs. PX's E arm doesn't use retention, so it isn't exercised.
- **L3. `_operator_prims` treats statements as answer entities.**
  - With `--operators`, any `!none`/`!several` observation joins the "shared properties of
    every observed answer" intersection, and that empties the until-proposal set.
  - Not exercised (operators off), but `proposals` got the equivalent guard and this one didn't.
- **L4. PX abstention items aren't in the sealed registry.** Only evaluated `rows` are. They're
  queried, never taught, so there's no leak.
- **L5. `no_example_is_evaluated` checks only the initial examples.** Investigate-answered
  subjects aren't included. They're protected by the sealed refusal, and my broader check found 0.

### Info

- G48R (seeds 491–497, 6/7, H6 failed) wasn't rerun. It wasn't requested, and it is superseded
  by G48R2. The results commit leaves its pre-registration text unchanged.
- PX's honesty items are proportional. They report that R's T1 drops to 0.000 because depth ≥ 3
  is not identifiable once the reflexive program is refuted, and that "P's 1.000 came from an
  Occam accident". There is no qualification gain on G48 or G46.

## Commands

```bash
cd /workspace/pl-verify && env -u GITHUB_TOKEN -u GH_TOKEN git fetch origin && git checkout e944840
python3 -m packetlm.g44_test; python3 -m packetlm.suite; python3 -m packetlm.g45_test; python3 -m packetlm.mutations
git worktree add --detach /workspace/pl-verify-264 264d082
(cd /workspace/pl-verify-264 && python3 benchmarks/g48.py --seeds 511,512,513,514,515,516,517 --out g48r2)
python3 benchmarks/px.py --out px
# P1
python3 -m packetlm.engine /tmp/s.json --programs --answers 'fact a p b' 'fact b p c' 'example k: c -> !none' 'what is a k'
python3 -m packetlm.engine /tmp/t.json --answers --no-activation 'fact a p b' 'fact b p c' 'example k: c -> !none' 'what is a k'
```

The P2 and P3 figures come from the raw data:
- **P2:** per-class sums of `abstain.{n,spurious}` over the PX part A tasks, excluding T1.
- **P3:** `hyp.scan.{complete, blocking_n, scanned}` over every programs-mode task in the PX and
  G48R2 raw data.
