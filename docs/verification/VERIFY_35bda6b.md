# Independent verification of g44-canonical-engine at 35bda6b (G57; prereg 963527c)

Verifier clone `/workspace/pl-verify`, branch `verify-35bda6b`, made from 35bda6b. `/workspace/PacketLM` was not touched. Every CPU-heavy job ran through `tools_35bda6b/guard.sh`, which waits while `/workspace/REGISTERED_RUN.lock` exists. The lock was never present during my jobs. All times are EST (UTC−5).

## Verdict

No High or Medium findings. The `--indexed` exactness claim (Ei) held under a hard adversarial differential: replies and full state matched byte for byte. Every count reproduced. The A values reproduced exactly from the registered CSVs and qualitatively on re-runs. Rule F ("not flat") reproduced at the extreme sizes. The timeline is consistent: the prereg was committed before the run, and no code changed after the prereg. Three Low findings, all about wording or provenance, and some Info items follow.

## 1. `--indexed` exactness (the evidence-gated re-asks)

**Tool:** `tools_35bda6b/indexed_diff.py`. I wrote it independently of `packetlm/g57_diff.py`.

It runs three in-process `serve.Server`s on the same session:
- **REF** has no `--indexed`, so every re-ask is executed.
- **IDX** has `--indexed` with `check_readonly=True`.
- **IDX2** has `--indexed` with `check_readonly=False`, which is the registered configuration.

After **every call** it compares the replies and `json.dumps(state)` (in insertion order). At the end it compares the snapshot files' bytes.

**Session design:**
- Capabilities are taught from a hidden chain program. `names[1]` is composed on `names[0]` to create a `cap:` dependency.
- Rounds of read-only re-ask calls follow. They use odd forms (`What is x n?`, `ask x n`, `what is x n.`), unknown entities, entities not yet told, lexicon words, and direct relation questions. They are often repeated so the gate fires.
- A single mutation separates the rounds. Mutations cover:
  - an alternative path or blocker on a relation the program uses;
  - a fact at a new entity (as subject or object);
  - retracting or correcting a used fact;
  - `complete`;
  - a contradicting example (suspension, re-acquisition, replacement) and `correct example`;
  - `investigate` and `requalify`;
  - `define` and redefinition of lexicon words, and `express`;
  - a construction (library change) and a question template;
  - re-teaching a capability on another relation (replacement or demotion; this also changes what `names[1]` depends on);
  - a new relation;
  - a mixed question+mutation call;
  - a memo drop (close).

| run | flags (plus `--answers --bounded --lean --deepen=3`) | sessions | calls | read-only calls | gated answers | reply / state / final-byte diffs | errors |
|---|---|---|---|---|---|---|---|
| idx.101 | – | 300 | 10611 | 5870 | 32748 | 0 / 0 / 0 | 0 |
| idx.102 | – | 300 | 10367 | 5716 | 31721 | 0 / 0 / 0 | 0 |
| idx.103 | – | 300 | 10544 | 5830 | 32908 | 0 / 0 / 0 | 0 |
| idx.104 | `--no-library` | 300 | 10380 | 5737 | 32426 | 0 / 0 / 0 | 0 |
| idx.105 | `--deepen=5` | 150 | 5203 | 2891 | 16075 | 0 / 0 / 0 | 0 |

In total: 1350 sessions, 47,105 calls, 146k gated answers, 0 differences. About 9% of the gated replies were `ambiguous` and about 90% were `known`.

**Sensitivity:** is the tool able to see stale gating? I applied the builder's G57 mutations in /tmp copies (`tools_35bda6b/mutsens.sh`; logs in `logs/mutsens/`).

