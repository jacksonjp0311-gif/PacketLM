# Independent verification of PacketLM @ cdb4828 (G52 fixes, G52 run, G51 amortization)

- **Verifier:** an independent Grok Bot verifier. The method is the same as for `VERIFY_b2bb9b8.md`.
- **Date:** 2026-11-27, about 01:13–01:45 America/New_York.
- **Target:** `g44-canonical-engine` @ `cdb4828`. The commits after b2bb9b8 are:
  - `b21cdd2` / `c4165e8`: G50;
  - `7dd716a`: G52 pre-registration plus the H1/M1/M2 fixes;
  - `fc2cb3e`: G52 results;
  - `ad1bc03`: G51 pre-registration;
  - `6b6cda4`: G51 results;
  - `cdb4828`: sealed registry.
- **Environment:** `GITHUB_TOKEN` and `GH_TOKEN` were unset, and `/workspace/PacketLM` was not
  touched.
- **Verifier tools:** they are in `docs/verification/tools_cdb4828/` (`adversarial.py`,
  `adversarial2.py`, `mybrute.py`). The b2bb9b8 tool (`tools_b2bb9b8/soundness.py`) was rerun
  unchanged against this engine.

## Verdict

**Everything registered reproduces:**
- all counts;
- G52 on seeds 551 and 555: **12/12 reply hashes byte-identical**, and the same 9/11 with FC2
  and D1 failing;
- the D1 attribution, which I confirmed on the pre-fix engine (c4165e8);
- G51:
  - my 2+2-seed rerun has **18/18 runs behaviourally identical** to the registered raw data,
    with CPU within about 5%;
  - the committed CSVs are byte-identical to CSVs regenerated from the raw data;
  - every registered A value and interval reproduces exactly from the committed CSV with the
    pinned instrument.

**The H1/M1 fixes hold:**
- my soundness tool reproduces G52's table exactly;
- 8 new adversarial honest-teacher searches found **0** wrong qualified answers.

**However, one gap remains in the qualification scope (S1).** A qualified version is not
re-checked when told facts grow **inside** its recorded domain. I constructed a 4-fact honest
example in which `complete` leads to a wrong **qualified** answer. M2 scopes by entity
membership only.

**G51 misreads the instrument's metric in its prose (G1):**
- "≈ 18×" should be **3.9×**;
- "≈ 2.2×" should be **1.8×**.

No registered threshold or number is affected by either issue.

## 1. Counts (cdb4828, fresh processes)

| command | claimed | reproduced |
|---|---|---|
| `python3 -m packetlm.g44_test` | 124 | **124, failed []** |
| `python3 -m packetlm.suite` | 212 | **212, 0 failed, 11/11** |
| `python3 -m packetlm.g45_test` | 18/18 | **18, failed []** |
| `python3 -m packetlm.mutations` | 69/69 | **69/69, baseline_failed [], 0 crash-only** |

Each of the five new mutations is killed by the intended checks:
- `h1_guard_space_data_dependent`: by the three `h1_*` checks;
- `h1_gap_ignored`: by `h1_guard_gap_caps_at_provisional`;
- `h1_no_identity_guard`: by `h1_identity_expressible_under_complete`;
- `m1_no_review_on_complete`: by `m1_complete_after_example_reviews_version`;
- `m2_scope_ignored`: by `m2_qualified_scoped_to_domain`.

## 2. H1 fix: soundness

**Code.**
- When any observation of the capability is at a `complete` subject, the guard space becomes
  every (Q, T) pair told about a node of the acquisition component, plus one absent pair.
  - `not:` on the absent pair is the identity filter.
  - If more than 8 pairs exist, the status is capped at provisional (`guard_gap`).
- The argument in G52.md holds for guards:
  - a pair absent from the component is constant on it, so an `is:` guard on it empties its
    clause and a `not:` guard on it is the identity;
  - relations with no subject in the component are empty on it;
  - every node a program visits from the domain stays in the component.
- **Remaining assumption: offered capabilities.** A capability is offered only if it has an
  observation in the component, and it is offered at its *current, pinned* version. A qualified
  capability can therefore be pinned to a **provisional** dependency (`_set_status` propagates
  only suspension). This is L1 below.

**My b2bb9b8 tool, rerun on this engine** (`tools_b2bb9b8/soundness.py`). It is identical to
G52's table:

| run | cases | qualified | wrong qualified in the domain | wrong qualified on a new world |
|---|---|---|---|---|
| seed 11, `complete` | 231 | 77 | 0 | 0 |
| seed 21, `complete` | 240 | 56 | 0 | 0 |
| seed 11, open-world control | 231 | 1 | 0 | 0 |
| seed 12, dependency | 104 | 31 | 0 | 0 |

