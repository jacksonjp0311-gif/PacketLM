# Independent verification of g60h-hdc at 69b5b26 (G60H HDC prototype; registered at b54de78)

Verifier clone `/workspace/verify-69b5b26`, branch `verify-69b5b26`, made from 69b5b26 (detached worktree of 69b5b26 at
`/tmp/v69/mutclone` for mutations). The builder's clone `/workspace/g60h` was only read (artifact timestamps and receipts),
never written. Every CPU-heavy job ran through `tools_69b5b26/guard.sh` (waits while `/workspace/REGISTERED_RUN.lock`
exists); the lock was never present during my work (13:00–13:45 EST). Instrument `/workspace/vendor/learning-amortization`
at 70297af, clean. `packetlm/hdc/` is identical at b54de78 and 69b5b26 (engine sha 47d0fb94…); no existing engine file changed
since 80cfb17. Tools and outputs: `tools_69b5b26/` (outputs under `tools_69b5b26/out/`), notes in `NOTES.md`.

## Verdict

**Everything registered reproduces exactly, and the registered rule was applied correctly: margin 1 PASS, margin 2 HOLD.**
But the margin-1 PASS **does not support the claim "first positive learning amortization" in the sense G59 tested.** One
**High** finding: the +1 uniqueness check is the same rule for both arms but not the same certificate. C checks in its own
language, where a whole library capability counts as one step. On the same evidence, about 20% of C's final `qualified`
programs would be **ambiguous** under B's rule in the base language, and also under the G59 horizon of 5 base steps, and even
under C's own language at horizon 5. These are 49/249 on comp, 55/249 comprep, 43/334 mixed and 220/999 long. They are exactly
the deep tasks (comp: 31/63 of depth-4 tasks, 18/21 of depth-5 tasks). **77% of C's task-CPU saving on comp comes from them.**
When C must also pass B's certificate (an unregistered counterfactual run, same protocol, 4 workers), comp A drops to
**+0.070 [+0.003, +0.142]**, and the library term to **−0.005 [−0.074, +0.070]**. The gate is then **HOLD**: mixed fails Q4b.
Every one of those 49/220 programs is correct (base = hidden, 0 wrong-qualified). So the library works as a learned prior
that is always right on these curricula, not as a uniqueness certificate. G60H §2 discloses the asymmetry ("description-length
prior") but does not quantify it. The "conditional" reading is therefore right in direction and understated in size: what is
shown is **positive amortization under a weaker, library-relative certificate.**

Also: one Medium (attribution: the HDC codes are not load-bearing, so the step-cost win cannot be credited to hypervectors as
such), five Low and several Info items. No leakage. B starts every task empty. Charging is equal. All counts reproduce.

## 1. Fairness of "qualified" at +1

**Rule.** `HEngine.acquire`: at the first depth n with a supported tuple there must be exactly one; then levels up to
n + margin are searched, and any new supported tuple blocks. `offered()` gives relations, plus library capabilities when
`library=True`. A depth-4 target is found at n = 1 or 2 in C's language, so C's "+1" covers 2–3 primitive steps. B's "+1"
covers base depth 5. The same rule therefore buys very different certificates.

**Shadow audit** (`tools_69b5b26/shadow_serve.py`, `shadow_run.py`, `shadow_an.py`). Every `acquire()` of every
registered job (all 5 curricula × 7 seeds × Ch/Bh/Ph, both margins: 210 jobs) is re-run on deep copies of the pre-call
engine under three certificates. The real engine is never touched. **The 105 + 105 jobs reproduce the registered reply
streams and final-state hashes byte for byte.** Certificates:
B1 = base language, margin 1 (B's rule on C's evidence); B5 = base language, every depth ≤ 5 (G59 horizon);
C5 = the arm's own language, every depth ≤ 5. Final status per task:

| margin | curriculum | Ch final qualified | B1 / B5 say **ambiguous** | C5 says provisional | Bh or Ph qualified that B5 rejects |
|---|---|---|---|---|---|
| 1 | comp | 249 | **49** | 49 (same tasks) | 0 / 240 |
| 1 | comprep | 249 | **55** | 55 | 0 / 239 |
| 1 | unrel | 168 | 0 | 0 | 0 |
| 1 | mixed | 334 | **43** | 43 | 0 / 272 |
| 1 | long | 999 | **220** | 220 | 0 / 968 |
| 2 | comp / comprep / mixed / long | 246 / 242 / 330 / 982 | 10 / 11 / 9 / 43 | same | 0 |

- **The reverse never happens.** B's and P's margin-1 certificates are as strong as the G59 horizon (0 disagreements with
  B5). Only C passes checks the other arms would fail.
- **Are any +1 answers wrong?** No. All 49 / 55 / 43 / 220 programs equal the hidden program (`acquired`). 0 wrong-qualified
  sealed or transfer answers in every arm. Sealed answers not marked ok are `unknown` replies on tasks left ambiguous.
  The prior is right because each curriculum builds targets as compositions of earlier tasks. No gate curriculum contains a
  decoy, where a library composition fits the examples but is not the target (unrel has nothing to reuse). So Q2's 0 is not
  evidence that the weaker certificate is safe in general.
- **Where the saving comes from** (`flag_strata.py`). On comp the flagged tasks hold 1.715 s of Bh's 3.08 s task CPU. C
  spends 0.295 s on them. That is 1.42 s of C's 1.85 s total task saving (77%). On long: 6.23 of 11.38 s for Bh, 1.31 s for
  C. C also needs fewer teacher rounds: 192 investigate questions vs Bh's 302 on comp at margin 1 (281 at margin 2). It stops
  asking once its own rule says `qualified`.
- **Counterfactual A, substitution** (`subst.py`, `substP.py`; registered files). Charge Ch the Bh (or Ph) cost on the
  flagged tasks. comp A(Ch+maint‖Bh) = **+0.089 [+0.040, +0.168]** (Ph cost: +0.095 [+0.028, +0.178]); library term
  **+0.028 [−0.038, +0.111]** (+0.034 [−0.016, +0.110]); long +0.025 [−0.001, +0.053]; mixed +0.062; comprep +0.059.
- **Counterfactual A, equal-certificate run** (`cc_serve.py`, `rerun.py cc`, all curricula and seeds, 4 workers,
  untouched B and P). After C's rule says `qualified`, B's base-language rule must agree on the same evidence. The base
  search is charged. If it disagrees, C goes to ambiguous or provisional, with B's live set, so the teacher asks what B would
  ask. Result: comp **+0.070 [+0.003, +0.142]**, library term **−0.005 [−0.074, +0.070]**, P‖B +0.123; comprep +0.080
  (lib +0.110); mixed **+0.019 [−0.033, +0.069] (Q4b fails)**; long +0.078 (lib +0.030); unrel −0.736. Strata on comp:
  −0.11 / −0.16 / +0.09 / +0.31. Gate **HOLD**. Correctness is unchanged: sealed correct 1124 vs Bh 1098, 0 wrong-qualified.
  Caveat: this C pays for its own search *plus* B's. A smarter certificate (meet-in-the-middle, as G60H §12 suggests) could
  cost less, so this is an upper bound on what B's certificate costs C. It is not proof that the library cannot pay.
- **Timeline: was +1 chosen before the results?** Yes, as far as the files show. The first dev artifact
  (`/workspace/g60h/artifacts/g60h_dev1`, started 12:40:18 EST) ran engine sha 5154308c…, which equals 7f06658 (12:41:01),
  where n+1 is hard-coded. The `margin` parameter and the margin-2 robustness run came later: dev_m2 started 12:45:25 and
  showed HOLD. Registration at b54de78 was 12:51:01; the run started 12:51:10. So the primary horizon was not picked after
  seeing margin 2 fail, and margin 2 was registered and reported honestly. I cannot rule out earlier runs that left no
  artifacts (the 12:00–12:40 build session is not reviewed). n+1 is weaker than G59's horizon of 5, and it was chosen
  without any comparison. G60H says so itself.

## 2. Leakage and equal treatment

- `packetlm/hdc/` never reads hidden programs, shapes, layers or sealed lists (grep). The teacher sends only facts,
  `complete` and examples. Sealed subjects get `unanswered` (g46 `_arm_body`). Ω = subjects of s1's relations in the
  order told. That is generic, and identical for every arm.
- **B starts each task empty.** g46 gives B a new state path per task, `B_{fi}_{ti}.json`. The HDC server closes the old
  path and builds a new `HEngine()`. No module-level caches exist (`codes.code` is a pure hash). B is re-told all facts each
  task: lines 54,790 vs P's 11,465 on comp. That cost is what P‖B measures.
- **Equal charging.** One process-CPU accounting for all arms (`cpu_total_s`). Validation and snapshots are charged to every
  arm. `+maint` adds the correction/transfer/retention families for C and P, the same way. The flag sets differ only by
  `--no-library` (g56 BASEF, plus `--margin`).
- Only C (`library=True`) gets the asymmetric certificate in §1. It is part of the registered design, not a leak.

## 3. Accuracy

- **0 decode errors reproduced**: part S 0/1493 (hC) and 0/345 (hP) from `runs.tgz`; gate 0/3984 per margin.
- **The replay is legitimate.** `g60h_decode_audit.py` reran the registered jobs. All 105/105 reply streams per margin equal
  the registered streams. My shadow runs also reproduce 210/210 streams and final states. The engine is deterministic, so
  the counters are those of the registered runs.
- **What the counter measures.** It counts unique capability decodes. `steps()` memoizes per (cap, version), and every
  decode is compared with the exact journal copy, falling back to it. Offered capabilities are filtered by the exact
  per-relation list. So the hypervectors never decide an answer. An error costs CPU only, or goes undetected (L1).
- **Capacity spot check** (`smallK.py`; comp 401 and long 441, Ch, margin 1). At K/L = 32/64, 16/16, 8/16 and 8/64 the reply
  streams equal the registered ones, with 0 decode errors. At 4/64, long 441 **diverges**: one sealed answer is lost (647 vs
  648), with every in-run counter still at 0. This agrees with the registered sweep (K = 4: 268 key collisions at 10⁵) and
  shows the counters miss key collisions and signature errors. Even 8/16 shows 0 in-run errors, because the prim codebook
  is small and sequences are 1–3 primitives. In-run "0 errors" therefore says little about margin to capacity; the sweep
  carries that evidence.

## 4. Reproduction from the registered files (pinned 70297af)

- `repro.py`: for both margins and all 5 curricula, CSV bytes are equal to the registered `.csv.gz`. **80/80 primary and
  secondary instrument first lines are equal**, and so are the resource contrasts. Work split, maintenance share,
  strata, censoring, rate ratio, in-run and emergence dicts are identical. So are outcomes, and so is the gate dict (m1
  PASS, m2 HOLD). Values: comp +0.5497 [+0.5232, +0.5715]; library term +0.5194 [+0.4811, +0.5516]; A_work +0.666;
  ρ 1.349; strata +0.111 / +0.152 / +0.628 / +0.867; long o/s 0.640, β +0.0003.
- `repro_scale.py`: every part-S summary entry is equal: α_task(hC, 16k→64k) **0.0038 [−0.0394, 0.0653]**, α_charged-prop
  **0.0147 [−0.0316, 0.0765]**, α_work 0, hP 0.074, all local exponents, and decodes.
- **Partial rerun, byte-identical**: all 105 jobs per margin, as part of the shadow runs (reply streams and final states).
- **Timed reruns** (`rerun.py reg`, 4 workers, quiet box): m1 **PASS**, comp +0.565 [+0.535, +0.591], lib +0.497, strata
  +0.21 / +0.19 / +0.64 / +0.88; m2 **HOLD**, comp −0.023 [−0.093, +0.031], only depth 5 qualifies. Noisy secondaries:
  P‖B comp +0.18 (registered +0.11); long o/s **0.28** (registered 0.64); unrel Bh total 0.38–0.47 s (M2 and §6).

## 5. Tests

g44 **191/191** (failed []), G45 **18/18**, suite **11/11 modules, 279 checks, 0 failed** (smoke 10/10), `packetlm.hdc.test_hdc`
**13/13**. Builder mutations (`/workspace/g60hdev/mut.py`, run on a worktree): **11/12**. The survivor `investigate_first` is
**truly equivalent**. `score_b` starts at 0 and is set only together with `best`, to a score > 0. So `best is None` ⇔
`score_b == 0`, and `score > score_b or (best is None and score)` reduces to `score > score_b`. My five extra mutations
(`mut_extra.py`): `self_not_excluded`, `omega_empty` and `several_unchecked` are killed. **`ambiguity_ignored` survives**:
with several supported tuples, the engine qualifies the first one. **`margin_ignored` survives**: it is equivalent at margin 1
only, and margin ≥ 2 is untested (L2).

## 6. The B unrel CPU oddity at margin 2 (0.606 vs 0.378 s)

**Timing noise, not a code-path difference.** Bh unrel evaluations are identical at both margins (11,547): margin never
matters on unrel. Reply streams equal. One task carries it: seed 422, family 20, task 0, **120 ms** process CPU (`cpu_s`
0.1196) for 117 evaluations, where the same task costs about 3 ms. Seeds 423–425 are also up 1.5–2×. The m2 pool ran about
12:53:40–12:54:10, and the load log shows other agents' processes. My reruns give Bh unrel 0.467 s (m1), 0.382 s (m2) and
0.395 s (cc run); the largest single task is 5.8 ms. Effect: it pushes margin-2 unrel A down by roughly 0.1 to 0.2. It
cannot flip any verdict (Q3 passes either way; margin-2 HOLD comes from Q1, Q4a and Q4b).

## 7. Is "positive at +1, conditional" accurate? What can and cannot be claimed

**Can be claimed (verified):**
- Under the registered margin-1 rule the gate is PASS. It reproduces from the files and in a timed rerun (+0.55 to +0.56 on
  comp). Accuracy and kill criteria hold, and part S is bounded (α 0.004).
- The HDC prototype's per-step cost does not grow with unrelated knowledge (hash-keyed fact memory, identical work at every
  N). Its evaluations cost about 1.3–1.9× B's (G59: 13–30×).
