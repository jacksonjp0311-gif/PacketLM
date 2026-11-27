# G44 audit resolution — acceptance criteria

Written before the qualification run. Item numbers follow the overnight
mission's G44 list. Each is a named check in `packetlm/g44_test.py`
(section `audit`) or `packetlm/legacy_checks.py`, and each must be able to fail.
The mutation run in `packetlm/mutations.py` must show it can.

## Uncertainty policy (engine schema 2)

- Contradicted: exactly one defined prediction, different from the answer.
- Undetermined: no prediction, or several (an ambiguous intermediate path).
- Every non-contradicted hypothesis is kept, zero-support ones included.
- Candidate: the unique hypothesis supported by every observation.
- Blocking alternative: another non-contradicted hypothesis with at least one
  supported observation whose predictions differ from the candidate's on some
  entity of the current world.
- No blocking alternatives: **qualified**. Some: **provisional**. It runs, and
  every answer through it says `[provisional]`. Several supported: nothing adopted.

## Criteria

1. Zero-support undetermined hypotheses are kept in the stored hypothesis
   record, and the count matches an independent enumeration.
2. The discovery case leaves an evidenced gap alternative. The result is
   `provisional`, not qualified. Answers say so. Teaching the missing facts
   resolves it to `qualified`.
3. New contradictory evidence suspends a capability. Re-acquisition makes a
   new version. A teacher can revoke.
4. Versions are numbered. Dependents pin `cap:name@v`. Superseding a
   dependency leaves its dependents on the old definition, with the same answers,
   until they are requalified.
5. Primitive relations (`rel:x`) and capabilities (`cap:x@v`) are separate.
   Derived conclusions are stored as `cap:x`, never as primitive `x`. A taught
   primitive and a capability with the same name coexist.
6. Acquiring X never offers a capability whose closure contains X. A cyclic
   state file is rejected on load.
7. A conclusion with two independent paths stores two proofs.
8. Retracting one path keeps the conclusion. Retracting both removes it.
9. When a value is known but no construction exists, the answer says
   `no construction for R`. Inference never borrows another relation's words.
10. Load rejects: a dangling premise, a missing dependency, a duplicate fact,
    a bad version status, a cycle, a checksum mismatch, and a binding mismatch.
    Each is recovered from backup and reported.
11. The three weak historical checks are repaired: `bridge.reloaded` compares
    the reloaded field with what was saved; `qualify.gap_in_loop` checks
    the gap is in each seed's live set; geom's `spoken` check is no longer shadowed.
    The old check names stay.
12. Each of the ten restored legacy modules gets invariant checks that are
    recomputed independently (`packetlm/legacy_checks.py`).
13. Every historical check still passes. Counts are reported.
14. Tests cover an ambiguous intermediate path (undetermined, not supported),
    several conclusions (ambiguous answer), conflicting observations (nothing
    adopted), an unknown oracle answer (no observation recorded), and a
    correction that invalidates an acquired procedure (suspended, then
    re-acquired as v2).

Independent reference: `packetlm/reference.py` (dict-of-sets, no shared code).
Engine execution, judgement and learning must agree with it on every case tested.

## Result

Engine schema 2 (`packetlm/engine.py`), reference `packetlm/reference.py`,
`packetlm/legacy_checks.py`, `packetlm/mutations.py`.

- `python -m packetlm.suite`: 10 of 10 modules pass, with 125 named checks and 0
  failures (historical 47, G44 56, legacy invariants 22). All 10 smoke modules run.
- `python -m packetlm.mutations`: 15 of 15 single mutations are killed
  (`docs/evidence/g44_audit_mutations.json`). Three are killed by a crash rather
  than a named check: no backup fallback, library off, and compose keeping its source.
- Zero-support hypotheses kept: 81 live (72 with zero support) in the 8-relation
  discovery world, equal to the reference's 81.
- Discovery: on all 5 seeds, the target was found in 3 questions, but as
  **provisional**: the `rg+rg` gap is a blocking undetermined alternative. After
  the missing `rg` facts are taught it becomes **qualified**. Under v1 this
  was reported as fully acquired, which the audit correctly rejected.
- Validation rejects 7 of 7 corruption classes and recovers from the backup, with a report.

### Failure evidence

`docs/evidence/g44_audit_run1_failed.json`: in the first run, 1 of 55 failed
(`silent_oracle_adopts_nothing`). This was a real engine bug: `acquire()` overwrote the
hypothesis record and lost the list of questions the oracle could not answer.
It was fixed by carrying the list over. Mutation `unanswered_lost` now guards it.

### Finding

`memory.py`'s own prompt opens 0 packets (0 hops), so its receipt has always
measured nothing. This is recorded in `legacy_receipt.json` findings, not hidden.
