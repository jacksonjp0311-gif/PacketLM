# Independent verification of PacketLM @ b2bb9b8 (G49)

- **Verifier:** an independent Grok Bot verifier. The method is the same as in
  `VERIFY_0b0f6a8.md`, `VERIFY_82dd0a2.md` and `VERIFY_e944840.md`, on branches `verify-*`.
- **Date:** 2026-11-27, about 00:05–00:35 America/New_York.
- **Target:** `g44-canonical-engine` @ `b2bb9b8`, the G49 results.
  - Pre-registration: `9535318`.
  - `packetlm/` and `benchmarks/g49.py` are byte-identical between the two commits. Only
    `sealed_extra.py`, `sealed_tokens_g49.json`, docs and evidence changed.
  - The engine hash `23986d0cea13` and source hash `ca99cf367059` match the receipt.
- **Environment:** `GITHUB_TOKEN` and `GH_TOKEN` were unset, and `/workspace/PacketLM` was not
  touched.
- **Verifier tools:** they are committed in `docs/verification/tools_b2bb9b8/`:
  - `mybrute.py`: an independent brute force;
  - `soundness.py`: an engine-level honest-teacher search;
  - `closure_tests.py`: closure and retraction probes.

## Verdict

**Everything registered reproduces exactly:**
- the counts;
- G49 on **all 7 seeds**, including 537: **42/42 reply hashes byte-identical**, every threshold
  identical (10/11, D1 fails), and every metric identical apart from CPU;
- X1: 500/500, row-identical to the committed proof file.

**My own brute force agrees with `programs.Exact` on 500/500 random cases.**
- It shares no enumerator, interpreter, judge or blocker code with the engine.
- The worlds include chains longer than MAX_DEPTH, cycles, a 1–2-token capability, three guard
  pairs, PX statements, `complete` subjects, noise, and a domain that is a strict subset of the
  entities.

**The P1 fix holds in both modes.**

**Retraction works** for added, removed and corrected told facts in a closure, and correctly
ignores incoming edges and unrelated facts.

**But `complete X` is not sound with an honest teacher in general:**
- **H1.** It lets **wrong answers be qualified inside the domain** whenever the hidden program
  lies outside the engine's data-dependent hypothesis space, namely the guard proposals.
- **M1.** A `complete` stated *after* the example at X does not review the current version, so
  a version its own judgment contradicts stays qualified.
- **M2.** "Qualified" covers only the acquisition domain. `complete` makes qualification common,
  so qualified answers on entities outside that domain are now often wrong.

None of these touches the registered numbers: FC1 = 0 reproduces, and 0/327 active versions in
the final states are self-contradicted.

## Reproduced vs claimed

### Counts (b2bb9b8, fresh processes)

| command | claimed | reproduced |
|---|---|---|
| `python3 -m packetlm.g44_test` | 116 | **116, failed []** (16 `g49.*` checks) |
| `python3 -m packetlm.suite` | 203 | **203, 0 failed, 11/11** |
| `python3 -m packetlm.g45_test` | 18/18 | **18, failed []** |
| `python3 -m packetlm.mutations` | 60/60 | **60/60, baseline_failed [], 0 crash-only**. The 14 new mutations include `p1_statement_alone_adopts`, `fc_*` (8) and `exact_*` (4) |

### G49 (`python3 benchmarks/g49.py --out g49v`, all seeds 531–537; 5 min 26 s wall on 8 cores)

| check | claimed | reproduced |
|---|---|---|
| X1 (`scan_exact_proof --cases 500 --seed 4950`) | 500/500; 40 qualified, 227 PX, 285 closed | identical. Every row equals the committed file apart from timing |
| G49_exact_scans_complete | pass | pass |
| FC1 F wrong-qualified | 0 | 0 |
| FC2 F qualified | 30/56 (T1 3, T2 14, T3 12, T4 1); R 0, P 0 | identical |
| FC3 scope control | 26/26 untouched equal to R; statuses 56/56 | identical |
| FC4 L false statements retracted | 167/167 | 167/167 |
| FC5 L wrong-qualified after the reveal | 0 | 0 |
| **D1** R T1 depth ≥ 4 | **0.9286 (n 224), FAIL** | **0.9286, FAIL** |
| D2 F T1 depth ≥ 4 | 1.000 | 1.000 |
| leaks / source_unchanged | pass / pass | pass / pass |
| L window | 81 qualified answers, 0 wrong, accuracy 0.466 | 81, 0, 0.4658; L0 0 qualified, 0.4255 |
| `cpu_total_s` P / R / F / N / L / L0 | 110.8 / 184.8 / 306.4 / 206.8 / 329.2 / 203.2 | 103.5 / 178.4 / 292.1 / 199.5 / 316.5 / 192.9 |