- With a learned library used as a prior over hypotheses, C reaches correct, qualified programs with fewer examples and less
  search than B on compositional curricula. Every such program was correct here.

**Cannot be claimed:**
- "First positive learning amortization" in G59's sense (exact answers plus a uniqueness certificate comparable across
  arms). With B's certificate imposed on C, the library term is about 0 on comp (−0.005 [−0.074, +0.070]) and the gate is
  HOLD. At margin 2 it is HOLD too.
- That HDC / hypervectors cause the gain (M1).
- That the weaker certificate is safe beyond curricula whose targets are compositions of earlier tasks (L4).
- Cross-engine statements such as "ρ 12.9 → 1.35" as the effect of the representation: they compare a different search, a
  different certificate and different seeds.

**Suggested wording:** "G60H: under a library-relative uniqueness check (+1 primitive in each arm's own language), C shows
positive amortization (comp +0.55). About 20% of C's qualified programs, carrying 77% of its saving, would be ambiguous
under B's base-language check. With B's certificate imposed, the library term is ≈ 0 (−0.005 [−0.07, +0.07]) and the gate
holds (HOLD). All of C's programs were correct, so the library acts as an accurate learned prior, not as a cheaper
certificate. Positive amortization with an equal certificate remains open; the next step is a certificate whose cost does
not grow with the library (G60H §12)."

