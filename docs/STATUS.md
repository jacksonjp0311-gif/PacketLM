# PacketLM Status

Last updated: 2026-11-25

## Current position

**Milestone: M0–M2 complete, M3 in progress, M4 in progress**

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0 | Stub router + dummy packet | Done |
| M1 | First language training job that produces a receipt artifact | Done |
| M2 | Eval gate that can reject a run | Done |
| M3 | Residual loop improves multi-step holdout | In progress (residual hop takes next unused packet; multi-hop covering at least as much counts as improvement) |
| M4 | Public demo of a receipted loop on a communication task | In progress (two-turn continuation selected by residual path union) |

## What is running today

- Corpus: small TinyStories slice (`data/tinystories_slice.txt`), windowed into short segments.
- Training: overlap-proxy steps on the windows. Receipt written to `artifacts/receipt.json`.
- Measurement: hop effect (single-select vs residual hop count) recorded every 10 steps.
- Probes: sealed set in `data/probes.json` (language + understanding + reasoning + communication continuation). Evaluated with twin measurement (field vs cold empty router). Certified only if field hits and cold fails.
- Ablation: multi-hop that covers at least as much of the expected as single-select counts as improvement. Receipt records per-probe overlaps, path lengths, and `hops_improve`.
- Residual hop: AND-NOT winner bits, always takes next unused packet when residual remains.
- Hash: token feature bits injected so a window containing an expected word overlaps that word's packet.
- Gate: hard reject — process exits non-zero unless probes certify **and** residual path shows multi-hop coverage. Receipt records `gate_passed` and status.
- Demo: `python -m packetlm.demo` produces a two-turn continuation, each turn selected by residual path union, and writes `artifacts/demo_receipt.json`. Runner executes it and uploads the artifact.
- Runner: `.github/workflows/train.yml` executes the language stub + demo and uploads both receipts (will fail the job on gate reject; demo still runs).
- Claim boundary: still a proxy on a tiny slice. Not a real language model.

## Plan — adapt, improvise, overcome

1. Residual hop always takes next unused packet when residual remains (done).
2. hops_improve if multi-hop covers at least as much as single (done).
3. Detailed per-probe numbers in receipt (done).
4. Public run — confirm gate passes.
5. Measure second-turn consistency.
6. Mark M3 complete once the gate passes publicly.

## Open design questions (unchanged)

- Router conditioning on residual state while remaining Hamming-exact.
- Exact form of the surprise signal for memory writes.
- When to move from proxy overlap to a real next-token objective.
