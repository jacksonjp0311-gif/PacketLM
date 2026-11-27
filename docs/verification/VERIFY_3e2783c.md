# Independent verification of g44-canonical-engine at 3e2783c

Commits checked since 050bebd: 70c6dcb (G54 prereg), e9c88f1 (G54 results), 045c61a (N1 fix, verifier t5
mutations, G45.md note), 0d686b5 (G55 prereg), 3e2783c (ledger). Separate clone, tokens unset,
/workspace/PacketLM untouched. Tools and logs are in `docs/verification/tools_3e2783c/`. All times are EST (UTC-5).

## Verdict

- The N1 fix works in programs mode.
- Counts reproduce: g44 133, suite 221, G45 18/18, mutations 92/92.
- The 13 G54 A values reproduce exactly with the instrument pinned at 70297af.
- The G55 pre-registration is in order.
- `--lean` keeps replies identical on every registered seed and on 520 random CLI sessions (about 9,500 processes).
- **However, `--lean` is not exact in general (Medium, L1).** A lean save reorders dict keys, and the engine
  iterates dicts in insertion order. Reply text is therefore reachable that differs between lean and
  non-lean runs.
- **The N1 class remains open in base mode (Medium, N1b).**
- The "structural floor" conclusion for unrel holds. But f0 is mostly engine import cost, not a fixed
  protocol cost (Low).

## Medium

**L1: `--lean` changes iteration order, so replies can differ.**
- `_save_lean` writes `json.dumps(state, sort_keys=True)`. A non-lean save keeps insertion order. After
  reload, `capabilities`, `observations` and `complete` iterate in sorted order instead of insertion order.
- These sites iterate dicts unsorted and emit events or list entries:
  - `_retire` (engine.py:605)
  - `review` (887)
  - `_dependents` (846)
  - `_fc_violated` (1863)
- Repro (`tools_3e2783c/lean_order_repro.sh`): capability `zz` is taught before `aa`, then `correct a r q`.
  - non-lean: `...; retired example zz: a -> b; retired example aa: a -> b`
  - lean:     `...; retired example aa: a -> b; retired example zz: a -> b`
- The doc says "exact; same replies" and "state contents unchanged (only the key order of the saved text)".
  Both are false in general: key order is semantically observable.
- Random sessions with `lean_diff.py`. Each session runs ref, lean and mixed; first-reply diffs are null in
  every case.

  | seed / flags | sessions | processes | state diffs | replies differ |
  |---|---|---|---|---|
  | 41 `--answers` | 150 | 2,760 | 9 | 0 |
  | 42 `--answers --bounded` | 150 | 2,769 | 18 | 0 |
  | 43 `--answers --programs` | 60 | 1,179 | 5 | 0 |
  | 44 `--answers --bounded --qualified-library --operators` | 100 | 1,773 | 14 | 0 |

  - With `LEAN_NORM=1` (every list sorted before comparing), seeds 41 and 44q give 0 diffs. So every state
    difference is order-only, for example two `complete_log` entries swapped.
  - The random sessions never produced a reply diff because `correct` rarely retires examples of two
    capabilities at once, and the G54 curricula never do.
- **The registered G54 result is unaffected.** All 22 arm×seed reply hashes match, and I re-ran 4 seeds at
  3e2783c with Cl==Cb and Bl==Bb.
- Not shown: whether the order can change a *decision* as well as event order (for example, a cascade in
  `_retire` that depends on processing order). I found none.
- Fix options:
  - (a) Lean writes insertion-order text and checksums that same text. This needs a checksum definition
    that does not require canonical text.
  - (b) Make every state-dict iteration `sorted()`. This changes non-lean reply order relative to history,
    so registered hashes would need re-checking.
  - (c) Keep the claim, but restrict it to "same replies up to the order of events in one reply". Add a
    g44 check that uses two capabilities in non-alphabetical insertion order.

**N1b: the base engine keeps qualified when re-acquisition finds no candidate.**
- Repro (`tools_3e2783c/base_n1_repro.sh`, no `--programs`):
  `fact a ra b; fact c ra d; fact e ra f; example kk: a -> b; example kk: c -> d; fact a ra x`
- Result:
  - `rel:ra` is now *undetermined* on its own example (ra(a) = {b, x}).
  - `hypotheses.kk.candidate` is `None`.
  - The version stays `qualified`, with history only `acquired`, and keeps answering as qualified.
- `adversarial3.py base`, seed 11: 20 cases are qualified after a none re-acquisition. Its 7 "witnesses" use
  guard programs outside the base space, so they are invalid. I found no wrong answer under an honest
  in-space teacher. In base mode, an honest teacher keeps H supported, so H is re-found.
- The issue is the status claim, the same one the N1 fix addresses. The fix (engine.py:1356) is only in the
  programs acquisition path, and the ledger (line 885) says "programs mode". Apply the same cap to base
  acquisition, plus a g44 check and a mutation.

## Low

1. **The lean checksum shortcut accepts non-canonical text.**
   - A file with a duplicate top-level `"state"` key, written as prefix + sha256(T), is refused by non-lean
     ("checksum mismatch") but loaded by lean (1 fact instead of 2).
   - So "a non-canonical text with the same hash would be a SHA-256 collision" is false.
   - It gives no new attack capability, because a writer can recompute the hash, and saves and random
     corruption cannot produce it.
   - Fix: reject duplicate keys (`object_pairs_hook`), or require exactly the expected top-level keys.