## Findings by severity

**High**
- **H1. Unequal certificate.** The margin-1 PASS and the +0.519 library term depend on C qualifying programs that B's rule,
  the G59 horizon and C's own horizon 5 all call ambiguous. That is ~20% of C's qualified tasks, mostly depths 4–5, carrying
  77% of the comp saving. With an equal certificate: comp +0.070 [+0.003, +0.142], library term −0.005 [−0.074, +0.070],
  gate HOLD (mixed Q4b fails). Substitution gives the same picture (+0.089; library term +0.028 [−0.038, +0.111]). The
  registered verdict stands by its own rule, but the headline and the ledger must not present it as the first positive
  amortization comparable to G59. Restate as in §7.

**Medium**
- **M1. Attribution to the representation is untested.** Fact memory is a Python dict keyed by a deterministic code of
  (s, r), so functionally a hash table. Capability offers are filtered by exact per-relation lists. Capability decodes are
  checked against the exact copy (§3). The step-cost result plausibly comes from hash-keyed memory plus the deduplicating
  tuple DP, not from hypervector algebra. No ablation with plain dicts and sets was run. "The fixed-width representation
  removed the cost-per-step term" should read "the new engine (hash-keyed memory, deduplicated tuple search) removed it".
- **M2. Several secondary numbers are within run-to-run noise.** Long o/s 0.64 registered vs 0.28 in my rerun; P‖B comp
  +0.11 vs +0.18 (so the "failed prediction" on P‖B is weak); unrel Bh 0.38–0.61 s. 4-worker co-scheduling, as in G59 L1.
  Report o/s with an interval or across reruns, not as 0.64.