**New adversarial searches.** The tools are `adversarial.py` and `adversarial2.py`. The teacher
is honest throughout: every fact is told, true values / `!none` / `!several` are given, and
`complete` follows every answer.

| mode | what it attacks | cases | qualified | wrong qualified |
|---|---|---|---|---|
| fullspace (seed 525679) | hidden program over **every** pair present in the world, entity-valued pairs included, plus `is:`/`not:` on an absent pair; small worlds so the full space fits in 8 | 70 | 60 | **0** |
| depsep (5226911) | Y taught with `complete` on world A; K = `cap:Y>rel:r` taught on a disjoint world B, where cap:Y is not offered | 48 | 1 | **0** |
| depwrong (525436) | Y taught from 1 example with no `complete`, so often provisional or wrong; K = `cap:Y>rel:r` with `complete` | 66 | 20 | **0** |
| depprefix (77) | as depwrong, but K = `rel:s>cap:Y>rel:r`, which cannot be inlined around a recursive Y | 84 | 17 | **0** |
| depsame (5216926) | b2bb9b8's dependency mode with investigate | 63 | 16 | **0** |
| depqual (526703) | depsame with `--qualified-library` | 56 | 17 (6 using cap) | **0** |
| grow (31) | K qualified, then random told facts at unobserved domain nodes outside every closure | 130 | 108 | **0** |
| depgrow (32) | Y on world A; world B linked B→A; K = `cap:Y>rel:r` on B | 23 | 0 | 0 (weak: nothing qualified) |

The random searches found nothing. The constructed case below did.

### S1 (High, mechanism; registered numbers unaffected): a qualified answer goes stale when facts grow inside the recorded domain

M2 stores the domain's **entities**. A told fact whose subject is an unobserved domain entity
outside every closure triggers:
- no retraction;
- no re-scan;
- no demotion.

The scan's uniqueness, however, was decided on the facts **as they were** at acquisition.

```
python3 -m packetlm.engine S.json --programs --answers \
  'fact a r1 c' 'fact c r1 c' 'fact c r2 c' 'fact m r1 c' \
  'example hq: a -> c' 'complete a' 'example hq: c -> c' 'complete c' \
  'what is m hq' 'fact m r3 z' 'what is m hq'
→ m hq c            (qualified; domain [a, c, m], guard_gap 0)
  recorded m r3 z
  m hq c            (still qualified, NOT [provisional])
```

- **Honest truth:** `not:r3:z>rel:r1`, size 2, a grammar program.
- **Before** `m r3 z` is told, r3 is absent, so this program is behaviourally identical to
  `rel:r1` on the domain. Qualifying `rel:r1` was therefore sound.
- **After** `m r3 z` is told, the truth at m has no value, yet the engine still answers `c`,
  qualified.
- Both `complete` statements remain true, because m is in neither closure.
- **Open-world control:** the same pattern stays provisional. The issue comes from
  closed-world qualification.

**Impact on the registered runs:** none.
- G52 F qualifies 0 tasks.
- In G51 and G50-B, wrong qualified answers on transfer are 0 for every arm, and retention
  changed 0.
- My random `grow` search (0/108) shows it needs a hidden program whose difference only appears
  once new facts arrive.

**Fix options:**
- demote a qualified version to provisional, or re-scan it, when a told fact's subject is in its
  stored domain;
- or store a fact fingerprint of the domain with the version.

Add a check and a mutation.

## 3. M1 and M2 fixes

**M1: fixed.** My b2bb9b8 reproductions now give:
- **base mode:** `rel:p+rel:p` is suspended after `complete x`, and `what is z k1` → `unknown`.
  This holds both with `--deepen=2` and without it.
- **programs mode:** v1 is suspended after `complete x`. The newly told `m` gets `unknown`.

**M2: works as claimed for new entities.**
- New entities and new worlds are answered `[provisional]`.
- My soundness tool shows 0 wrong qualified answers on a new world, against 50 before.
- `requalify` widens the scope (`chat.generic_requalified`).
- It doesn't cover facts that grow inside the domain: S1 above.

## 4. The two restated checks: legitimate

**`fc_less_defined_refuted_qualifies_programs`.**
- I re-ran the old fcw world on the fixed engine. After `complete b` it is provisional with
  guard_gap 0. The blockers include `prog:is:r1:x2>rel:r1`, which is:
  - supported at b (closed);
  - undetermined at a, where the judgment is open;
  - different from the candidate at a.
- That is a genuine alternative, so provisional is correct.
- The new world is provisional without `complete` and qualified with it. The base-mode half of
  the check is unchanged.
