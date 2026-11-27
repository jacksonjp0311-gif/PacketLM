# Independent verification of g44-canonical-engine at d6cbcf3

Commits: a0b068f (ledger), ca9f3a1 (G56 prereg), 6d9c1d8 (verify-3e2783c response, amendment 1),
d6cbcf3 (G56 results). Separate clone, tokens unset, /workspace/PacketLM untouched. Every CPU-heavy
job ran through `tools_d6cbcf3/guard.sh`, which waits while `/workspace/REGISTERED_RUN.lock`
exists. The lock was never present during this check (04:40–05:10 EST). Tools and logs:
`docs/verification/tools_d6cbcf3/`. Times are EST.

## Verdict

- The fixes for M1, N1b and Low 1 hold.
- `--lean` is now byte-exact on random sessions.
- G54's 77 hashes are unchanged; I reproduced all 77 at d6cbcf3.
- Counts reproduce.
- All 20 G56 A values reproduce with 70297af.
- The long-lived protocol's replies are exact (registered seeds and about 2,000 adversarial calls,
  including kill -9).
- There is no hidden in-memory state, and B gets a fresh empty state per task.
- **One Medium:** a crash inside the first snapshot of a new path makes that path unopenable.
  This was hit with a real kill -9 as well as by fault injection. It is fail-stop: no wrong reply
  or state was ever produced.
- G56 accounting is fair as defined. The G55 failure record and the G56 abort and amendment are
  consistent with the receipts. I found two small precision issues.

## Medium

**S1: crash recovery fails for the first snapshot of a new path.**
- How it happens: `_snapshot` writes the primary with the lean `save`, then restarts the journal.
  For a new path, the journal header has `base: null` and no backup exists. If the process dies
  between those two steps:
  - recovery finds `head["base"] (None) != have (primary checksum)`;
  - the "contained" branch requires `head["base"] is not None`;
  - so `open_path` raises `StateError: journal does not extend the loaded snapshot`.
- The primary already contains every journaled call, so nothing is lost. But the path cannot be
  opened again without deleting the journal by hand.
- G56.md §2 says this crash case is handled and dropped as contained. It is handled only when a
  previous snapshot exists.
- Evidence:
  - `journal_first_snapshot_repro.py` (deterministic).
  - `serve_faults.py`: every durability step (fsync, replace, link) of every call, made to crash
    in turn. There were 1,503 crash points over 60 sessions. 123 recovery errors occurred, every
    one in this window (the dir-fsync after the primary replace, or the journal-tmp replace, of the
    first snapshot: call 0 with snapshot-every 1, call 1 with snapshot-every 2). The other
    1,380 crash points recovered to exactly the per-process final state.
  - `serve_diff.py --crash`: one real kill -9 hit it (seed 62, session 6).
- Effect on G56: none. A crash kills the run. A B path's first snapshot is taken when the next
  task opens a new path. But a C path's first snapshot (call 64, or close) is exposed.
- Fix: in recovery, when the header base matches neither file, replay the journal onto the base
  it names (`None` = `empty_state()`). If the result's text hash equals the loaded primary's
  checksum, the journal is contained and can be dropped. Otherwise fail as now. Add a g44 check and
  a mutation.

## Low

1. **A stale journal resurrects a deleted state.** If STATE and STATE.bak are deleted (a reset)
   while a `base: null` journal remains, the server replays the journal onto the empty state, and
   the old capability answers (`a kk b`). A fresh per-process engine on the same path answers
   `unknown`. So "a path with no file starts from `empty_state()`" holds only if the journal is
   deleted too. G56 is unaffected: `g46._run_arm` globs `B*.json*`, which includes `.journal`, and
   `g56.job` rmtrees the seed dir. Fix: document "reset = delete STATE*", or refuse a journal
   without a primary unless a crash before the first snapshot is the only explanation (no backup,
   journal mtime newer than any primary).
