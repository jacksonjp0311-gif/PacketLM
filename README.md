# PacketLM

A language model assembled from routed binary weight packets instead of one dense slab.

**Primary focus**: language learning, understanding, reasoning, and communication.

Bitwork geometry core: 4096-bit sparse patterns, Hamming-space nearest neighbor (overlap = |q| − H(q, p)), temporal routing that pulls packets per step, eval-gated promotion. CPU-runner trainability. Local-first. Evidence-gated. No auto-promotion.

## Current status

See [docs/STATUS.md](docs/STATUS.md). M0 done. M1 (language phase with receipt) in progress.

## What this is

PacketLM trains first on the things that make communication work: syntax, meaning, multi-step reasoning, and the ability to answer or continue a thought without collapsing into noise. The weights are addressable packets. A router selects which packets participate in each residual hop. Memory lives inside the packet store. Every promotion is a sealed twin measurement with an inspectable receipt.

This is not a dense LLM with a side-car memory. The substrate is the same integer Hamming geometry used in Bitwork / Perci. Soft binding is approximated by packet selection + residual hops rather than floating-point attention.

## Training focus (in order)

1. **Language** — TinyStories-scale and similar clean, vocabulary-constrained text. Prove the model absorbs syntax and local coherence.
2. **Understanding** — questions that require retrieving and combining facts already present in the packet store. Sealed holdouts that cold-start cannot answer.
3. **Reasoning** — multi-step sequences where residual hops must improve accuracy over a single-hop baseline.
4. **Communication** — continuation, clarification, and simple dialogue turns that stay consistent with prior context.

Only after these loops are measurable do we expand into other domains.

## Architecture (current plan)

1. **Embedding / encoder** — maps tokens to sparse 4096-bit patterns (FNV-1a features + structural cues).
2. **Packet store** — collection of weight packets (bit sets + counts). Domain packets, learned packets, storage packets.
3. **Temporal router** — per-step selection of which packets to pull, conditioned on residual state. Must preserve Hamming exactness.
4. **Residual loop** — AND-NOT the winner’s bits, re-query. Bounded iterations. This is the reasoning substrate.
5. **Parametric memory** — storage packets that can be written under a governed rule (surprise / residual threshold + sealed gate).
6. **Readout** — integer overlap scores → next-token distribution (or deterministic argmax for first versions).

## Governance (non-negotiable from day one)

- Seed recorded. Eval gate pre-registered. Promotion only on sealed twin measurement.
- Every packet pull logged. Every write is a proposal until the gate passes.
- Claim boundary: this is a packet-routed integer model focused on language and reasoning, not AGI, not consciousness.

## Milestones

- M0: stub router + one dummy packet (done)
- M1: first language training job on a public runner that produces a loss curve artifact (in progress)
- M2: eval gate that can reject a run
- M3: residual loop demonstrably improves multi-step holdout on understanding/reasoning probes
- M4: public demo of a receipted loop on a communication task

## Run

```bash
git clone https://github.com/jacksonjp0311-gif/PacketLM
cd PacketLM
python -m packetlm.train
```

(Implementation in progress.)

---

Local-first. Evidence-gated. Receipts stay inspectable.