- `h1_identity_expressible_under_complete` accepts any non-wrong outcome. That is weak as a
  positive, but adequate as a soundness guard.

**`chat.generic`.**
- `orion` is told after `tail` is qualified, so it lies outside the scanned domain. Under the M2
  rule `[provisional]` is the correct answer.
- The added `chat.generic_requalified` keeps the positive: the answer is qualified after
  `requalify`.

## 5. G52 run (seeds 551 and 555 of 551–557)

- **Command:** `python3 benchmarks/g49.py --seeds 551,555 --out g52v`.
- **Reply hashes:** 12/12 equal the registered raw data.
- **Thresholds:** the same pattern as registered. FC2 fails: F qualifies 0, and every F scan
  has guard_gap 25–67 > 8. D1 fails on seed 555.
- **D1 attribution:** on a c4165e8 worktree, seed 555 R and N asked the identical 6 questions
  (`dmiinw, eqlsqu, wuwwzo, xydmws, qjmqni, edkalf`). Both end suspended on
  `is:nwxtwk:fxbert|rel:szgbal>self`, with depth ≥ 4 at 0/16, the same as the fixed engine. So
  the failure is not caused by the fixes. Confirmed.

## 6. G51 amortization

**Reproduction.**
- **Command:** `python3 benchmarks/g51.py --out g51v --comp-seeds 71,72 --unrel-seeds 81,82`.
  The harness hash and engine hash equal the registered receipt. The instrument is
  `/workspace/vendor/learning-amortization` at `70297af`, clean.
- **Behaviour:** all 18 seed × arm runs are identical to the registered raw data in every
  task's status, program, questions, sealed replies, transfer and retention.
- **Solved, qualified and library-use counts** are identical. For example, comp 72 C has 36
  solved, 35 qualified and 21 using the library; B has 35/35.
- **CPU:** `cpu_total_all_s` is within about 5%. For example, 71:C is 29.6 against 29.9 s.
- **A values (S = 2):**

  | contrast | compositional (mine) | unrelated (mine) |
  |---|---|---|
  | A(C+maint ‖ B) | −2.91 | −5.02 |
  | A(Q+maint ‖ B) | −2.88 | −5.22 |
  | A(C ‖ P) | −0.90 | n/a |
  | A(C+maint ‖ P+maint) | −0.80 | n/a |

  These are consistent with the registered S = 7 values.
- **Contrasts near 0 are within CPU noise:** in my rerun, unrelated A(C ‖ P),
  A(C+maint ‖ P+maint) and A(Q+maint ‖ C+maint) change sign. Report them as "no detectable
  difference" (Info).
- **From the committed data:**
  - `la_export` over the committed raw gz reproduces both CSVs byte-for-byte;
  - the pinned instrument reproduces every registered A_n and interval exactly;
  - unrelated A(Q+maint ‖ C+maint) reports break-even n = 14. That isn't mentioned, but it is
    irrelevant because the interval contains 0.

**Arms and cost accounting audit.**
- **Flags:** C `--answers`; Q `--answers --qualified-library`; B and P `--answers --no-library`;
  F `--answers`. All use `--deepen=5`.
- **B** gets a fresh state per task and is told the family's facts on every task. That cost is
  charged to B.
- **P** keeps a persistent state.
- **F** is frozen in phase B: no teaching, sealed items are still asked, and those tasks are
  censored (120).
- All arms get the same teacher, including `complete`, and the same investigate budget of 4.
- **Task cost** is the sum of `cpu_total_s` over the task's processes.
  - `la_export` splits it into acquisition and execution, where execution is the last
    sealed-ask process.
  - **Maintenance** is the per-family correction, transfer and retention calls, charged only in
    `<arm>+maint` at the family's last task. B has none.
  - Task plus maintenance equals `cpu_total_all_s` for every arm. For example, comp C is
    200.4 + 15.4 = 215.8.
- **Fairness verdict:** fair, and conservative against the persistent learner.
  - B never answers the transfer and retention questions whose cost the `+maint` contrasts
    charge to C, Q and P.
  - That is the pre-registered rule, and it doesn't change the direction of any decision.
- **Thresholds:** unchanged from ad1bc03. The ad1bc03 → 6b6cda4 diff of G51.md only replaces the
  Results placeholder, and `g51.py` is unchanged since ad1bc03.

### G1 (Medium): the G51 prose misreads A_n as a log ratio

The instrument defines **A_n = 1 − C_cont(n) / C_base(n)**: `amortization/metric.py`, and
Definition 5 in its README. So:

