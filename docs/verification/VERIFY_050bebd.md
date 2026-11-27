# Verification of g44-canonical-engine at 050bebd (commits 1932326, 050bebd)

Verifier: Grok Bot (executor). Fresh clone `/workspace/pl-verify`, `GITHUB_TOKEN`/`GH_TOKEN` unset,
`/workspace/PacketLM` untouched. Times are America/New_York. Tools: `docs/verification/tools_050bebd/`.

## Verdict in one paragraph

- **t5 restatement: legitimate correction, not a weakened regression.**
  - The demotions are genuine: a fresh learner given the same facts and examples reaches the
    same provisional status with the same blockers.
  - Every retained value is byte-identical.
  - The restated check still fails on each of 5 retention-loss mutations I wrote, on all 3 seeds.
- **S1 and L1 fixes work.** The S1 repro now answers `[provisional]`, and L1 demotion propagates.
- **New finding, Medium (N1), programs mode only.** In programs mode, the S1 re-acquisition can come
  back with *no candidate*. When it does, the current version keeps `qualified` without being
  re-scanned. This happens after the `complete` statements that qualified it were retracted.
  Under the engine's own rule (the full guard space), that version has blockers.
  - I found **no** honest-teacher wrong answer from it in about 3,200 random operations, 960 of
    which were truth-preserving by construction.
- **`--bounded` is exact on everything I ran:**
  - 18/18 arm×seed reply streams equal the registered ones, and Cb = C on all 4 rerun seeds;
  - 1,400 random differential sessions (65k lines, 547 skips) showed 0 differences.
- **Everything else reproduces:**
  - counts: 128 / 216 / 18/18 / 77/77;
  - registered A values: exact;
  - G51 corrections: correct;
  - timeline: consistent with the receipts.

## 1. Counts (050bebd, fresh processes)

| command | claimed | reproduced |
|---|---|---|
| `python3 -m packetlm.g44_test` | 128 | **128, failed []** |
| `python3 -m packetlm.suite` | 216 | **216, 0 failed, 11/11 modules** |
| `python3 -m packetlm.g45_test` | 18/18 | **18/18** (`retention_strict_identical` false on 101/202/303) |
| `python3 -m packetlm.mutations` | 77/77 | **77/77 killed, baseline_failed []** |

Each new mutation is killed by its intended check:
- `s1_growth_ignored` and `s1_region_is_domain_only`: by `s1_growth_in_region_requalifies`;
- `l1_dependency_status_ignored` and `l1_no_demotion_propagation`: by `l1_qualified_needs_qualified_deps`;
- `g53_memo_key_ignores_primitive`, `g53_index_drops_primitives` and `g53_sparse_conflict_ignored`: by
  `g53_bounded_scan_equals_unbounded`;
- `g53_skip_ignores_basis`: by `g53_fc_skip_only_settled`.

Three existing mutation sites were re-anchored to the new code: `prune_on_evidence_only`,
`fc_no_requalify` and `m1_no_review_on_complete`. Each one still mutates the same logic.

## 2. Priority 1: G45 t5 (retention) restatement

**What changed.** At cdb4828, t5 required `final replies == replies right after acquisition`.
At 1932326, t5 passes if both of these hold:
- every *changed* reply has the same value with ` [provisional]` appended;
- its capability's current version satisfies all of these:
  - it is `provisional`;
  - it was once `qualified`;
  - its last history entry is `requalified`;
  - `evidence.blocking > 0`.

The strict result is still reported as `retention_strict_identical`.

**(a) The demotions are genuine alternatives** (`t5_run.py`, `t5_fresh_learner.py`). On each seed,
D1's capability is demoted after D5 (`cap(D1)+e`) tells `e` facts from D1's layer-2 entities.

| seed | D1 cap | candidate | blockers (engine) | my evaluation of each blocker on the final facts |
|---|---|---|---|---|
| 101 | mdtypd | zrdhxg>uffxsz | `{gqwzvq,uffxsz,vxgoeb,zrdhxg}>kkabje` | empty output on both observations (open world: undetermined, not contradicted); singleton value different from the candidate's on 12 of the 24 domain entities (the layer-1 ones) |
| 202 | raccri | scmbvs>olveji | `{izyvvg,olveji,rnkfwg,scmbvs}>kmcmlr` | same pattern: 0/2 contradicted, 12/24 conflicting |
| 303 | fmqrst | dolsvn>kacdio | `{dolsvn,ecmymu,kacdio,ykaqvi}>hczlss` | same pattern: 0/2 contradicted, 12/24 conflicting |

