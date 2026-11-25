# PacketLM Status

Last updated: 2026-11-25

## Current position

**Milestone: M0–M2 complete, M3 in progress, M4 in progress**

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0 | Stub router + dummy packet | Done |
| M1 | First language training job that produces a receipt artifact | Done |
| M2 | Eval gate that can reject a run | Done |
| M3 | Residual loop improves multi-step holdout | In progress (hop improvement = higher overlap from path union than single-select) |
| M4 | Public demo of a receipted loop on a communication task | In progress (two-turn continuation selected by residual path union) |

## What is running today

- Corpus: small TinyStories slice (`data/tinystories_slice.txt`), windowed into short segments.
- Training: overlap-proxy steps on the windows. Receipt written to `artifacts/receipt.json`.
- Measurement: hop effect (single-select vs residual hop count) recorded every 10 steps.
- Probes: sealed set in `data/probes.json` (language + understanding + reasoning + communication continuation). Evaluated with twin measurement (field vs cold empty router). Certified only if field hits and cold fails.
- Ablation: path union must produce higher overlap with the expected than single-select on requires_hop probes. Receipt records sums, probes_improved, and `hops_improve`.
- Residual hop: AND-NOT winner bits, collects diverse packets, accumulates union via `path_union`.
- Hash: token feature bits injected so a window containing an expected word overlaps that word's packet.
- Gate: hard reject — process exits non-zero unless probes certify **and** residual path covers more than single-select. Receipt records `gate_passed` and status.
- Demo: `python -m packetlm.demo` produces a two-turn continuation, each turn selected by residual path union, and writes `artifacts/demo_receipt.json`. Runner executes it and uploads the artifact.
- Runner: `.github/workflows/train.yml` executes the language stub + demo and uploads both receipts (will fail the job on gate reject; demo still runs).
- Claim boundary: still a proxy on a tiny slice. Not a real language model.

## Analysis

Token feature bits made field certification possible but also made single-select succeed too often, so binary hit-rate delta stayed zero. Ablation now measures raw overlap: path union improves if it covers more of the expected than the single winner. Gate still demands both certification and a positive coverage delta.

## Plan to finish

1. Token feature bits (done).
2. Hop improvement measured by higher residual coverage (done).
3. Public run — confirm gate passes.
4. Measure second-turn consistency.
5. Mark M3 complete once the gate passes publicly.

## Open design questions (unchanged)

- Router conditioning on residual state while remaining Hamming-exact.
- Exact form of the surprise signal for memory writes.
- When to move from proxy overlap to a real next-token objective.