2. **The per-process engine ignores the journal.** A per-process engine, or the harness's
   `_file_load_state` fallback, opening a path the server left with journal records reads the
   older snapshot. The protocols are not interchangeable on one path after a crash or without a
   close. G56 never mixes them on a path. My first serve runs counted this as state loss until I
   recovered the files before comparing (my harness bug, fixed: `finalize`). Document it in
   G56.md §2.
3. **G55 failure timing (precision).** G55.md says the run "died at 04:22:14 EST, when one L32
   call exceeded the 600 s limit (L32_562)". L32_562's last save is 04:00:29, so the timed-out
   call started then or later and hit its limit around 04:10:30. 04:22:14 is when `pool.map`
   re-raised after the other workers finished (L32_565 was still saving at 04:12:14). The load
   window in the disclosure (04:00–04:13, up to about 13) is the relevant one, so the honesty of
   the record holds. Only the "when" is conflated.

## Info

- The builder's own jobs overlapped the G55 registered run. These were the G56 dev runs at
  04:04:25 and 04:07:47 (dirty tree at a0b068f), the PacketLM-g56 tests, and the 17 s first G56
  start at 04:20:14. They are disclosed generically ("builder's G56 dev runs and tests"). The
  first start overlapped G55's last 2 minutes and is not named among the load sources.
- "Artifacts deleted unread" for the aborted first start cannot be verified from the repo. Nothing
  in the evidence derives from seeds 161–167 or 171–177.
- `field.bits_for` (`lru_cache`, pure) is the only process-level cache. Every other cache is
  per-`Engine`, and a fresh `Engine` is built per call. Warm interpreter caches (pyc, `re`) are
  shared across B tasks by design. That is the protocol being measured, not state.
- Sensitivity of my serve tools to serve mutations:

  | mutation | killed by my tools? |
  |---|---|
  | `new_path_reuses_state` | yes |
  | `no_journal_record` | yes |
  | `no_snapshot_on_close` | yes |
  | `journal_base_ignored` | yes |
  | `replay_unverified` | no (honest runs never trigger it) |
  | `memory_unvalidated` | no (honest runs never trigger it) |
  | serve without `eng.finish()` (my own mutation) | no |

  - The builder's g44 checks kill all of these.
  - The `finish` one is observable: a call ending in a growth fact (base_n1 split into calls)
    gives `qualified` instead of `provisional`, and g44 `g56_serve_replies_and_state_equal`
    catches it. It is not in the mutations list; consider adding it.
- `faults.84` (programs mode, crash points) had not finished when I wrote this report and is not
  counted.

## Checks performed

1. **M1, N1b, Low 1 fixed; lean byte-exact.**
   - Repros: `lean_order_repro.sh` gives `retired zz…; retired aa…` for both lean and non-lean.
     `base_n1_repro.sh` gives provisional, "re-acquisition found no candidate".
   - `lean_diff.py` now compares the state byte-for-byte in written (insertion) order, plus the
     backup state, plus whole final files of an all-lean twin.

     | seed | flags | sessions | differing |
     |---|---|---|---|
     | 51 | `--answers` | 100 | 0 |
     | 52 | `--answers --bounded` | 100 | 0 |
     | 53 | `--answers --programs` | 40 | 0 |
     | 54 | `--answers --bounded --qualified-library --operators` | 100 | 0 |

     About 6,000 processes in total.