2. **f0 is mostly engine import cost, not a protocol constant.**
   - f0 is the median `cpu_total_s` of 40 empty-state Bl calls, measured serially after the Pool run.
   - On my loaded box it splits as:
     - bare `python -c pass`: 9.1 ms (6.4 ms with `-S`);
     - `import packetlm.engine`: about 30 ms (dataclasses, inspect, tokenize, json);
     - the engine's self-reported empty call: 29 ms.
   - Calling A_struct "the protocol's floor" overstates it. Part of the floor is under the engine's control
     (lazy imports).
   - The qualitative conclusion survives. Even an interpreter-only floor of 9 ms gives about
     A' ≈ −504f/(407f + 0.88) ≈ −1.0 on unrel, as long as each call is a fresh Python process.
   - "Structural" here means exactly the maintenance re-ask processes. The process difference equals the
     maintenance count: comp 168, unrel 504. These are charged only to persistent learners.
3. **G54 table wording.** The unrel Cl+maint‖Pl+maint interval is [−0.0319, −0.0032], entirely below 0, but the
   table labels it "≈ 1".
4. **G55.md §2.** It says the h1gap world at N=16 "finds a blocker, so it is provisional". I get qualified,
   gap 0, 0 blockers, domain {a,c}; `what is d hq` is provisional through M2. The g44 check accepts either
   outcome, so the doc sentence is inaccurate.

## Info

- The G55 dev evidence stores only cap and scan summaries, not blocker programs. So the claim of
  "≥16 genuine blockers" cannot be checked from the evidence.
- The G55 arm set changed (F24/F72 → F32) after the aborted dev run. This is disclosed and happened before
  registration.
- **Load contention.** The registered G55 run started at 04:00:02 in /workspace/PacketLM. My verification runs
  and the builder's own /workspace/PacketLM-g56 jobs ran concurrently (load average up to about 13 on
  8 cores, 04:00–04:13).
  - Rule C, the median F32/F8 CPU ratio ≤ 2.0, is a ratio within each seed, so it is partly robust.
  - Its CPU figures should still be read as measured under contention. Consider re-timing or reporting the
    load.
- Not re-run: the registered G55 probe (seed 9301). I did not use any seed from 561–567.

## Checks performed

1. **N1 (programs).**
   - The 050bebd repro now ends `e3 kk e4 ... [provisional]`, with history "re-acquisition found no candidate".
   - `adversarial3.py` results (each: 0 wrong qualified, 0 qualified-after-none, 0 honest witness):

     | run | qualified | ops |
     |---|---|---|
     | prog, seed 13 | 76 | 261 |
     | prog, seed 14 | 81 | 270 |
     | progkeep, seed 31 | 90 | 249 |
     | progkeep, seed 32 | 85 | 260 |
     | dep, seed 11 (33 cases) | 9 | 31 |

   - The dep run was cut short and re-run niced to reduce load on the registered G55 run.
2. **Lean.**
   - The G54 registered reply hashes and process counts are equal for all 22 arm×seed runs.
   - My rerun at 3e2783c (comp 141, 145; unrel 151, 156) gives Cl==Cb and Bl==Bb on all 4 seeds, with CPU
     within about 5%.
   - For random sessions, see L1.
3. **Counts.** g44 133 (failed []); suite 221 checks, 0 failed, 11/11 modules; G45 count 18, failed []; mutations
   killed 92/92.
4. **G54.**
   - The instrument at 70297af (clean, 5000 bootstrap resamples) on the registered CSVs reproduces all 13 A
     values. Examples:
     - comp Cl+maint‖Bl: −0.8451 [−0.9195, −0.7730]
     - comp Cl+maint‖Cb+maint: +0.1738
     - unrel Cl+maint‖Bl: −3.3123 [−3.4794, −3.1631]
     - unrel Cl+maint‖Pl+maint: −0.0147
     - unrel Cl+maint‖Cb+maint: +0.3347
   - Independent A_struct and share recomputation from the registered numbers:
     - comp: −0.1005 and 0.1189;
     - unrel: −1.1427 and 0.345.
     - These match the doc's formula, A_struct = 1 − (prc_Cl·f0 + above_floor_Bl)/tot_Bl.
   - Per-process cost:

     | | Bl | Cl |
     |---|---|---|
     | comp | 52.3 ms | 80.2 ms |
     | unrel | 28.1 ms | 54.1 ms |

     The process ratios are 1.203 (comp) and 2.238 (unrel).
5. **G55 pre-registration.**
   - Rules Q and C, the arms F8/F32/L32 and seeds 561–567 are fixed in 0d686b5 (03:58:34).
   - The ledger at 3e2783c (03:59:13) says the seeds are unconsumed. The first registered artifact
     (F32_561.json) is from 04:01:11, after both commits.
   - The dev seeds (9101, 9102, adversarial 9201) and the probe seed (9301) are disjoint from 561–567.
   - `closed_guards` defaults to `MAX_GUARDS`=8, and its only use is `len(allp) <= self.closed_guards`.
   - G52 rerun (`benchmarks/g49.py --seeds 551,555`): all 12 `replies_sha` values (arms P, R, F, N, L, L0 ×
     seeds 551 and 555) equal `docs/evidence/g52/g52_raw.json`.
   - `benchmarks/verifier_tools_050bebd/` is byte-identical to my tools.
6. **Timeline.**

   | time | event |
   |---|---|
   | 02:29:16 | G54 dev receipt (head 050bebd, dirty) |
   | 02:50:05 | 70c6dcb committed |
   | 02:50:06 | G54 registered receipt (head 70c6dcb, clean) |
   | 03:00:00 | e9c88f1 |
   | 03:11:49 | 045c61a |
   | 03:46 | G55 dev stop |
   | 03:58:34 | 0d686b5 |
   | 03:59:13 | 3e2783c |
   | 04:00:02 | G55 registered run starts |

   - The timeline is consistent with the receipts.
   - G54 was registered on the pre-N1 engine. N1 is programs-only, G54 is not programs mode, and my rerun at
     3e2783c reproduces the same hashes.