**Low**
- **L1. In-run accuracy counters are incomplete.** Only capability decodes are counted. Signature cleanup errors and
  bound-key collisions are not detected. `counters["collisions"]` is initialized and never incremented. At K=4, L=64 an
  answer was lost with every counter at 0. Irrelevant at the registered K=32, L=64 (the sweep shows 0), but the kill
  criterion's "decode errors" does not cover every approximation failure. G60H §3 notes the key-collision part.
- **L2. Test gaps.** The `ambiguity_ignored` mutation survives, so the ambiguous → `ambiguous` path is not unit-tested,
  though it is exercised in the gate. Margin ≥ 2 is untested. The builder's mutation runner lives in `/workspace/g60hdev`,
  not in the repo.
- **L3. Decode counters were obtained by replay.** Legitimate (105/105 identical streams per margin), but a harness gap, as
  stated. The receipts should keep the `cum_*` counters.
- **L4. Q2 does not test the prior's safety.** 0 wrong-qualified holds because every flagged program is the target. The
  curricula never offer a library decoy. A decoy curriculum would be needed before the weaker certificate is trusted.
- **L5. The §6 oddity** is timing noise (one 120 ms task). It does not affect the verdicts.

**Info**
- I1. All registered numbers reproduce exactly: 80/80 contrasts, the gate dicts, part S, strata, rate ratio and
  decomposition. Byte-identical reruns of all 210 jobs.