| contrast | A | correct cost ratio | stated |
|---|---|---|---|
| comp A(C+maint ‖ B) | −2.87 | **3.87×** (215.8 / 55.7 s) | "about e^2.9 ≈ 18×" (G51.md L1, RESEARCH_LEDGER, PR #1) |
| comp A(C+maint ‖ P+maint) | −0.774 | **1.77×** | "≈ 2.2×" |
| unrel A(C+maint ‖ B) | −5.08 | **6.08×** (74.8 / 12.3 s) | (no ratio stated) |

- The direction and every decision rule (L1–L4) are unaffected.
- But the magnitudes quoted to readers overstate the cost by about 4.6×.

**Fix:** replace "≈ 18×" with "≈ 3.9×", and "≈ 2.2×" with "≈ 1.8×", in G51.md, the ledger and
the PR.

### G2 (Low): proportionality of L3 and of "why the empty-state reference wins"

- On the unrelated curriculum, maintenance is **65%** of C's cost: 48.4 of 74.8 s.
- Without maintenance, A(C ‖ B) is **−1.15** [−1.18, −1.12], against −5.08 with it. I computed
  this; it is not a registered contrast.
- The L3 statement still holds, since both are below 0. But most of its magnitude is
  transfer/retention re-asking that B never does.
- On the unrelated curriculum, the library is used 0 times, and C ≈ P. So "the library adds
  candidate steps, which multiplies the search" explains the compositional gap only.
- Suggest stating this split.

## 7. Timeline vs receipts

| experiment | pre-registration commit | receipt `started` | receipt `head` / porcelain | results commit | gap |
|---|---|---|---|---|---|
| G52 | 7dd716a 01:00:26 | 01:00:32 | 7dd716a / `M benchmarks/g51.py` | fc2cb3e 01:06:39 | 6 min 13 s |
| G51 dev | (none) | 01:06:45 | fc2cb3e / `M benchmarks/g51.py` | (in ad1bc03) | |
| G51 | ad1bc03 01:07:54 | 01:07:57 | ad1bc03 / clean | 6b6cda4 01:11:07 | 3 min 10 s |

- My reruns fit those gaps: G52 took 2 min with 2 seeds, and G51 about 3.5 min with 2+2 seeds
  under load.
- `packetlm/` is identical between 7dd716a and ad1bc03, so G51's engine hash equals G52's.
- The dev receipt's harness hash equals the registered one, so the dev run used the
  ad1bc03 harness.
- The porcelain entry in G52's receipt is the G51 draft, which is not part of the G52 harness.
- **Consistent.**

## Findings by severity

- **High:**
  - **S1.** A qualified version is not re-checked when told facts grow inside its recorded
    domain. The 4-fact honest-teacher reproduction gives a wrong qualified answer. M2 is
    incomplete for this case. No registered number is affected.
- **Medium:**
  - **G1.** "18×" and "2.2×" misread A_n. The correct ratios are 3.87× and 1.77×.
- **Low:**
  - **L1.** A qualified capability can be pinned to a provisional dependency; no status
    propagates. 6 adversarial dependency searches (and depgrow, which qualified nothing) found
    no wrong answer. State this as an assumption, or cap at provisional.
  - **G2.** The magnitude of L3 is mostly maintenance, and the library explanation doesn't apply
    on the unrelated curriculum.
  - **L2.** `h1_identity_expressible_under_complete` accepts any non-wrong outcome. It is a
    guard, not a positive.
- **Info:**
  - the restated checks are legitimate;
  - G51's arms and accounting are fair;
  - near-zero contrasts are within CPU noise;
  - the unrelated Q ‖ C break-even of 14 goes unmentioned;
  - the D1 attribution is confirmed.

## Commands

```bash
cd /workspace/pl-verify && git checkout cdb4828
python3 -m packetlm.g44_test; python3 -m packetlm.suite; python3 -m packetlm.g45_test; python3 -m packetlm.mutations
python3 benchmarks/g49.py --seeds 551,555 --out g52v
git worktree add --detach ../pl-verify-c41 c4165e8 && (cd ../pl-verify-c41 && python3 benchmarks/g49.py --seeds 555 --out d555)
python3 benchmarks/g51.py --out g51v --comp-seeds 71,72 --unrel-seeds 81,82
PYTHONPATH=/workspace/vendor/learning-amortization python3 -m amortization docs/evidence/g51/comp_total.csv --cont C+maint --base B --n 36 --bootstrap 5000
python3 docs/verification/tools_b2bb9b8/soundness.py 300 11 plain   # (verify-b2bb9b8 branch) also 300 21 plain; 300 11 plain open; 200 12 dep
python3 docs/verification/tools_cdb4828/adversarial.py 120 <seed> {fullspace|depsep|depwrong|depsame|depqual|depprefix}
python3 docs/verification/tools_cdb4828/adversarial2.py 200 31 grow; ... 120 32 depgrow
```
