# NOTES verify-69b5b26
- (4) gate m1/m2: all 80 contrasts, csv bytes, outcomes, strata, rate ratio, work split, gate dicts reproduce exactly from registered raw (tools_69b5b26/repro.py, repro_out.json).
- timeline: dev1 12:40:18 ran engine sha 5154308c == 7f06658 (n+1 hard-coded); margin param added ~12:45 (dev_m2 12:45 HOLD); registration 12:51:01; run 12:51:10.
- (4) part S: all summary exponents reproduce exactly from runs.tgz (repro_scale.py).
- (1) shadow audit m1 (shadow_serve.py/shadow_run.py; 105 jobs reply streams+final states byte-identical to registered):
  Ch final qualified that base-language rule (B1) and G59 horizon 5 (B5) call AMBIGUOUS: comp 49/249, comprep 55/249, mixed 43/334, long 220/999, unrel 0/168.
  C5 (own language horizon 5) -> provisional on exactly those. Bh/Ph: 0 disagreements with B5. All are correct programs (acquired=True), 0 wrong.
- substitution (charge Bh cost on flagged tasks): comp A +0.089 [+0.040,+0.168]; lib term +0.028 [-0.038,+0.111]; long +0.025 [-0.001,+0.053]
  with Ph cost: comp +0.095 [+0.028,+0.178]; lib +0.034 [-0.016,+0.110].
- teacher asks m1 comp: Ch 192 vs Bh 302 investigate asks; m2 Ch 281.
- (6) unrel Bh m2: identical evaluations m1/m2 (11547); one task 422 fam20 = 120 ms (vs ~3 ms) + other seeds elevated.
