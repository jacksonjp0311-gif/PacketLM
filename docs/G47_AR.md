# G47-AR: G47 with adaptive retention on (pre-registered)

This was written and committed before `benchmarks/g47ar.py` ran on any registered seed. Dev
seed 999 was run first, and its receipt is committed in `docs/evidence/g47ar/dev/`.

## Purpose

This measures G47 (hierarchical reuse under matched budgets) with adaptive retention on,
under the cost rules adopted after the verification of 0b0f6a8:

- **Cost:** whole-process CPU (`cpu_total_s`, process startup included), summed over **every**
  call of the run, maintenance included (M1/M4).
- **Seeds:** 5, namely 11, 22, 33, 44 and 55 (M3). Seeds 44 and 55 are new.
- **Interval labels:** S = 5 is still a small seed sample. Any interval or count is labelled as
  a seed statistic, not timing noise.

This is a new experiment, not a rerun of G47 or ARET. The registered G47 and ARET results stand
as published, with the verification caveats.

## Arms (G46 world, teacher, sequence and budgets, unchanged)

| arm | flags | deepen |
|---|---|---|
| K | (library) | 2 |
| Q | `--no-library` | 2 |
| L | (library) | 3 |
| M | `--no-library` | 3 |
| W | `--adaptive-retention` (= K + retention) | 2 |
| Y | `--adaptive-retention` (= L + retention) | 3 |

The engine is frozen at the commit of this file, and its sha256 is in the receipt.
Retention constants are unchanged from ARET: WINDOW 64, MIN_AGE 8, GUARD 1, R0 4096, RECENT 4.

## Hypotheses (decided as stated; nothing is tuned on these seeds)

- **H-AR1, no harm:** for every seed, W's task rows and family records (acquisition, sealed
  replies, correction, transfer and retention) are identical to K's, and Y's to L's.
- **H-AR2, lower whole-run cost:** whole-run `cpu_total_s` with maintenance and startup is
  lower for W than K on at least 4 of 5 seeds, and lower for Y than L on at least 4 of 5 seeds.
  The ratios are reported per seed.
- **Reported, not thresholds:**
  - G47 H3 (K reaches ≥ 1.5 × Q's depth-2 acquisitions) on all 5 seeds;
  - whole-run CPU per acquired capability for L, Y and M (G47 H5 under the new cost boundary).

H-AR2 can fail. Retention charges restore and archive work to the arm, and on G46-U the
family-end probes forced restores (ARET). Either outcome is recorded.

## Dev run (seed 999, not registered)

- H-AR1 held: W was identical to K, and Y to L.
- Whole-run `cpu_total_s` ratios: W/K = 0.719 and Y/L = 0.721, with 5 archive files each.
- K acquired 36/36 and Q 15/36.
- Whole-run CPU per acquired capability (depth 3): L 0.356, Y 0.256, M 0.419.
- The harness is unchanged after this run.

## Results

(Written after the registered run.)
