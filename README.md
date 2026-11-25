# PacketLM

A language model assembled from routed binary weight packets instead of one dense slab.

**Bitwork geometry core**: 4096-bit sparse patterns, Hamming-space nearest neighbor (overlap = |q| − H(q, p)), temporal routing that pulls packets per step, eval-gated promotion. CPU-runner trainability. Local-first. Evidence-gated. No auto-promotion.

## What this is

PacketLM is a looped, memory-native transformer-style model whose weights are not a single dense matrix. They are addressable packets. A router selects which packets participate in each residual hop. Memory lives inside the packet store. Every promotion is a sealed twin measurement with an inspectable receipt.

This is not a dense LLM with a side-car memory. The substrate is the same integer Hamming geometry used in Bitwork / Perci. Soft binding is approximated by packet selection + residual hops rather than floating-point attention.

## Architecture (current plan)

1. **Embedding / encoder** — maps tokens to sparse 4096-bit patterns (FNV-1a features + structural cues).
2. **Packet store** — collection of weight packets (bit sets + counts). Domain packets, learned packets, storage packets.
3. **Temporal router** — per-step selection of which packets to pull, conditioned on residual state. Must preserve Hamming exactness.
4. **Residual loop** — AND-NOT the winner’s bits, re-query. Bounded iterations.
5. **Parametric memory** — storage packets that can be written under a governed rule (surprise / residual threshold + sealed gate).
6. **Readout** — integer overlap scores → next-token distribution (or deterministic argmax for first versions).

## Training plan

- Phase 1: language on TinyStories-scale data. Prove the loop reaches lower loss than a non-looped baseline under identical seeds.
- Phase 2: bolt residual hops and measure multi-step coherence on held-out sequences.
- Phase 3: sealed reasoning probes. Promotion only on twin (cold vs field) certified delta.
- Compute: public GitHub Actions CPU runners for sub-10M parameter models. Artifacts hold checkpoints and receipts.

## Governance (non-negotiable from day one)

- Seed recorded. Eval gate pre-registered. Promotion only on sealed twin measurement.
- Every packet pull logged. Every write is a proposal until the gate passes.
- Claim boundary: this is a packet-routed integer model, not AGI, not consciousness.

## Milestones

- M0: stub router + one dummy packet (this commit series)
- M1: first training job on a public runner that produces a loss curve artifact
- M2: eval gate that can reject a run
- M3: residual loop demonstrably improves multi-step holdout
- M4: public demo of a receipted loop

## Run

```bash
git clone https://github.com/jacksonjp0311-gif/PacketLM
cd PacketLM
python -m packetlm.router --demo
```

(Implementation in progress.)

---

Local-first. Evidence-gated. Receipts stay inspectable.
