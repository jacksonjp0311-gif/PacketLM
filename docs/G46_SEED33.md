# The G46 seed-33 threshold-6 failure: mechanism (analysis only; the registered result stands)

**Reproduce:** run `python3 benchmarks/seed33_mechanism.py` after a G46 run (engine v4). It reads
`artifacts/g46/seed33/C.json` and does not change it.

## What failed

Task: family 4, task 5, shape `cdabc`, name `bbtwyr`.
- The hidden program is `uxbylp umhlnx yaqakx hrjpgy uxbylp`.
- Arm C ended the task `ambiguous`, with more than one supported program and none adopted.
- Its sealed query `bpapsg` has an ambiguous truth (`fasvss` or `qzihwn`). It was answered
  `unknown`, but threshold 6 requires `ambiguous`.

## Mechanism

1. **Several programs remain supported.** In C's final state there are three:
   - `cap:dditje@1 + cap:vomvnu@1`, which expands to the hidden program;
   - `rel:uxbylp + cap:fukpwk@1`;
   - `rel:umhlnx + cap:fukpwk@1`.
2. **No answerable question can separate them.** The script checks every subject where the
   candidates disagree; the "answerable discriminators" list is empty. There is no non-sealed
   subject whose true answer is a single value and contradicts a wrong candidate.
   - Where a wrong candidate gives a value and the hidden program differs, the hidden program
     is either undefined there (`ozvihs`, `rlgpry`, `vmtlio`, `wzerbk`; phase B removes 15% of
     edges) or ambiguous there (`kypodt`, `vngduk`).
   - Where the hidden program has a single value that a wrong candidate lacks (`ucfmus`), the
     wrong candidate is undefined. Under the uncertainty policy that is "undetermined", not a
     contradiction.
3. **The teacher protocol cannot carry the evidence that separates them.**
   - G46's teacher says `unanswered NAME: s` both when the truth has no single value and when
     `s` is sealed.
   - The engine records `unanswered` but treats it as no information. It must, because
     `unanswered` also covers withheld (sealed) subjects whose true answer may be a single value.
   - C asked `ozvihs` (undefined) and `lumuyl` (sealed and undefined). Both were unanswered.
   - `investigate` scores only subjects where two candidates give different *defined* values.
     After those two questions none was left, and the loop ended.
4. **The reply is consistent with that state.** With an unadopted, ambiguous capability, the
   engine says `unknown` instead of choosing between candidates. At `bpapsg` the candidates
   predict nothing, nothing and {fasvss, qzihwn}, so the engine cannot honestly say `ambiguous`
   either.

## Reading

This is not a search or qualification bug. The task is not identifiable from single-value
answers alone. The missing ingredient is **negative evidence**: "s has no value" or "s has
several values", stated by a teacher who is not withholding. That would contradict every
candidate that gives exactly one value at `ozvihs`, `kypodt` or `vngduk`.

## What I am not doing

- I am not changing threshold 6.
- I am not re-scoring G46.
- I am not letting `unanswered` count as negative evidence. That would be wrong for withheld
  subjects.

**Possible protocol extension** (future, pre-registered separately; not applied to G46):
1. Add a teacher statement `example NAME: s -> none` for "no value", and `-> several` for
   "more than one value".
2. Keep it distinct from `unanswered`, which means withheld.
3. Judge it as a contradiction against any single-valued prediction.