- I2. Counts: g44 191/191, G45 18/18, suite 279/0, HDC 13/13, mutations 11/12 (the survivor is equivalent).
- I3. Timeline consistent with margin 1 being fixed before any result. Margin 2 registered before the run and reported.
- I4. No leakage; B starts empty; equal charging.
- I5. Margin-2 rerun: HOLD, comp −0.023, only depth 5 qualifies (+0.33), as registered.

## Reproduce

```
cd /workspace/verify-69b5b26   # verifier tools only; packetlm/ and benchmarks/ unchanged from 69b5b26
python3 tools_69b5b26/repro.py                    # §4 gate reproduction (≈3 min)
python3 tools_69b5b26/repro_scale.py              # §4 part S
SHADOW_C5=1 python3 tools_69b5b26/shadow_run.py 1 /tmp/sh_m1 comp:401-407:CBP,comprep:411-417:CBP,unrel:421-427:CBP,mixed:431-437:CBP,long:441-447:CBP
python3 tools_69b5b26/shadow_an.py /tmp/sh_m1; python3 tools_69b5b26/subst.py /tmp/sh_m1 1
python3 tools_69b5b26/rerun.py cc --out v69_cc_m1 --margin 1    # equal-certificate counterfactual
python3 tools_69b5b26/rerun.py reg --out v69_reg_m1 --margin 1
python3 tools_69b5b26/smallK.py; python3 tools_69b5b26/mut_extra.py <worktree>
```