Each blocker passes the engine's existing conflict clause: it is not contradicted, and it has a
singleton value that differs at some domain entity. This is the clause that has always applied.

**Fresh-learner test.** I replayed only the told facts and D1's two examples into a new state:
- **with all final facts:** provisional, with exactly the 4 blockers above, on all 3 seeds;
- **without D5's `e` facts:** qualified, with 0 blockers.

So the demotion is exactly what the qualification rule gives on the current facts. Before S1, the
old version was simply never re-scanned. That was the stale-status bug S1 fixed.

Note that the blockers disagree only at layer-1 domain entities. At the re-asked layer-0 subjects
they are undefined. Demoting the whole version is therefore conservative for those answers, which
is consistent with per-version status. This is an observation (I1), not a defect.

**(b) Values are byte-identical** (`t5_values.py`).
- On each seed, 10 of the 60 domain re-asks changed. All belong to the demoted capability.
- Every changed reply is `before + " [provisional]"`, and every value equals the truth.
- The 12 transfer items are at new entities and were already provisional.

**(c) The restated check still catches real retention loss** (`t5_mutations.py`). Each mutation
was applied to a temporary copy of `packetlm/`, and seeds 101/202/303 were run:

| mutation | what it does | restated t5 |
|---|---|---|
| `t5_value_changed_when_provisional` | provisional answers return a different value | **fails on 3/3** |
| `t5_value_lost_when_provisional` | provisional answers become `unknown` | **fails on 3/3** |
| `t5_demoted_without_rescan` | growth demotes to provisional (reason `requalified`) without a re-scan or blockers | **fails on 3/3** |
| `t5_rescan_adopts_blocker` | the re-scan adopts a blocker's program as the current seq | **fails on 3/3** |
| `t5_value_changed_qualified` | qualified answers change value in the retention process | **fails on 3/3** |

**Verdict on t5: a legitimate correction.**
- The strict reading tested "no status change ever". S1 makes that false by design whenever a real
  alternative appears.
- The restated check keeps the part retention was about: the same values, plus a demotion that is
  justified by a re-scan with blockers.
- It rejects lost values, changed values, unjustified demotions and silent re-adoption.

Two caveats (L1, L2 below):
- `docs/G45.md` still states the strict criterion.
- The check trusts the engine's own `blocking` count. A scan that reported spurious blockers would
  pass t5. That case is guarded elsewhere, by the scan-vs-brute-force checks and the `g53_*` and
  `fc_*` mutations, not by t5.

## 3. Priority 2: S1 and L1 fixes; adversarial search

**S1 repro** (my 4-fact case from VERIFY_cdb4828):
```
... 'what is m hq' 'fact m r3 z' 'what is m hq'
→ m hq c [no construction for hq]
  recorded m r3 z
  m hq c [no construction for hq] [provisional]
```
- Before: qualified. After: `[provisional]`. Fixed.
- `g44`'s `s1_growth_in_region_requalifies` also checks that a fact at a new entity (`u r3 z`) does
  not trigger a re-scan.

