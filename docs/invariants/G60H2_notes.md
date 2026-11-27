# Invariants notes — G60H2 (2026-11-27)

New observations from the registered G60H2 run (docs/G60H2.md §12; evidence docs/evidence/g60h2/).

1. **Certificate invariance (structural, now measured).** If the uniqueness certificate is an exact
   function of (evidence, facts) — B's base-language rule — then C's verdict, live set and next question
   are B's whatever the library proposes. The library term is then bounded above by 0 minus the proposal
   cost: registered −0.41 [−0.46, −0.36] on comp, negative on every curriculum and at both margins.
   Amortization by a library under an equal certificate requires reusing certificate work (a change in
   what is certified, pre-registered), not a better proposer.
2. **Library-relative certificates are unsafe on decoys.** G60H's +1-in-own-language rule qualified a
   wrong-but-consistent library composition: 68 wrong-qualified sealed answers on the decoy curriculum;
   the equal check: 0.
3. **The library is an accurate prior.** Whenever C adopted a program under the equal check, its
   proposal equalled the certified tuple (0 differences; 370–2749 certificate runs per curriculum).
4. **Meet-in-the-middle ≡ DP.** The MITM base certificate reproduces the DP's verdict, tuples and
   lexicographically-first shortest representatives (105/105 identical reply streams; random-world test)
   at ≈ 0.6–0.8× the CPU. Kept as an invariant: any certifier change must pass the d = e differential.
5. **Representation.** For exact symbolic memory at this scale, plain dicts/sets dominate the sparse
   block codes (≈ 1.5–2× less CPU, identical answers). The G60H step-cost gain belongs to the engine
   (hash-keyed memory, deduplicated tuple search), not to hypervectors.
6. **Counters.** With every hypervector read checked against an exact copy, all error counters were 0 at
   K=32, L=64 in every registered run; at K=2, L=4 every collision kind occurs, is counted and loses no
   answer (unit test).
