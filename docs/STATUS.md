# PacketLM Status

Last updated: 2026-11-25

## Current position

**Milestone: M0–M1 complete, M2 complete, M3 in progress**

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0 | Stub router + dummy packet | Done |
| M1 | First language training job that produces a receipt artifact | Done |
| M2 | Eval gate that can reject a run | Done (rejects on zero certified probes) |
| M3 | Residual loop improves multi-step holdout | In progress (gate now also demands positive hop delta; multi-hop probe present) |
| M4 | Public demo of a receipted loop on a communication task | Not started |

## What is running today

- Corpus: small TinyStories slice (`data/tinystories_slice.txt`), windowed into short segments.
- Training: overlap-proxy steps on the windows. Receipt written to `artifacts/receipt.json`.
- Measurement: hop effect (single-select vs residual hop count) recorded every 10 steps.
- Probes: sealed set in `data/probes.json` (language continuation + understanding + one reasoning probe marked `requires_hop`). Evaluated with twin measurement (field vs cold empty router). Certified only if field hits and cold fails.
- Ablation: hop-depth comparison on probes (single-select hit rate vs residual-hop hit rate). Receipt records delta, `hops_improve`, and `m3_ready`.
- Residual hop: AND-NOT winner bits, avoids immediate repeats, stops on empty residual or non-positive score.
- Gate: hard reject — process exits non-zero unless probes certify **and** hops improve. Receipt records `gate_passed` and status.
- Runner: `.github/workflows/train.yml` executes the language stub and uploads the receipt (will fail the job on reject).
- Claim boundary: still a proxy on a tiny slice. Not a real language model.

## Next concrete step

Make the residual hop reliably produce a positive delta on the reasoning probe (so the gate can pass). Then add a communication continuation probe for M4.

## Open design questions (unchanged)

- Router conditioning on residual state while remaining Hamming-exact.
- Exact form of the surprise signal for memory writes.
- When to move from proxy overlap to a real next-token objective.
