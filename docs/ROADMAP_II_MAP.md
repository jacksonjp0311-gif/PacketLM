# Roadmap II: mapping from this repository's experiment numbers to its objectives

`docs/ROADMAP_II.txt` is the master roadmap adopted by James at 05:12 EST on 2026-11-27 (drafted
externally, endorsed by James; copied verbatim except for the line-number prefixes of the notes
copy). It is a dependency structure, not a race. Existing experiment numbering is kept; where the
roadmap's numbers and ours differ, this file maps between them.

| roadmap objective | roadmap § | this repository | status |
|---|---|---|---|
| G44–56 foundations and qualification | 2 | G44–G56 (ledger; docs/G44.md … docs/G56.md) | established foundations; positive amortization not qualified (G56: C 2.13× B comp, 18.0× unrel) |
| **G57 selective computational activation** (relation/entity/component/dependency indexes, evidence-gated rechecks, incremental verification, exactness against the exhaustive reference, index costs, scaling vs irrelevant knowledge) | 3 | **G57** (docs/G57.md): `--indexed` (relation-grouped rows, memoized recall, component classes, evidence-gated re-asks) + part S (scaling against padded unrelated state) | this chunk; pre-registered |
| not yet covered within G57 | 3 | entity/dependency indexes beyond the answer fingerprint, incremental fact index, incremental (delta) validation, sparse geometric activation, localized candidate generation | next chunk(s), each pre-registered |
| G58 adaptive capability economics (V(p), active/dormant/provisional/suspended/archived, capability routing so unrelated procedures do not enlarge search) | 4 | planned as G58; builds on `--adaptive-retention` (packetlm/retention.py, G45/G47-AR) | queued |
| G59 learning-amortization qualification gate (break-even, marginal, tail, novelty-stratified; exact thresholds pre-registered; HOLD allowed) | 5 | planned as G59; instrument learning-amortization 70297af unless James changes it | queued |
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
