# verify-80cfb17 notes
start 12:01 EST. clone fresh, branch verify-80cfb17 @80cfb17.
## (4) timeline — DONE
prereg 80cda1a 11:19:14 EST; lock 11:19:23–11:52:37; scale receipt head 80cda1a clean, src/engine/harness sha match my recompute at 80cda1a (src ed6079c5, eng 7ded3684, harness g59 ad021378, scale 17e6b36d); source_unchanged True; ref 33565b0 clean; G59.md §1–11 byte-unchanged 80cda1a->80cfb17 (only "(appended after the run)" removed); packetlm/benchmarks unchanged. loadavg start 1.95/2.94/4.31 (decay). Public events API lacks the push times (can't verify push-before-run, only commit-before-lock).
## (2) counts: g44 191/191 failed[], suite 11/11 (279 checks, 0 failed), G45 18/18 — DONE 12:03. mutations running (counts.sh, 4 workers)
## (1) part_diff.py (from routed_diff) arms REF,XR64,XK,XK64,XKP(q=1); dense/block codes; deep pairs/small_part rebuild. runs a/b/c started ~12:20 (run_adv.sh)
math check of §2a: sound (p ⊆ union of 3 codes ≤16 bits; two largest overlaps ≥ k; ≤4 groups ⇒ pigeonhole for k≥5; decode needs |p^q|≤16). memo ent differs (only |p^q|≤16 triples) but only used for decode.
rv exclusion: rv holds fingerprints only; lag legit; only full eval can check → Info.
