# PacketLM Status

Last updated: 2026-11-25

## Current position

**Milestone: M0–M2 complete, M3 in progress, M4 in progress**

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0 | Stub router + dummy packet | Done |
| M1 | First language training job that produces a receipt artifact | Done |
| M2 | Eval gate that can reject a run | Done |
| M3 | Residual loop improves multi-step holdout | In progress (gate demands positive hop delta; path union + sparser hash) |
| M4 | Public demo of a receipted loop on a communication task | In progress (two-turn continuation selected by residual path union; receipt uploaded by runner) |

## What is running today

- Corpus: small TinyStories slice (`data/tinystories_slice.txt`), windowed into short segments.
- Training: overlap-proxy steps on the windows. Receipt written to `artifacts/receipt.json`.
- Measurement: hop effect (single-select vs residual hop count) recorded every 10 steps.
- Probes: sealed set in `data/probes.json` (language + understanding + reasoning + communication continuation). Evaluated with twin measurement (field vs cold empty router). Certified only if field hits and cold fails.
- Ablation: hop-depth comparison using path union. Receipt records delta, `hops_improve`, and `m3_ready`.
- Residual hop: AND-NOT winner bits, avoids repeats, accumulates union via `path_union`.
- Hash: sparser feature hash so residual bits remain for later hops.
- Gate: hard reject — process exits non-zero unless probes certify **and** hops improve. Receipt records `gate_passed` and status.
- Demo: `python -m packetlm.demo` produces a two-turn continuation, each turn selected by residual path union, and writes `artifacts/demo_receipt.json`. Runner executes it and uploads the artifact.
- Runner: `.github/workflows/train.yml` executes the language stub + demo and uploads both receipts (will fail the job on gate reject; demo still runs).
- Claim boundary: still a proxy on a tiny slice. Not a real language model.

## Next concrete step

Confirm the gate can pass on a public run. Then measure whether the second turn stays consistent with the first (multi-step communication score).

## Open design questions (unchanged)

- Router conditioning on residual state while remaining Hamming-exact.
- Exact form of the surprise signal for memory writes.
- When to move from proxy overlap to a real next-token objective.