**D1, seed 537, round 2:** confirmed. R and N both asked
`dmknis, ibalxz, aipbqj, akgihe, crjbva, enuduq`. The three middle questions are sealed depth-≥4
nodes. All 22 rows are unanswered, and depth-≥4 accuracy is 0/16. The recorded final status is
`suspended` (the reflexive program), with no adopted successor. The results text says "ended
ambiguous", which is the investigate outcome; the capability status is suspended. F asked the
same three sealed nodes in the same task, yet still identified the recursion (provisional, 16/16).

Leakage guard:
- `sealed_tokens_g49.json` covers all 1827 G49 evaluated, window and abstention items, and the
  registry now has 7970 tokens.
- None of them appear under `data/`.
- The leak check now covers every observation, and finds 0.

## Exactness of the exact scan (my own brute force)

`docs/verification/tools_b2bb9b8/mybrute.py`:
- It re-implements the grammar from the `programs.py` docstring: its own enumerator in canonical
  order, its own interpreter with the depth cap, its own open and closed judgments, and its own
  blocker rule.
- It enumerates **every** program of size ≤ 5, with no budget and no blocker cap, and dedupes by
  behaviour on domain ∪ observed subjects.
- It then requires `Exact` to match on four things: the program count, the ordered list of
  canonical-first blocking programs, the number of blocking behaviours, and `complete`.

| batch | cases | identical | qualified | with `complete` | with PX | brute force CPU | Exact CPU |
|---|---|---|---|---|---|---|---|
| seed 49001 | 300 | **300** | 41 | 190 | 183 | 90 s | 1.4 s |
| seed 7777 | 200 | **200** | 26 | 134 | 120 | 56 s | 1.0 s |

- About 25% of the worlds are chains of 10–13 nodes, half of them with a cycle back, which
  exercises the MAX_DEPTH = 8 cutoff in `recurse`.
- The domain is a random subset of the entities, often smaller than the observed subjects plus
  the universe.
- Up to 57,124 programs per case.

**Verdict:** `Exact` is exact on these worlds. Its module-doc argument also checks out:
- tokens distribute over union, so merging prefixes by relation is sound;
- c1|c2 is decided by projection onto the start nodes;
- the recursion is computed by the depth-bounded iteration from depth 8 down;
- the representative key order equals the `Inducer.programs` order.

## Soundness of `complete X`

### What holds

**Closure scope:**
- `_reach` follows outgoing told facts, excluding `cap:` facts.
- Every program token reads only outgoing facts of the current nodes: `rel:` images, guards on
  the node itself, and `cap:N@v`, which runs a pinned program over the same facts.
- So a told-fact closure does make the output at X final, relative to the pinned capability
  versions.
- The closed judgment is used only at X itself (`_judge`: `s in complete`). Other members of the
  closure are still judged open-world.

**Retraction** (`closure_tests.py`, both modes):

| event | result |
|---|---|
| a new told fact inside the closure (`c p d`, or at X itself) | retracted, and logged in `complete_log` |
| `retract` of a closure fact | retracted |
| `correct b p e` (removes `b p c`) | retracted |
| a fact stated after `complete` that extends the closure | retracted |
| an incoming edge into the closure (`w p a`) | **not** retracted, which is correct: no program reads incoming edges |
| an unrelated fact | not retracted |
| re-telling an existing fact | not retracted |

- After a retraction, the observed capabilities are re-acquired under the open-world judgment.
- `fc_new_fact_ignored`, `fc_removed_fact_ignored` and `fc_no_requalify` are killed.

**The honest-teacher argument holds *inside* the hypothesis space.** If the hidden program is
expressible with the proposed tokens and guards and has size ≤ 5:
- closed judgments never contradict it;
- it supports at least one value observation (guaranteed by the P1 guard);
- so it blocks any candidate that differs from it on the domain.

In my engine-level search (next section), **0 of 236 qualified in-space cases** gave a wrong
answer on the domain.

### H1 (High, mechanism soundness): an honest teacher can produce wrong qualified answers inside the domain

