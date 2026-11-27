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

**Registered run:** pre-registration commit 8fa5c7b. Receipt and raw data are in
`docs/evidence/g47ar/`. Seeds 11, 22, 33, 44 and 55.

**H-AR1, no harm: PASS.** On all 5 seeds, W ≡ K and Y ≡ L in every task row and family
record.

**H-AR2, lower whole-run cost: PASS.** W < K on 5/5 seeds and Y < L on 5/5.

| seed | W/K | Y/L |
|---|---|---|
| 11 | 0.719 | 0.732 |
| 22 | 0.699 | 0.729 |
| 33 | 0.729 | 0.735 |
| 44 | 0.719 | 0.726 |
| 55 | 0.696 | 0.724 |

The ratios use whole-run `cpu_total_s`, which includes startup and maintenance.

**Per seed (acquired / sealed correct / whole-run `cpu_total_s`)**

| seed | K | W | L | Y | Q | M |
|---|---|---|---|---|---|---|
| 11 | 36 / 162 / 10.80 | 36 / 162 / 7.76 | 36 / 162 / 12.51 | 36 / 162 / 9.16 | 15 / 85 / 8.64 | 23 / 121 / 10.00 |
| 22 | 36 / 162 / 10.48 | 36 / 162 / 7.32 | 36 / 162 / 12.45 | 36 / 162 / 9.07 | 15 / 84 / 8.19 | 23 / 118 / 10.09 |
| 33 | 35 / 161 / 10.35 | 35 / 161 / 7.55 | 35 / 161 / 12.38 | 35 / 161 / 9.10 | 15 / 85 / 8.00 | 24 / 121 / 9.81 |
| 44 | 36 / 162 / 11.26 | 36 / 162 / 8.09 | 36 / 162 / 12.50 | 36 / 162 / 9.07 | 15 / 81 / 8.56 | 23 / 118 / 10.30 |
| 55 | 36 / 162 / 10.40 | 36 / 162 / 7.24 | 36 / 162 / 12.33 | 36 / 162 / 8.92 | 15 / 81 / 7.79 | 24 / 121 / 9.59 |

**Reported only:**
- G47 H3 holds on 5/5 seeds.
- Whole-run CPU per acquired capability at depth 3 is L 0.343–0.354, Y 0.248–0.260 and
  M 0.400–0.448. So the library arms are cheaper per acquisition than the primitive-only arm
  under the whole-process, maintenance-inclusive boundary, on all 5 seeds.

**Learning-amortization instrument** (70297af, unmodified; descriptive, not pre-registered):
- export: `la_export.py --total`, giving whole-process `cpu_total_s` per task;
- `A_36(W+maint‖K+maint)` = +0.288 [+0.277, +0.298];
- `A_36(Y+maint‖L+maint)` = +0.271 [+0.267, +0.275];
- both are paired seed bootstraps with S = 5 and sign-flip p = 0.0625, with 1 censored task
  per arm;
- full report: `docs/evidence/g47ar/la_report.txt`.

**Reading.** On the compositional G47 curriculum, adaptive retention lowers whole-process
cost, maintenance and startup included, by about 27–30% with no change to any answer. This is
retention against static, the same learner. It says nothing about beating an empty-state
learner; that comparison was not part of this experiment.