**L1 probe:**
- `yy = ra>rb` is qualified, and `kk = cap:yy@1>rc` is qualified.
- I added `rd` facts that make `yy` ambiguous. `yy` goes provisional ("several supported
  programs"), and `kk` then goes provisional with history reason `dependency yy@1 provisional`.
- Answers of both are `[provisional]`.
- `requalify yy`, which comes back `ambiguous`, leaves `kk` provisional. That is conservative.

**Code read of S1:**
- Growth is recorded for told non-`cap:` facts whose subject was already a fact entity, and for
  every removed told fact.
- Before the next non-`fact` line, and before `save`, every qualified version whose region (the
  component of domain ∪ observed subjects) contains a grown subject is re-acquired.
- The claim "a fact whose subject is a new entity cannot change values at known entities" holds,
  because programs read outgoing edges only.
- One edge case: an *observation-only* subject (an example at an entity with no facts) counts as
  "new". In programs mode such an entity is outside the recorded domain, so its answers are
  provisional (M2). In base mode the equal-length alternative needed to exploit it makes the
  capability ambiguous. I could not get a wrong qualified answer from it.

**Adversarial search** (`adversarial3.py`):
- **Set-up:**
  - an honest teacher;
  - after qualification, 1–6 random operations (facts at known entities, including closure
    members; facts from brand-new entities into the world; facts to brand-new entities, with
    facts at them; `retract`; `correct`);
  - save and re-open between operations with probability ½;
  - every old and new entity queried against the truth on the **current** facts after every
    operation.
- **Classification of each wrong qualified answer:**
  - whether the hidden H was inside the declared space (base: length ≤ horizon; programs: H's
    guards among the scanned guards);
  - whether every recorded observation is still true under H on the current facts. This is the
    honest-teacher criterion: if it is false, the world changed the truth at an observed subject.

| mode | qualified cases | ops | wrong qualified after ops | of which H in space | of which observations still true |
|---|---|---|---|---|---|
| base (seeds 11, 12) | 164 | 558 | 2 cases | 0 | **0** |
| bounded (11, 12) | 164 | 558 | 2 cases (identical to base) | 0 | **0** |
| prog (11–14) | 305 | 1,046 | 1 case | 0 | **0** |
| progkeep (31–34; only truth-preserving ops) | 340 | 960 | 0 | – | **0** |
| dep (11, 12; K = cap:Y>rel, ops in Y's world) | 32 | 117 | 0 | – | **0** |

- The base-mode wrong answers *before* any operation (8 cases) all have |H| = 3 > horizon 2. That
  is outside the documented open-world-within-horizon assumption (I2).
- The one post-operation prog case: H's guards were not in the space, and the operation made the
  teacher's own earlier example false under H.
- I re-ran my older tool (`adversarial2.py`, mode grow, 82 cases). It reported 1 case, which that
  tool does not classify; the classified harness above supersedes it.

### N1 (Medium, programs mode): an S1 re-acquisition with no candidate leaves the version qualified, without a re-scan

```
python3 -m packetlm.engine R.json --programs --answers \
  'fact e0 ra e1' 'fact e0 ra e2' 'fact e1 k cb' 'fact e1 ra e2' 'fact e1 rb e1' 'fact e2 k ca' \
  'fact e2 rb e4' 'fact e3 ra e2' 'fact e3 ra e4' \
  'example kk: e4 -> e4' 'complete e4' 'example kk: e2 -> e2' 'complete e2' 'example kk: e1 -> e1' \
  'complete e1' 'example kk: e3 -> e4' 'complete e3' 'example kk: e0 -> e0' 'complete e0' \
  'show kk' 'fact e3 ra n2' 'show kk' 'what is e3 kk'
→ v1 prog:not:ra:e4|rel:ra>rel:rb qualified
  recorded e3 ra n2                       (inside e3's closure: `complete e3` retracted)
  v1 prog:not:ra:e4|rel:ra>rel:rb qualified          <- unchanged
  e3 kk e4 [no construction for kk]                  <- qualified
```

- **Mechanism:**
  1. The retraction and the S1 growth both re-acquire `kk`.
  2. With `complete e3` gone, the guard space for `kk`'s observations is data-dependent again, and
     it does not contain `not:ra:e4`.
  3. `_acquire_programs` returns `result: none` (hypotheses `candidate: None`).
  4. Nothing touches the current version: it is still supported, so the M1 review does not suspend
     it, and its status stays `qualified`.
- **Under the engine's own rule** (the same state, re-acquired with the guard space set to every
  pair on the component), the result is `provisional`, with 3 blockers: `not:ra:e4|rel:k`,
  `not:ra:e4|rel:ra` and `not:ra:e4|rel:ra>not:k:ca`.
- **Reach:** 24 of 497 qualified cases reached this state ("qualified after a no-candidate
  re-acquire"): 2+6 in prog seeds 13–14, and 5+6+4+1 in progkeep seeds 31–34. Prog seeds 11–12
  ran before this metric existed.
- **Search for an honest witness** (`ADV_WITNESS=1`):
  - I searched every program of size ≤ 3 over the full guard space for an H′ that gives every
    observation's value on both the old and the new facts and disagrees with a current qualified
    reply. I found **none** in the 16 stale states.
  - So no wrong answer is demonstrated. The problem is that the status claim is not backed by any
    scan, and G53 §2b says the version "is re-acquired, which re-runs the scan on current facts".
- **Not affected:**
  - base mode: its hypothesis space does not depend on `complete`, so a supported current version
    is always re-found;
  - any G53/G45 number.
- **Suggested fix:** when a re-acquisition triggered by growth or retraction does not return the
  current version as a candidate, cap the current version at provisional. Alternatively, run the
  exact scan on the current seq with its own guards added to the space. Add a check from the repro
  above.

## 4. Priority 3: `--bounded` exactness and the skip rule

**G53 rerun** (`python3 benchmarks/g53.py --out g53v --comp-seeds 121,125 --unrel-seeds 131,136`, at
050bebd; the tree was dirty only with `docs/verification/`):
- Guards: all true.
- **The reply-stream SHA-256 of every arm on every rerun seed equals the registered receipt's:**
  - 18/18: C, Cb, Bb, Pb and Fb on 121 and 125; C, Cb, Bb and Pb on 131 and 136;
  - Cb = C on all 4 seeds.
- Whole-process CPU per arm and seed is within about 5% of the registered values (the box was loaded).

| contrast | registered, all 7 seeds | registered, same 2 seeds | my rerun, 2 seeds |
|---|---|---|---|
| comp Cb+maint ‖ C+maint (M) | +0.534 [+0.519, +0.551] | +0.530 | +0.512 [+0.496, +0.527] |
| comp Cb+maint ‖ Bb (L1) | −0.885 [−0.981, −0.790] | −0.802 | −0.964 |
| unrel Cb+maint ‖ C+maint | +0.010 [−0.004, +0.023] | +0.002 | +0.001 |
| unrel Cb+maint ‖ Bb (L3) | −5.065 [−5.456, −4.666] | −4.605 | −5.293 |

- **Registered A values, exact.** The pinned instrument (`/workspace/vendor/learning-amortization`,
  70297af, clean, 5000 resamples) run on `docs/evidence/g53/*_total.csv` reproduces all 9 registered
  A values and intervals to 4 decimals.
- **Cost ratios check:** 0.47, 1.89×, 1.16×, 1.20×, 3.03× and 6.06× all equal 1 − A.
- The Bb contrasts move most between runs (I3), but no decision changes.

**Skip rule** (`_fc_requalify`, bounded and not programs):
- **When it skips:** the re-acquire is skipped only if the version is qualified, the new judgment
  leaves it `supported`, and `basis` is unchanged. `basis` covers the fact epoch, `primitives(name)`,
  the observations, `deepen` and `use_library`.
- **Why that is sound:**
  - The judgments are monotone. A closed judgment equals the open one on supported marks, and it
    can only turn undetermined into contradicted (for values, `!none` and `!several`).
  - So the candidate (shortest supported) and the supported set are unchanged, and the blockers can
    only shrink.
  - Every fact change, including derived `cap:` facts and removals, bumps `fact_epoch`.
  - Retraction only follows a fact change.
  - Dependency status changes either:
    - change `primitives` (under `--qualified-library`), or
    - demote the dependent through L1, so it is no longer qualified and no longer skippable.
  - `qualified_library` reaches the basis through `primitives`. Programs mode is excluded.
- **Uncovered process flags:** `operators`, `answers`, `activation` and `geometry` are not in the
  basis. They are fixed per arm in every harness. A process re-opened with different flags is an
  untested edge (I4).
- **Differential test** (`bounded_diff.py`). Random base sessions on several capabilities, with
  facts, examples (including `!none` and `!several`), `complete`, `retract`, `correct`,
  `investigate`, `requalify` and `what is`, and random save/re-open. After every line, I compared
  each reply and each capability's (current, status, seq):

| flags | sessions | lines | skips taken | sessions differing |
|---|---|---|---|---|
| none (seeds 21, 22) | 800 | 36,852 | 363 | **0** |
| `--qualified-library` (23) | 300 | 14,317 | 107 | **0** |
| `--operators` (24) | 300 | 14,512 | 77 | **0** |

- **Sensitivity of this test** (60 sessions each):
  - it detects `g53_skip_ignores_basis` (8 sessions differ), `g53_memo_key_ignores_primitive` (23)
    and `g53_sparse_conflict_ignored` (12);
  - it does not detect `g53_index_drops_primitives`, which is killed by the g44 check.

## 5. G51 metric corrections (G1/G2 of cdb4828)

I recomputed each figure with the pinned instrument on `docs/evidence/g51/*_total.csv`. All are
correct.

| corrected figure | registered A | 1 − A |
|---|---|---|
| L1: 3.87× (215.8 / 55.7 s) | C+maint ‖ B = −2.872 | 3.87 |
| L2: 1.77× | C+maint ‖ P+maint = −0.774 | 1.77 |
| L3: 6.08× (74.8 / 12.3 s) | unrel C+maint ‖ B = −5.080 | 6.08 |
| unrel without maintenance: −1.15 [−1.18, −1.12], 2.15× | C ‖ B = −1.148 [−1.178, −1.116] | 2.15 |

- `docs/G51.md` and the ledger mark each correction as made after verify-cdb4828, and the decisions
  are unchanged.
- I did not re-check the PR #1 description; I made no GitHub API calls.

## 6. Timeline vs receipts

| time | event | git state | seeds |
|---|---|---|---|
| 01:11:51 | cdb4828 committed | – | – |
| 01:28:13 | dev run before S1 (`g53_dev_receipt_pre_S1.json`) | cdb4828, 6 dirty paths | dev 951–954 |
| 01:57:20 | dev run after S1 (`g53_dev_receipt.json`) | cdb4828, 11 dirty paths | dev 951–954 |
| 02:04:48 | **1932326 committed**: pre-registration | – | – |
| 02:04:54 | registered run started (`g53_receipt.json`) | HEAD 1932326, porcelain **empty** | 121–127 / 131–137 |
| 02:15:54 | 050bebd committed: results | – | – |

- The profile seeds (941–943, 951, 953) and the dev seeds are disjoint from the registered seeds.
- Between 1932326 and 050bebd, `docs/G53.md` changed only in its Results section. The rules M,
  L1, L2 and L3, the arms, the seeds and the guards are unchanged.
- An 11-minute run fits the receipt's CPU totals (about 730 s over 8 workers).
- The G53 sealed-token registry was written after the run, in 050bebd. Nothing taught on those
  tokens in between, since G53 has no teaching sessions.

## 7. Findings by severity

- **High:** none.
- **Medium:**
  - **N1.** In programs mode, a version stays `qualified` after a growth or retraction
    re-acquisition that returns no candidate. Repro and fix are in §3. Under the engine's own rule
    it has blockers. No honest wrong answer was found, and no registered number is affected.
- **Low:**
  - **L1.** `docs/G45.md` criterion 5 still reads "identical". The restatement is documented only
    in G53.md §2b and the ledger. Annotate G45.md.
  - **L2.** The restated t5 trusts the engine's `evidence.blocking` count rather than re-deriving
    the blockers. That is acceptable given the scan checks elsewhere, but worth one line in G45.md.
  - **L3.** "The gap narrows from 3.87× (G51) to 1.89×" compares across experiments: different
    seeds, an engine with S1/L1, and a bounded Bb. It is not a registered contrast, so present it as
    descriptive.
- **Info:**
  - **I1.** S1 demotion is per version. In G45, the blockers differ only at layer-1 entities, while
    the re-asked layer-0 answers are uncontested. This is conservative.
  - **I2.** Base-mode wrong qualified answers occur only with |H| > horizon. This is the documented
    assumption.
  - **I3.** The Bb contrasts are the most load-sensitive. On 2 seeds, my rerun under load gave L1
    −0.96 and L3 −5.29, against −0.80 and −4.60 for the registered same-seed subset. The signs and
    decisions are unchanged.
  - **I4.** The skip basis omits the `operators`, `answers`, `activation` and `geometry` flags. They
    are constant per arm in every harness.

Branch: `verify-050bebd` (this file plus `tools_050bebd/`).