- Guard proposals are data-dependent:
  - pairs shared by every observed answer;
  - pairs of an observed subject, where at least two entities have that pair;
  - at most MAX_GUARDS of them.
- A hidden program can therefore use a guard that is never proposed.
- In the open world, such a gap is masked: less-defined alternatives survive as undetermined and
  block.
- `complete` refutes exactly those alternatives, so the scan can finish with **no blocker** while
  the truth is absent, and the engine qualifies a wrong program.

**Minimal reproduction** (programs mode). The teacher is fully honest: every fact is told, both
answers are true, and both closures are complete.

```
python3 -m packetlm.engine S.json --programs --answers \
  'fact e0 k cb' 'fact e0 ra e4' 'fact e1 ra e4' 'fact e2 k ca' 'fact e2 ra e3' 'fact e3 ra e4' \
  'fact e4 k cb' 'fact e4 ra e0' 'example kk: e4 -> e0' 'complete e4' 'example kk: e2 -> e2' \
  'complete e2' 'what is e1 kk' 'what is e3 kk'
→ e1 kk e1 [no construction for kk]      (qualified; truth: no value)
  e3 kk e3 [no construction for kk]      (qualified; truth: no value)
```

- **Hidden program:** `is:k:ca|is:k:cb>rel:ra>is:k:cb`, size 4. In words: "itself if `k ca`;
  otherwise its `ra` neighbour if both are `k cb`".
- Guard `k ca` is never proposed: only one entity (e2) has it, and the two answers (e0 `cb`,
  e2 `ca`) share nothing. The proposals are only `[k cb]`.
- The adopted program is `not:k:cb|rel:ra`. The exact scan is complete with 0 blocking
  behaviours, so it is **qualified**.
- e1 and e3 are in the acquisition domain (7 entities).
- **Without the `complete` lines, the same answers are `[provisional]`.**

**Scale** (`soundness.py`):
- random honest-teacher worlds;
- hidden programs of size ≤ 4 over `ra`/`rb` and guards on `k ∈ {ca, cb}`;
- examples and every investigate answer are followed by `complete`.

| run | cases | qualified | cases with a wrong qualified answer in the domain | of those, hidden outside the proposal space | in-space qualified cases with a wrong domain answer |
|---|---|---|---|---|---|
| seed 11, `complete` | 231 | 197 | **16** | **16** | 0 of 113 |
| seed 21, `complete` | 240 | 203 | **11** | **11** | 0 of 123 |
| seed 11, open-world control (no `complete`) | 231 | 1 | 0 | n/a | n/a |

**Impact on the registered run:** none.
- FC1 = 0 reproduces. G48-style hidden programs use guards that the proposal rule does propose.
- But "with an honest teacher, `complete` does not cause wrong qualifications" is **not true in
  general**.
- G49.md §1 ("What it can and cannot do") should state the condition: closed-world qualification
  is sound only if the truth is inside the proposal-limited grammar.
- **Options:**
  - make guard proposals independent of the observations (all class-like (Q, T) pairs in the
    closure); or
  - qualify under `complete` only when the closure's guard pairs are all proposed; or
  - report this explicitly as an assumption.
- Suggested coverage: this reproduction as a check, plus a mutation.

### M1 (Medium): `complete X` stated after the example at X doesn't review the current version

- `complete()` only calls `acquire`.
- When `acquire` finds no new supported candidate, it returns `none` and **leaves the current
  version, and its status, unchanged**, even when the closed judgment at X now contradicts it.
- **The outcome depends on the order:** stating `complete x` *before* the example suspends the
  version.

```
# base engine, honest teacher (truth: the first p-successor with k top: a -> c, x -> y, z -> c)
... 'example k1: a -> c' 'example k1: x -> y' 'complete a' 'complete x' 'what is z k1' 'requalify k1' 'what is z k1'
→ qualified k1 rel:p+rel:p … complete x … z k1 b (qualified)   # rel:p+rel:p predicts nothing at x: closed-contradicted
# same lines with 'complete a' 'complete x' first:
→ qualified k1 rel:p+rel:p ; none k1; k1@1 suspended: contradicted by its observations ; unknown
```

- Programs mode behaves the same way. `fact a p b`, `fact x q w`, `example k1: a -> b`,
  `complete a`, then `example k1: x -> y` and `complete x`: v1 `prog:rel:p` stays **qualified**
  and answers `m k1 n` for a newly told `m p n`.
