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
- shadow m2: 105/105 identical too. m2 Ch flagged: comp 10/246, comprep 11/242, mixed 9/330, long 43/982.
- flagged comp tasks: B-depth 4: 31/63, depth 5: 18/21; carry 1.715 of Bh's 3.08 s task CPU; C saved 1.42 of 1.85 s total task saving (77%) on them. All use the library.
- (3) decode audit: 105/105 reply streams equal registered, both margins; capidx decode filtered by exact list; cap decode checked vs exact copy (HDC never load-bearing for correctness).
- (5) g44 191/191, G45 18/18, suite 11/11 mods 279/0, hdc 13/13, builder mutations 11/12 (investigate_first equivalent: best is None <=> score_b==0). Extra: margin_ignored SURVIVED (equiv at margin 1 only; margin 2 untested), ambiguity_ignored SURVIVED (real gap), 3 others killed.
- DONE: VERIFY_69b5b26.md written (H1 unequal certificate; cc run HOLD comp +0.070, lib -0.005).
