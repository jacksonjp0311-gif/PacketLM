# verify-80cfb17 notes
start 12:01 EST. clone fresh, branch verify-80cfb17 @80cfb17.
## (4) timeline — DONE
prereg 80cda1a 11:19:14 EST; lock 11:19:23–11:52:37; scale receipt head 80cda1a clean, src/engine/harness sha match my recompute at 80cda1a (src ed6079c5, eng 7ded3684, harness g59 ad021378, scale 17e6b36d); source_unchanged True; ref 33565b0 clean; G59.md §1–11 byte-unchanged 80cda1a->80cfb17 (only "(appended after the run)" removed); packetlm/benchmarks unchanged. loadavg start 1.95/2.94/4.31 (decay). Public events API lacks the push times (can't verify push-before-run, only commit-before-lock).
## (2) counts: g44 191/191 failed[], suite 11/11 (279 checks, 0 failed), G45 18/18 — DONE 12:03. mutations running (counts.sh, 4 workers)
## (1) part_diff.py (from routed_diff) arms REF,XR64,XK,XK64,XKP(q=1); dense/block codes; deep pairs/small_part rebuild. runs a/b/c started ~12:20 (run_adv.sh)
math check of §2a: sound (p ⊆ union of 3 codes ≤16 bits; two largest overlaps ≥ k; ≤4 groups ⇒ pigeonhole for k≥5; decode needs |p^q|≤16). memo ent differs (only |p^q|≤16 triples) but only used for decode.
rv exclusion: rv holds fingerprints only; lag legit; only full eval can check → Info.
(correction: adv runs started 12:05, not 12:20)
## (3) recompute — gate_recompute.py, scale_recompute.py: ALL point values reproduce exactly (A per curriculum, strata, rho, rate o/s 2.1049, Q1-4 -> HOLD; part S k 0.507[0.397,0.598], prop 0.494, work 0.082, fixed 1.045; r0 1.319/work 1.246). guards reproduce.
extra: P||B comp -0.13, long -1.05, unrel -1.48 (accumulation w/o library); C||P comp -0.34; maint share Ck unrel 48% (retention probes grow linearly per family); task-only: comp -0.41, unrel -0.30 (Q3 would pass task-only, but Q3 registered +maint & same as G58 L3r), long -1.29.
Ck||Cr unrel -0.148 CI<0: k slower on small states. k at N=0 2.70 vs r 2.36 ms.
cpu_per_call alpha k 0.42; work metric = call+c_call events (1 per builtin regardless of size; py3.13 comprehensions inlined) -> probe work_probe.py pending (wait for load).
(1) p3 block audit 30 sess 2508 calls 0 diffs (3520/3556 partitioned); x1 cross-tree XK64 vs 33565b0 XR64: 60 sess 4874 calls 0 per-call/final/journal diffs. p1,p2,p4,p5 running; mutdiff (5 mutants, no audit, dense) running.
gate protocol: long-lived Server (not process per call); close snapshot charged to last family maint.
ledger "every prediction held except part S point": charged-prop point 0.36[0.28,0.43] vs 0.49 and work 0.10[0.098,0.107] vs 0.082 also outside predicted CIs; comp A -1.07 vs -0.52 -> Low wording.
