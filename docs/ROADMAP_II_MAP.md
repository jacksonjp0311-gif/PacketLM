# Roadmap II: mapping from this repository's experiment numbers to its objectives

`docs/ROADMAP_II.txt` is the master roadmap adopted by James at 05:12 EST on 2026-11-27 (drafted
externally, endorsed by James; copied verbatim except for the line-number prefixes of the notes
copy). It is a dependency structure, not a race. Existing experiment numbering is kept; where the
roadmap's numbers and ours differ, this file maps between them.

| roadmap objective | roadmap § | this repository | status |
|---|---|---|---|
| G44–56 foundations and qualification | 2 | G44–G56 (ledger; docs/G44.md … docs/G56.md) | established foundations; positive amortization not qualified (G56: C 2.13× B comp, 18.0× unrel) |
| **G57 selective computational activation** (relation/entity/component/dependency indexes, evidence-gated rechecks, incremental verification, exactness against the exhaustive reference, index costs, scaling vs irrelevant knowledge) | 3 | **G57** (docs/G57.md): `--indexed` (relation-grouped rows, memoized recall, component classes, evidence-gated re-asks) + part S (scaling against padded unrelated state) | done (35bda6b): Mi claimed, rule F failed (R_16000 = 91.9) |
| G57b (within G57) | 3 | **G57b** (docs/G57b.md): `--incremental` persistent fact index, change-scoped validation (full every 64 calls), exact recall candidate filter, sparse scan tables | done: material (R1k_16000 2.90, was 17.5), rule F still fails; L1j 1.68×, L3j 3.21× |
| not yet covered within G57 | 3 | entity/dependency indexes beyond the answer fingerprint, sublinear candidate generation, sparse geometric activation | later, each pre-registered |
| G58 adaptive capability economics (V(p), active/dormant/provisional/suspended/archived, capability routing so unrelated procedures do not enlarge search) | 4 | planned as G58; builds on `--adaptive-retention` (packetlm/retention.py, G45/G47-AR) | **done (G58, docs/G58.md)**: exact capability routing `--routed` (review, capability index for offered/scan/activation, growth routing); library-scaling material (Xr R64_1024 1.99 vs 14.74), not flat; L1r −0.744, L3r −1.898 no claim; Mr unrel +0.094 claimed; scoped requalification and V(p) retention deferred |
| G59 learning-amortization qualification gate (break-even, marginal, tail, novelty-stratified; exact thresholds pre-registered; HOLD allowed) | 5 | **G59** (docs/G59.md): `--partitioned` exact recall + verify-33565b0 folds + proportional maintenance; gate Q1–Q4 over comp/comprep/unrel/mixed/long, depth strata, padding exponent, work/time split, rate ratio; instrument 70297af | **done: HOLD, switch rule triggered** (comp A −0.518 [−0.611, −0.434]; no stratum qualified, depth 5 at −0.011 [−0.104, +0.066]; padding α_task 0.51 [0.40, 0.60] not bounded, α_work 0.08 bounded; long diverging, no crossover). Next per the switch rule: an alternative mathematical approach, same instrument and verification |
| switch-rule evaluation after G59 (alternative mathematical approach, same instrument; route chosen by James 2026-11-27: fixed-width HDC / VSA codes) | 5 (switch rule, G58 §8 / G59 §8) | **G60H** (docs/G60H.md): `packetlm/hdc/` sparse block codes (K=32×L=64), fact memory keyed by bound codes, capabilities as composed hypervectors, local capability index; G59 gate protocol, part S, decomposition, margin-2 robustness, capacity sweep | **done: PASS at margin 1, HOLD at margin 2 (conditional)** — comp A +0.550 [+0.523, +0.572] (library term +0.519), every compositional curriculum and stratum positive, long crosses zero (o/s 0.64); padding α_task 0.004 (bounded); ρ 1.35 (G59 12.9); margin 2: comp −0.007, only depth 5 positive; 0 decode errors. Next: cheap uniqueness certification before scaling. "H" keeps the number apart from roadmap §6's G60 |
| G60–64 algorithmic intelligence | 6–10 | partial precursors: G48 programs (`prog:`), G49 exact scan, G55 closed-guard budget; `until` operator | later band |
| G65–69 language | 11–15 | precursors: constructions/`express`/lexicon (G44) | later band |
| G70–74 adaptive learning (G74 learning-to-learn gate) | 16–20 | – | later band |
| G75–79 transfer | 21–25 | – | later band |
| G80–84 bounded self-improvement (the candidate never controls its own verifier) | 26–30 | – | later band |
| G85–90 generalization qualification | 31 | – | later band |

Queued from the d6cbcf3 audit for later chunks: a competitive indexed symbolic-execution
baseline (a fair non-Bitwork comparator), sparse geometric activation of relevant capabilities,
adaptive capability routing.

Number collision note: G55 in this repository is the closed-guard-budget experiment
(docs/G55.md), not a roadmap objective; G57's number coincides with the roadmap's G57 by design.