2. **serve exact.**
   - My G56 rerun at d6cbcf3 (comp 181, 185; unrel 191, 196): E holds for every role (C, B, P, F).
     All 28 arm×seed reply-stream hashes, call counts and maintenance counts equal the registered
     receipt. CPU is within about 5%.
   - `serve_diff.py --crash`: real server processes against per-process `--lean`.

     | seed | flags | sessions | calls |
     |---|---|---|---|
     | 61 | base | 100 | 583 |
     | 62 | `--no-library` | 100 | 572 |
     | 63 | `--programs` | 40 | 263 |
     | 64 | `--qualified-library --operators` | 100 | 577 |

     - Events:
       - 403 kill -9 between calls and 384 in the middle of a call (247 applied; 163 of those had
         their journaled reply hash checked against the reference);
       - snapshot-every values of 1, 2, 3, 5 and 64;
       - 399 B-style calls on brand-new paths interleaved, each compared with a fresh per-process
         run: 0 differences.
     - Result: 0 reply differences and 0 final-file differences (whole bytes), except the single
       S1 session.
   - **Hidden state** (`--inproc`, seeds 71 and 72; 80 sessions, 494 calls). After every call, the
     in-memory state equals type- and order-strictly (a) its JSON round trip and (b) the state a
     second Server recovers from a copy of snapshot + journal: 0 differences.
   - **B fresh per task.** In code, each task has a new path (`B_{fi}_{ti}.json`), and `Engine.open`
     on a missing file gives `empty_state()`. Empirically, the 399 new-path calls gave 0 diffs, and
     the `new_path_reuses_state` mutation is caught. The caveat is Low 1.
3. **G54 hashes.**
   - `g54_hash_recheck.json` is consistent: 77/77, with the engine sha equal to d6cbcf3's.
   - Independently, I ran the full `benchmarks/g54.py` (7+7 seeds) at d6cbcf3. All 77 reply-stream
     hashes and process counts equal the registered G54 raw files, and all guards hold.
4. **Counts.** g44 142/142 (failed []); suite 230 checks, 0 failed, 11/11 modules; G45 18, failed [];
   mutations 101/101.
5. **G56 A values and accounting.**
   - The instrument at 70297af (clean) on the registered CSVs reproduces all 20 contrasts exactly:
     - Ms comp +0.3961 [+0.3759, +0.4168]
     - Ms unrel +0.7041 [+0.6988, +0.7101]
     - L1s −1.1257
     - L3s −16.9913
     - L2s −0.5309 (comp) and −0.0009 (unrel)
     - all secondary contrasts
   - The accounting audit on the raw logs:
     - every arm's task + family costs sum to `cpu_total_all_s`;
     - the closing snapshot is charged (added to the last bucket);
     - the first call carries interpreter start-up and imports (Bs unrel seed 191: first task
       29 ms, then 3–4 ms);
     - one server per arm run for every role, B included, so each arm pays one start-up per run;
     - maintenance re-asks are charged identically in both protocols. Calls: comp C/P 168 each,
       F 147; unrel 504 each.
     - Inspections are excluded in Xs, as file reads by the harness are in Xl. Their totals are
       small (Cs about 0.7 s, against 14–49 s).
     - Sealed-answer evaluation calls are excluded in both protocols alike.
   - So the charging is equal as pre-registered.
6. **Records and timeline.**
   - The G55 evidence matches its claims: F8/F32 have 8/8 provisional on all 7 seeds; kept blockers
     are F32 96–99 and F8 32–35; L32 stopped after 2 capabilities.
   - Sealed registry: `sealed_extra.py` reproduces `sealed_tokens_g54_g56.json` byte-for-byte.
     - At ca9f3a1 it covers 161–177 plus dev seeds.
     - Amendment 1 (6d9c1d8, 04:33:43) adds 181–197 before the run at 04:33:49.
     - `teach.py` globs every registry.
     - Seeds 181–197 appear in no other harness.

   | time | event |
   |---|---|
   | 04:00:02 | G55 registered run starts (receipt mtimes 04:00:29 onwards) |
   | 04:00:48 | a0b068f |
   | 04:04:25, 04:07:47 | G56 dev1 and dev2 (dirty, a0b068f; dev seeds 961–964) |
   | 04:20:09 | ca9f3a1 prereg |
   | 04:20:14–04:20:31 | first start, aborted |
   | 04:22:14 | G55 pool raises |
   | 04:27:47 | dev3 (fixed engine, dev seeds) |
   | 04:33:43 | 6d9c1d8 amendment 1 |
   | 04:33:49–04:35:24 | registered run (head 6d9c1d8, clean; load 0.98 → 4.49) |
   | 04:39:24 | d6cbcf3 results |

   - The engine is unchanged between 6d9c1d8 and d6cbcf3.
   - The timeline is consistent with the receipts.