- In the base case the qualified answer z → b is already wrong without `complete`; that is the
  base horizon. The defect is that the engine ignores evidence it has, depending on the order.
- **Registered run:** unaffected. In all 42 final G49 states, 0/327 active versions are
  contradicted by their own (closed) judgment, because F states `complete` in the same call
  right after each example.
- **Fix:** `complete()`, and `_fc_requalify`, should re-evaluate the current version, as
  `observe` does, and suspend it when it is contradicted. Add a check and a mutation.

### M2 (Medium): "qualified" covers only the acquisition domain, and `complete` makes this matter

- The exact scan decides alternatives on the component of the observations.
- A qualified version keeps answering, qualified, at entities outside that component, and at
  entities told later.
- Telling disconnected facts touches no closure, so nothing re-checks.
- This existed before, but it was invisible because open-world qualification almost never
  happened.

**Measurements** (`soundness.py`): after a fresh, disconnected random world was told, qualified
answers there were wrong in:

| run | cases with wrong qualified answers there |
|---|---|
| seed 11, with `complete` | **50/231** |
| seed 21, with `complete` | **36/240** |
| seed 11, open-world control | 1/231 |

There were also 5 and 2 cases with wrong qualified answers at original entities outside the
observations' component.

**In G49:** F's transfer-chain rows have 0 wrong-qualified answers.

**Suggestion:** scope the qualification to the domain in the reply. For example, answer
`[provisional]` outside the acquisition component, or re-scan when new components arrive. Also
state this in G49.md.

### Low

- **L1. The receipt start time and HEAD are self-reported.**
  - The receipt records `started 2026-11-26T23:54:46-0500` and `head 9535318`. That is 5 s after
    the pre-registration commit (23:54:41).
  - The results commit is at 00:00:55, 6 min 9 s later. My run took 5 min 26 s on the same
    8 cores, so the timeline is consistent.
  - `head` doesn't record a dirty working tree, and `source_sha256` covers `packetlm/*.py` but not
    `benchmarks/g49.py`. Git shows the harness unchanged, and my run reproduces all 42 reply
    hashes from the pre-registered code, so the result is a deterministic function of 9535318.
  - **Suggestion:** add `git status --porcelain` and a harness hash to the receipt.
- **L2. D1 wording.** The results say "the task ended ambiguous", but the recorded capability
  status is `suspended`. Suggest saying "ambiguous (capability suspended)".
- **L3. The base-engine question pool is still in storage order** (e944840 L2). It is declared
  open in G49.md §0.7; no change.

### Info

- Closed judgments through `cap:N@v` are final relative to the **pinned** dependency version,
  not to the dependency's true program. A provisional, wrong dependency makes a dependent's
  closed-world refutation a statement about that version.
- I tested 104 honest two-stage cases: Y taught, then K = `cap:Y>rel:r`.
  - With `complete`: 86 qualified, 1 with a wrong in-domain answer, and 15 with wrong qualified
    answers on new entities.
  - Open-world control: 1 qualified, 0 wrong.
- The PX.md restatements (P2, P3) are accurate: they quote the numbers from my e944840 report.
- The P1 fix holds in both modes:
  - `!none` alone adopts nothing;
  - `!none` plus `!several` adopts nothing, even with `--no-activation`;
  - `!none` plus `complete` adopts nothing;
  - `correct example a -> !none` on an adopted capability suspends it.
- The only `_adopt` call sites are behind the `acquire` guard.

## Commands

```bash
cd /workspace/pl-verify && env -u GITHUB_TOKEN -u GH_TOKEN git fetch origin && git checkout b2bb9b8
python3 -m packetlm.g44_test; python3 -m packetlm.suite; python3 -m packetlm.g45_test; python3 -m packetlm.mutations
python3 benchmarks/g49.py --out g49v                     # all 7 seeds; compare receipt/raw with docs/evidence/g49
python3 -m packetlm.scan_exact_proof --cases 500 --seed 4950 --out x1.json
python3 docs/verification/tools_b2bb9b8/mybrute.py 300 49001; python3 docs/verification/tools_b2bb9b8/mybrute.py 200 7777
python3 docs/verification/tools_b2bb9b8/soundness.py 300 11 plain        # add 'open' as 4th arg for the control
python3 docs/verification/tools_b2bb9b8/soundness.py 300 21 plain
python3 docs/verification/tools_b2bb9b8/soundness.py 200 12 dep
python3 docs/verification/tools_b2bb9b8/closure_tests.py
```