My differential **kills these 12**:
- `gate_ignores_stamps` (68 reply diffs), `gate_ignores_capabilities` (15);
- `memo_ignores_added` (24), `memo_keeps_removed` (16), `memo_stamp_missed` (20);
- `indexed_ambiguity_off` (31);
- `packets_stale_after_rebuild`, `append_path_skips_one`, `by_rel_wrong_relation`;
- `region_seeds_only`, `uf_ignores_added_edges`;
- `readonly_any_line`. For this one IDX raised "read-only call changed the state" 42 times, which shows the before/after state-hash check works.

**7 survive.** I read the code for each and argue they are observably equivalent, i.e. the builder's guards are conservative, not load-bearing (Info 1):
- `gate_ignores_dependencies`: `expand()` re-reads the pinned dependency versions, and the fingerprint already holds the expanded base relations, or None.
- `gate_ignores_known_entity`: `execute` returns ∅ for an unknown subject, and any fact that makes s known on a base relation bumps that relation's stamp.
- `gate_ignores_library`: the memo caches the answer dict only. `say` (library, `express`) runs live after it.
- `gate_outside_readonly`: the fingerprint is complete, so gating inside mutating calls is also exact. This survivor is extra evidence that the fingerprint is complete.
- `uf_keeps_removed_edges` and `region_ignores_seeds`: an over-approximated region only adds re-acquisitions, and those are exact. A seed with no fact edge cannot be in `grown`.
- `readonly_unchecked`: this only removes a check.

The builder's mutation suite kills all 7 through its own direct tests.

**Read-only calls do not mutate state.** IDX (with the check on) raised no error in any run. Replies, state and snapshot bytes of IDX2 (no check) matched REF after every call. And the readonly-detection mutation was caught by the check (above).

