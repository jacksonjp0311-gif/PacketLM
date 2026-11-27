# PacketLM invariants and emergent behaviour: log and assessment

Analysis date: 2026-11-27 (America/New_York). Base: `g44-canonical-engine` at 8994490 (G57b registered), plus
`g58-wip` at 5366881 (G58 pre-registration draft) for context only. **No engine run was made.** Every number
below is recomputed from published evidence by `docs/invariants/invariants_analysis.py` (stdlib + numpy, about 1 s);
its output is in `docs/invariants/analysis_output.txt`. The one new computation, R1, is a 20,000-sample
simulation of the packet encoder (`packetlm/field.py`), with no state and no timing. Anything marked *guess* is
a hypothesis, not a finding. Instrument: learning-amortization 70297af, with paper v0.2 (98d4455) for Props 7–11.

Legend: **exact** = holds with equality in all data; **approx** = holds within the stated spread;
**fails** = checked and does not hold. **BC** = true by construction (the code or protocol forces it);
**EMP** = empirical (not forced by the code).

## 1. Invariant table

| # | Invariant (precise statement) | Evidence (source → numbers) | Strength | BC / EMP | Implication |
|---|---|---|---|---|---|
| I1 | **Exactness extends to logical work.** Across engine modes (s → i → j), replies, final state bytes *and every logical work counter* are identical. Only CPU per operation changes. | g57b `comp_raw.json.gz`: family counters (evaluations, executions, row_ops, asks, processes, lines) identical i vs j in **126/126** families; run-level interactions, processes and state bytes identical in **28/28** arm×seed pairs. Part S reply and state guards held at every (seed, N) (G57b §6a). G54/G56 hash rechecks are in the ledger. | exact | BC (that is the design goal, enforced by differential tests) | Every efficiency milestone so far is a pure **computational effect** (Tambe et al.): it changes time per step, never the number of steps. Then 1−A_cpu = (1−A_work) × (per-op cost ratio), an instance of Prop 7. G59 can report the two factors separately at no extra cost. |
| I2 | **Chain rule across contrasts on the same seeds.** For example L1j = (Ci+m‖Bi) × (Cj+m‖Ci+m) ÷ (Bj‖Bi). | G57b §6b: 1.801 × 0.959 ÷ 1.030 = **1.677**; measured **1.677**. | exact | BC (Prop 7: ratios of totals) | This is useful as a consistency check on reported tables, not as a discovery. |
| I3 | **The irrelevant-state exponent is invariant across engine modes.** Per-task cost in excess of the N=0 cost grows as N^α with local α(4k→16k) ≈ **1.08–1.10** in every arm. The modes change only the prefactor. | g57 scale Xs 1.079, Xi 1.091; g57b scale Xs 1.094, Xi 1.087, **Xj 1.101**. Prefactor at 16k: Xs 23.7 µs/fact, Xi 12.7, **Xj 0.39** (≈60× smaller). | approx (one 4k→16k step per arm; 7 seeds) | EMP | **This matters most.** G57b's large win (R1k_16000 17.5 → 2.90) is a 60× smaller *coefficient*, **not a smaller exponent**. Xj's 1k–16k log-log slope of 0.38 is a transient: it is the constant term still dominating. By Prop 10, a cost that grows linearly in N without bound means positive asymptotic amortization is impossible under unbounded knowledge growth, whatever the prefactor. *Extrapolation (guess):* Xj ≈ 31 ms per task at N=64k, about 13× N=0. |
| I3a | **Mechanism of I3 (code-level, partly derived).** The exact recall filter (`Memo.recall_candidates`, engine.py:658) visits the 16 posting lists of b_s in `codebits`, whose expected length is 16·|codes|/4096 = |codes|/256. It then adds every triple of any code sharing ≥2 bits with b_s, which happens at a per-code rate of ≈ C(16,2)/256² = 1.8·10⁻³ (R1 simulation: **1.66·10⁻³**). Both terms are linear in the number of codes. | Code plus R1. Linking this to the measured Xj prefactor is a *guess*, because no profile split exists for Xj at 16k. | derived (the scan term is exact; the attribution of Xj's growth is a guess) | BC | Rule F cannot pass with a global inverted index over fixed-width codes. Raising BITS or lowering bits per code shrinks the slope but keeps it linear. A bounded R_N needs **partitioning by relevance** (components or routing, as G58 does for capabilities) so a query never touches unrelated codes. This is the same conclusion as the Bloom-filter and SDM capacity laws (§3). |
| I4 | **The insertion-cost law follows from the per-call law.** The total cost of loading N padding facts scales as N^(1+α_call). | pad_cpu 4k→16k exponents: Xs 2.04–2.05, Xi 2.02–2.03 (α_call ≈ 1.05 → expected 2.05); Xj **1.69** (in between, consistent with its transient). Snapshot ≈ N^1.13–1.22. | approx | BC (integral of per-call cost) + EMP agreement | This is an internal consistency check: two independently timed quantities agree on the same scaling law. The snapshot cost is slightly super-linear (*guess:* JSON serialisation and sort). The 1/64 amortised snapshot therefore grows faster than tasks do, which matters for G59 at large N. |
| I5 | **Teacher-line ratio C/B on comp is invariant across all milestones.** | Lines C/B: G53 0.541, G54 0.539, G56 0.541, G57 0.541, G57b **0.542** (different seeds each time). Excluding C's family-window asks (probes) it is **0.326–0.328**. On unrel, C/B is 3.31–3.32 (1.68 without probes). | exact to ±0.002 | mostly BC: the curriculum and protocol fix which lines B must be re-told, and exact engine changes cannot alter it (I1) | On comp, the persistent learner already needs about ⅓ of the teaching input. **Amortization is positive on a sample-or-teacher resource and negative on CPU.** The paper's A is resource-indexed, so this is a legitimate secondary contrast, but it must be pre-registered and it is largely protocol-determined, so it should not be overclaimed. |
| I6 | **The library cuts search evaluations by a constant factor, but CPU does not follow.** Evaluations C/P ≈ 0.26 on comp in every milestone, while CPU C‖P stays above 1. | Evaluations C/P: 0.270, 0.267, 0.271, 0.264, **0.255**. CPU C+m/P+m: G53 1.16, G54 1.31, G56 1.53, G57 1.42, G57b 1.39. | approx (±0.008) | EMP (the curriculum makes reuse possible; the factor is measured) | This is **the textbook utility problem**, in Tambe's words (cognitive effect positive, computational effect negative) and Francis & Ram's (f_c < 1 but f_a > 1). The saved work is eaten by qualification scans and offering cost (G57b §6c: `_scan` 11.9 of 16.8 s). G58's routing targets exactly this term. Success shows up as CPU C/P moving toward the evaluation ratio. |
| I7 | **Cost ratios are determined by task shape and stable across milestones.** One stratum consistently favours the library, and its advantage grows. | Per-shape C+m/B (G54 → G56 → G57 → G57b): **abca 1.08 → 0.73 → 0.67 → 0.52** (C/P 0.54). cdabc (depth 5) 1.91 → 1.65 → 1.28 → 1.22. dab is 4–11× vs B but only 1.07–1.10 vs P, so it is a persistence-state cost, not library cost. Phase-B shallow tasks (ab, cd, ef, abc) are 1.6–3.7×. | approx (descriptive; not a registered contrast; no CIs) | EMP | **The only place amortization is already positive is the deep-composition stratum, where the library replaces a length-4 primitive search with length 2.** Savings scale with how much search a reused chunk removes, roughly b^L versus (b+k)², not with the count of stored items. For James's threshold hypothesis, this suggests the threshold is in **compositional depth and leverage**, not raw accumulation (*hypothesis*). |
| I8 | **Within a run, C/B worsens as state accumulates.** The per-task slope of log(C/B) is > 0 in 8/8 milestone×curriculum cells. | Slopes per task: comp +0.017 to +0.026; unrel +0.05 to +0.14 (G57b +0.070; C/B by thirds 1.42 → 3.54 → 5.15). Comp has a recurring hump (G56 1.52/2.65/2.14; G57 1.22/2.60/1.75; G57b 1.30/2.57/1.64), but it follows the curriculum's phase structure, not accumulation. | exact sign, 8/8 | EMP | At current scale there is **no sign of a crossover with accumulated count**. The in-curriculum R grows roughly linearly with tasks learned, the in-run face of I3. A crossover needs per-task savings that grow faster than this. |
| I9 | **Outcome counts are invariant to engine mode and nearly invariant across milestones.** C solves 252/252 on comp with 5 provisional; B solves 247/252, and the 5 it misses are ambiguous. | G57b §6b; G57 246 vs 252; G56 247 vs 252 (248 qualified). The same 5 tasks per run are C-provisional and B-ambiguous: cdabc ×3, abca ×2 (g57b raw, seeds 241, 242, 244, 245, 246). | exact across modes (BC via I1); approx across seeds | BC + EMP | This is the censoring pair of Prop 9. The comp contrast is never accuracy-matched, so a G59 claim must use the censoring interval, or the matched 247-task subset as a pre-registered secondary. |
| I10 | **Retention is perfect and interference is zero.** | g57b: retention changed **0/9450** (comp) and **0/21000** (unrel); transfer 1512/1512 correct on comp, 996/1008 on unrel; corrections 12 affected / 12 propagated on comp (G56: 11/11). | exact | BC (exact symbolic store) | There is no catastrophic interference. PacketLM's cost of memory is *time*, not *forgetting*. In complementary-learning-systems terms it has only the fast, non-interfering store and pays for it in retrieval cost (§3). |
| R1 | **The representation density is constant.** A packet is the XOR of three ≈16-bit codes in 4096 bits: popcount 47.55 ± 0.90 (min 41), density ≈ 1.16%. No packet falls below SMALL_PACKET=38. | Simulation from `packetlm/field.py`. | exact in distribution | BC | The density is independent of state size, so the per-item false-match probability is constant and the false-match *count* grows linearly with items (I3a). The guard space (≤ MAX_GUARDS = 8 pairs, programs.py:32), MAX_DEPTH 8 and K=64 are constants, so they are not interesting as invariants. |
| F1 | *Fails:* **a steady per-milestone improvement rate in log(1−A).** | L1 comp ratios: G51 3.87 → G53 1.89 → G54 1.85 → G56 2.13 (protocol change, equal charging) → G57 1.80 → G57b 1.68. ln: 1.35, 0.64, 0.62, 0.76, 0.59, 0.52. Unrel: 6.08, 6.06, 4.31, 18.0, 6.87, 3.21. Within the G56 protocol, comp steps are −0.168 then −0.069. | fails | – | There is no constant rate: one large jump (bounded engine), protocol breaks, then diminishing steps. Fitting an equation across milestones is premature, because seeds and protocols change between points. Only same-protocol chains (G56 → G57 → G57b, linked by M contrasts) are comparable. |
| F2 | *Fails:* **a constant maintenance share.** | Unrel: G51 65%, G56 77%, G57 41%, G57b 41% (1.56/3.85 s). Comp: 10% at G56, 6% at G57 and G57b. | fails | – | Maintenance is a design variable, not a law. It is now under half of unrel cost; per-call state cost dominates. |
| F3 | *Fails:* **the reuse distribution is heavy-tailed or self-organising.** | See E1. | fails | – | See §2. |

## 2. Emergent behaviour (requested 09:23)

Each observation is classed as **E** (genuinely emergent: not specified by code or curriculum), **D** (by design)
or **P** (partly: the structure is designed, the content is discovered).

| # | Observation | Evidence | Class | Cross-domain match |
|---|---|---|---|---|
| E1 | **Capability reuse is flat and fully curriculum-determined.** There are no hubs and no preferential attachment. | g57b Cj comp: over 7 seeds, 105 capabilities are used once, 21 twice and 21 three times. Every seed has the same profile (15/3/3); there is exactly one distinct profile. | **D** (honest negative) | Software call graphs show power-law in-degree, with preferential attachment as a partial explanation (Myers 2003). PacketLM's curriculum is too regular to let that happen. **Suggestion:** a G59 or later curriculum with a skewed or open-ended task distribution is needed before any self-organisation claim can be tested. |
| E2 | **Search depth collapses to a constant 2.** With the library every comp task is found at searched_len 2. B needs 2, 3, 4 or 5 by shape (cdabc 5, abca/bbab/efab 4). | g57b raw, all 252 tasks per arm. | **P**: the library mechanism and curriculum are designed, but which capabilities compose is found by search with no supplied target programs. | This is chunking (Newell & Rosenbloom; Soar) and DreamCoder's library learning, where abstractions make later programs shorter so search is shallower. It is the source of the savings in I6 and I7. |
| E3 | **Accumulated state resolves cases that empty state cannot.** On the same 5 tasks per run where B is *ambiguous*, C answers *provisionally*. | I9. | **P/E**: no code targets those tasks; it follows from having prior capabilities. | Segre et al.'s resource-limit bias: learning can *extend the range of solved problems*, and cost totals mislead when completion differs. That is Prop 9. |
| E4 | **No phase transitions.** Every cost curve is smooth (power law in N, linear in-run trend). The dab spikes (C/B 4–11×) recur at the same curriculum positions in every milestone. | I3, I7, I8. | **D** | There is no criticality or avalanche signature (see E5). The "parabolic turn" James predicted is not visible at current N or task counts. |
| E5 | **Correction cascades are small and one-to-one.** Affected equals propagated, 11–12 per 42 families on comp and 0 on unrel. | I10. | **D** (bounded by dependency structure) | Self-organised criticality would predict heavy-tailed cascade sizes. These are bounded, which is good for soundness and shows no SOC. |
| E6 | **No cross-curriculum transfer.** The library is used 0 times on unrel (G51 L3 note); C‖P on unrel is about 0 (G57b −0.020, G54 −0.015, G57 −0.001). | Ledger and docs. | – (negative) | Transfer learning requires shared structure; the unrel curriculum has none by design. G75–79 territory. |
| E7 | **A shape-specific reuse win grows steadily as overhead is removed.** abca 1.08 → 0.52 over four milestones, without any change to its logic. | I7. | **E** (an unplanned consequence: exact overhead cuts uncover the latent search saving) | Wright and experience-curve form: a fixed saving revealed as overhead falls. It is the closest thing to "compounding" in the data. |

**Proposed per-milestone emergence log** (one JSON line per milestone, appended to
`docs/invariants/emergence_log.jsonl`; every field below can be derived from existing receipts, raw files and
CSVs by extending `invariants_analysis.py`, at zero engine cost):

```
{"milestone","commit","seeds","protocol_id",
 "work":{"evaluations_C/P","lines_C/B","lines_C/B_excl_probes","executions_C/P"},          # I5/I6 (cognitive effect)
 "cpu":{"C/B","C/P","per_op_cost_ratio = cpu_ratio / work_ratio"},                           # I1 decomposition
 "scaling":{"alpha_local_excess","prefactor_us_per_fact","R_N@sizes","snapshot_alpha"},         # I3/I4
 "strata":{"C/B by shape","C/B by B-searched-depth"},                                         # I7
 "in_run":{"slope_log_CB_per_task","C/B_by_thirds"},                                          # I8
 "outcomes":{"solved C/B","qualified","provisional","ambiguous","censored"},                  # I9
 "reuse":{"uses->caps histogram","max_uses","gini","distinct_profiles_across_seeds"},          # E1
 "depth":{"searched_len hist C vs B"},                                                         # E2
 "cascades":{"affected","propagated","max_single_correction"},                                 # E5
 "retention":{"changed/n"},"transfer_unrel_lib_uses":0,                                        # I10/E6
 "notes":"anything not explained by the above (flag; do not chase)"}
```

## 3. Literature map (sources opened 2026-11-27)

| Invariant | Match | Source | Fit | What it suggests |
|---|---|---|---|---|
| I3, I3a, I6, I8 | **Utility problem in EBL**: learned knowledge must save more than the cost of testing whether it applies. PRODIGY kept only rules with positive measured utility. | Minton 1988/1990, https://doi.org/10.1016/0004-3702(90)90059-9 and https://dl.acm.org/doi/10.5555/2887965.2888065 | **strong** | Use utility-filtered retention as a G58/G59 lever (V(p) in Roadmap §4). Paper: cite as prior art for L3 and Prop 10. |
| I1, I6 | **Expensive chunks: cognitive vs computational effect.** Chunking cuts steps but can raise time per step, with slowdowns up to ~4× in the cited summary. The ideal model is constant time per action, achieved by restricting expressiveness so match cost is bounded. | Tambe, Newell & Rosenbloom 1990, https://doi.org/10.1007/bf00117107 | **strong** | Their "ideal computational model" is exactly rule F (bounded R_N). Their fix, restricting representation so match is bounded, maps to partitioned or routed recall. Paper: add the work × per-op decomposition of 1−A. |
| I3, I8 | **Swamping in CBR**: serial retrieval cost is linear in case-base size, so the system swamps when (C_p−C_p′)R_a < ΔR_c. A log-cost memory may never swamp. f_c (work) < 1 while f_a (time) > 1. | Francis & Ram, https://sites.cc.gatech.edu/fac/ashwin/papers/er-93-08.pdf and er-95-02.pdf | **strong** | This is a closed-form threshold condition, a direct analogue of James's crossover. It says crossover needs retrieval cost that is *sublinear* (log) **and** savings per task that do not shrink. Paper Prop 10 is the stricter asymptotic version (bounded). |
| I9, E3 | **Resource-limit bias in EBL evaluations**: cumulative-time comparisons mislead when the solved sets differ; raising the limit flipped a 19% penalty into a net gain. | Segre, Elkan & Russell 1991, https://doi.org/10.1007/bf00114163 | **strong** | This is direct prior art for Prop 9 (censoring interval). Cite it in the paper. |
| I3 (per-concept) | **ACT-R fan effect**: retrieval time rises with the number of facts attached to a concept (~94–119 ms for fan 3 vs 1). | Anderson 1974, https://doi.org/10.1016/0010-0285(74)90021-8 and http://act-r.psy.cmu.edu/book/Chapter3/basic_fan.html | **partial** | Human memory pays per-*concept* fan, not per-total-store. That is the target G58/G59 should aim for: cost depending on the fan of the touched entities, not on N. |
| I3a, R1 | **Bloom-filter false-positive law** (1−e^(−kn/m))^k and **SDM capacity/crosstalk**, set by the number of active bits and stored items. | Broder & Mitzenmacher, https://www.internetmathematicsjournal.com/article/1393.pdf; Kanerva, https://redwood.berkeley.edu/wp-content/uploads/2020/08/KanervaP%5FSDMrelated%5Fmodels1993.pdf | **strong** (same mathematics: fixed-density codes in a shared space mean false matches grow with load) | Fixed BITS=4096 with k≈16 gives a linear false-candidate term. Relevance partitioning or sharding is the standard fix. |
| E2, I7 | **Chunking and the power law of practice**: T = B·N^(−a); chunks reduce processing. | Newell & Rosenbloom 1981, http://shelf2.library.cmu.edu/Tech/7897434.pdf | **partial** | PacketLM's in-run trend is the *opposite sign* (I8). A power law of practice would require repeated, same-structure tasks, which this curriculum lacks. Consider a G59 stratum with repeated task structure. |
| E2, I7 | **DreamCoder library learning**: abstractions deepen the library, so later tasks need shorter programs and shallower search. | Ellis et al. 2021, https://dl.acm.org/doi/10.1145/3453483.3454080 | **strong** (mechanism) | Gains concentrate on deep compositions, matching I7. Stratify G59 by composition depth. |
| E7, F1 | **Wright's law**: unit cost falls as a power of cumulative production; best forecaster across 62 technologies. | Nagy et al. 2013, https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0052669 | **superficial** for now | The milestone series (F1) is not a cumulative-production series: protocols change and there are only 6 points. Revisit only with a same-protocol series. |
| I10 | **Complementary learning systems**: a fast store without interference plus slow consolidation, which avoids catastrophic interference. | McClelland, McNaughton & O'Reilly 1995, https://stanford.edu/~jlmcc/papers/McCMcNaughtonOReilly95.pdf | **partial** | PacketLM has zero interference (I10) but no consolidation step that compacts or partitions old knowledge out of the hot path. A "consolidation" phase moving inactive knowledge into a separate partition is a principled route to bounded R_N (*proposal*). |
| E1 | **Software networks**: power-law reuse and partial preferential attachment. | Myers 2003, https://arxiv.org/pdf/cond-mat/0305575 | **superficial** (no hub formation observed) | Test only with an open-ended curriculum. |

Not searched or not supported: thermodynamics of computation and economic increasing returns. Nothing in the
data maps onto them beyond analogy, so they are left out deliberately.

## 4. Gaps in the amortization theory exposed here

1. **The paper has no per-task savings model.** Prop 10 bounds the overhead side (R_N), but the savings r_i are
   taken as given. The data (I7, E2) show that savings depend on **composition depth and leverage**, not on how
   much is stored. A crossover theorem needs both sides: savings(depth) against R(N). Francis & Ram's threshold
   (C_p−C_p′)R_a < ΔR_c is a ready template.
2. **Work and time are not separated.** I1 and I6 show A_work > 0 (evaluations ×0.26, teacher lines ×0.33)
   while A_cpu < 0. The chain rule gives 1−A_cpu = (1−A_work)·ρ, where ρ is the per-op cost ratio. Stating this
   explicitly would locate the utility problem (Tambe et al.) inside the framework.
3. **Prefactor and exponent are conflated in reporting.** R_N at fixed N (3.75 at 16k) hides the fact that the
   exponent is unchanged (I3). The paper and the G59 gate should report α (local exponent) with an interval, not
   only R_N.

## 5. Suggestions for G59 pre-registration (concrete)

- **S1. Exponent-based scaling criterion.** Report the local exponent α(N₁→N₂) with a bootstrap CI over seeds at
  ≥3 sizes beyond 16k (e.g. 16k/32k/64k, cheap: part S is ~30 s). Register: "bounded" iff the α upper CI < 0.2;
  else report the projected R at the G59 knowledge horizon. Predicted from I3 (*guess*): α ≈ 1 for any engine that
  keeps a global inverted index.
- **S2. Depth-stratified amortization.** Register A(C+m‖B) per B-searched-depth stratum (2/3/4/5) alongside the
  aggregate; prediction from I7: the deepest strata cross zero first (abca already 0.52× at G57b). This is the
  testable form of James's threshold hypothesis: crossover in *depth*, not in raw accumulation.
- **S3. Rate-ratio estimate (James's hypothesis, already queued).** Operationalise "savings-compounding rate" as the
  slope of per-task saving vs depth/leverage, and "overhead-growth rate" as α × prefactor; predict the crossover N
  (or none) before running. Current in-run slope is positive in 8/8 cells (I8), so the honest prior is "no crossover
  at current N".
- **S4. Secondary resources (pre-registered, not primary).** Log `evaluations` and teacher `lines` as extra
  resources in the instrument CSV (it is multi-resource) and report A_work and ρ; note I5 is largely
  protocol-determined.
- **S5. Accuracy matching.** Report the censoring interval (Prop 9) and the matched 247-task subset; the 5
  C-provisional/B-ambiguous tasks are invariant (I9).
- **S6. Fill the emergence log** (§2) at each milestone from receipts; zero extra engine cost.
- **S7. Design implication for G58/G59 engines (not a criterion):** bounded R_N requires recall that never touches
  unrelated codes (relevance partition / consolidation), per I3a and the Bloom/SDM/Tambe literature; reducing the
  coefficient alone cannot satisfy Prop 10.