**Code audit of `_answer_fp`:**
- It covers everything `_answer_exec` reads: the version (target's record hash), the `execute` rows (base relations plus stamps), `pos` membership, and `_dom_set` (the domain is in the target record).
- `ask` builds `_idx()`, so `Memo.sync` runs before any fingerprint is compared.
- Adaptive retention is refused under serve, and programs and operators turn the gate off.

**Crash/journal (the d6cbcf3 fixes) with `--indexed`:**

| run | flags | sessions | calls / runs | crashes | final state or byte diffs | errors |
|---|---|---|---|---|---|---|
| serve.61 | crash | 100 | 583 | 122 between, 111 mid | 0 | 0 |
| serve.66i | crash, `--indexed` | 100 | 594 | 119 between, 125 mid | 0 | 0 |
| faults.82 | – | 30 | 994 | 831 | 0 | 0 |
| faults.85i | `--indexed` | 20 | 551 | 461 | 0 | 0 |

- **S1 (my first-snapshot repro):** fixed. A reopen recovers.
- **Low 1:** a journal beside no state file is now refused: "journal without its base snapshot (reset a path by deleting STATE, STATE.bak and STATE.journal)".
- **Low 2:** the per-process engine on a journal that holds records now exits with rc 3, "unclosed packetlm.serve journal".
- **M1 lean-order and base-N1 repros:** both pass (logs in `logs/*repro.log`).

## 2. Counts

- g44: **152/152**, failed [].
- Suite: **240** checks, 0 failed, 11/11 modules.
- G45: **18/18**.
- Mutations: **124/124** killed, baseline_failed [].

**The 3 re-anchored mutations keep their intent:**
- `g54_lean_ambiguity_off`: the same edit. Only the anchor is extended (`…\n\n    def _ask_indexed`) so it selects the `_ask_lean` block.
- `s1_region_is_domain_only`: still hits the non-indexed region test (`bool(grown & {s_ for s_, _ in obs})`), with the same meaning as before. The indexed path has its own mutations, `g57_region_seeds_only` and `g57_region_ignores_seeds`.
- `g56_serve_replay_unverified`: the same `_need` line, moved into `Server._replay`.

## 3. G57 A values and part S

**Instrument (70297af, 5000 resamples) on the registered CSVs:** 18/18 primary and secondary contrasts match the receipt's report lines exactly. Examples:
- L1i comp: −0.8034 [−0.9042, −0.7156].
- L3i unrel: −5.8667 [−6.4361, −5.2326].
- Mi comp: +0.0407 [+0.0203, +0.0624].
- Mi unrel: +0.5931 [+0.5842, +0.6011].

**Re-run on 2 seeds per curriculum (comp 201,205; unrel 211,216):**
- All 28 runs have reply-stream and final-state hashes identical to `progress.jsonl`.
- Each run's CPU is 0.86–1.11× the registered run.
- My run competed with the builder's own concurrent mutation run in `/workspace/PacketLM-g56`; it was not a registered run and no lock was held.

| contrast | registered S=7 | registered, same 2 seeds | my re-run, S=2 |
|---|---|---|---|
| L1i comp | −0.803 | −0.857 | −1.099 [−1.240, −0.980] |
| A(Ci+m‖Bs) comp | −0.797 | −0.863 | −1.105 |
| Mi comp | +0.041 | +0.050 | +0.023 [**−0.005**, +0.050] |
| L3i unrel | −5.867 | −5.184 | −5.473 [−5.874, −5.137] |
| A(Ci+m‖Bs) unrel | −5.948 | −5.491 | −6.009 |
| Mi unrel | +0.593 | +0.595 | +0.607 [+0.601, +0.612] |

**Full comp re-run on all 7 seeds:**
- All 62 runs are hash-identical.
- Mi comp **+0.032 [+0.025, +0.040]**, so it is claimed again.
- L1i −0.905 [−0.993, −0.834], still no claim.

All decisions reproduce. On my 2-seed run the comp Mi interval touches 0 (Info 3).

**Part S, re-run at N ∈ {0, 16000}, all 7 seeds:**
- All 28 reply hashes and `known` counts are identical to the registered `scale/s*_n*_*.json`.

| | N=0 (ms) | N=16000 (ms) | R_16000 |
|---|---|---|---|
| Xi | 2.30 | 197.7 | 86.1 [82.9, 89.4] |
| Xs | 2.61 | 374.0 | 143.5 [139.2, 147.5] |

The registered values are Xi 91.9 [86.5, 95.7] and Xs 156.2 [150.4, 162.8]. Rule F is not claimed, which reproduces the registered decision.

Recomputing `boot` from the 56 registered per-run files gives exactly the registered R values.

**Padding audit:**
- The padding is name-disjoint from the workload (`pz*`/`pr0..19`/`pc*`/`pcap*` against `t*e*`/`w*`/`wc*`).
- The workload never touches the padding, and the known count is 184 at every N.
- Profile of one Xi run at N=16000 (`cProfile`, 50 workload calls, 6.1 s). The remaining O(N) work per call is:
  - the `_idx()` rebuild after each mutating call (2.6 s);
  - `validate_lean` (1.3 s);
  - `relations()` scanning all facts during acquisition (1.1 s);
  - `reference.index` (0.9 s);
  - the first geometric recall per (s, r) (0.4 s).
- So the "still roughly linear" reading is right, and these are the next targets. See Low 1 for the "relevant state held fixed" claim.

## 4. Timeline

**Sequence:**
- 963527c, the prereg (code, harnesses, predictions), was committed at 05:30:09.
- G57.md says the lock was created at 05:30:21.
- The registered run ran 05:30:22–05:31:22 on head 963527c, with a clean tree and guards true.
- Part S ran 05:31:22–05:31:49.
- 35bda6b was committed at 05:32:32.

**What changed after the prereg:**
- 963527c..35bda6b changes no code. It adds evidence files only, plus 76 lines appended to G57.md and 23 to the ledger, with 0 deletions.
- The prereg's predictions are unedited, and all of them held. For example, it predicted R "likely 50–100×", and the result is 91.9.

**Dev receipts:**
- They ran before the prereg on dirty d6cbcf3 trees, which is disclosed: dev at 04:55, scale-dev at 05:09, dev4 at 05:10.
- The registered seeds (201–217, 221–227) differ from the dev seeds (e.g. 991–992).

**My own activity:** my CPU work for this milestone started at 05:33:56, after the lock was removed. I was idle during 05:30–05:32. So the run was not slowed by the verifier, despite the receipt's note that it "may have been running". The 3.89 end load came from the run's own 8 workers.

The lock's creation and removal times cannot be checked from the repo (Low 2).

## Findings by severity

**High:** none. **Medium:** none.

**Low**
1. **Part S: "relevant state is the same at every N" is too strong for the N=0 baseline.**
   - At N=0 the state has none of the 20 padding relations and none of the padding capabilities. At N>0 it has all 20 relations, plus 2–32 capabilities.
   - The relations enter acquisition's hypothesis space (`relations()` → `primitives`/`hypotheses`), so the R_16000 denominator also differs in shape, not only in size.
   - The decision is unaffected: between N=1000 and N=16000, which share all 20 relations, Xi still grows 17.8× (Xs 18.7×) per seed.
   - Suggest stating the claim as "relevant content fixed", or using a baseline that contains every padding relation (for example N=20 with one fact per relation).
2. **Provenance is thinner for part S and the lock.**
   - `g57_scale_receipt.json` has no `head`, clean-tree or source-hash fields; only the main receipt has them.
   - Neither receipt records the lock (its path, mtime or presence).
   - The lock times in G57.md are an unverifiable statement.
   - Suggest that the harnesses write head, porcelain status and lock mtime into each receipt.
3. **One snapshot is charged to the tasks at N=16000 only.**
   - Part S charges `srv.call` CPU, and the server snapshots every 64 calls. Padding uses 40 calls at N=16000 (fewer at smaller N), so the snapshot at call 64 lands inside the workload only at N=16000. That snapshot serializes 16k facts.
   - The effect is small (one snapshot across 10 tasks) and favours no arm, but it is an O(N) cost inside the charged window at one size only.

**Info**
1. Seven G57 mutations survive a pure differential (see §1). The fingerprint fields `deps`, `known entity` and `library`, and the read-only restriction, are conservative rather than necessary. That is fine, and the builder's suite kills these mutations directly.
2. A latent cache key in `_dom_set` (from 7dd716a, before G57): `(name, v, id(ver["domain"]))`.
   - CPython reuses addresses. Two domain replacements of the same version with no `_dom_set` call between them can give a new list at the cached address, and then the stale set is returned. I showed this synthetically.
   - Probes (`domcache_probe.py`: 781 calls, 379 hits; `domcache_stress.py`: 6298 calls, 2254 hits, directed at growth requalification and `requalify`) found 0 stale hits. So I found no path that reaches it.
   - Suggest keying on the list object itself, or on the domain content.
3. **Comp Mi is a small, timing-sensitive effect.**
   - The registered +0.041 reproduced as +0.032 [+0.025, +0.040] on all 7 seeds.
   - On a 2-seed re-run (beside other load) the CI was [−0.005, +0.050].
   - Its "claimed (small)" wording is apt. Unrel Mi (+0.59) is robust.

## Files

- `tools_35bda6b/`:
  - `indexed_diff.py`, `mutsens.sh`, `guard.sh`;
  - `domcache_probe.py`, `domcache_stress.py`;
  - the d6cbcf3 tools, re-used: `serve_diff.py`, `serve_faults.py`, `lean_diff.py`, `journal_first_snapshot_repro.py`, `lean_order_repro.sh`, `base_n1_repro.sh`.
- `tools_35bda6b/logs/`:
  - g44, suite, g45 and mutation logs;
  - `adv/` (idx, serve and fault runs) and `mutsens/`;
  - G57 re-runs (`g57v.log`, `g57c7.log`, with their `*_progress.jsonl`) and the part S re-run (`g57sv.log`);
  - the repro logs.
