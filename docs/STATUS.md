# PacketLM Status

Last updated: 2026-11-25

## Current position

**Milestone: M0 complete, M1 in progress (language phase with sealed probes)**

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0 | Stub router + dummy packet | Done |
| M1 | First language training job that produces a receipt artifact | In progress |
| M2 | Eval gate that can reject a run | Not started (twin eval present, gate logic next) |
| M3 | Residual loop improves multi-step holdout | Not started |
| M4 | Public demo of a receipted loop on a communication task | Not started |

## What is running today

- Corpus: small TinyStories slice (`data/tinystories_slice.txt`), windowed into short segments.
- Training: overlap-proxy steps on the windows. Receipt written to `artifacts/receipt.json`.
- Measurement: hop effect (single-select vs residual hop count) recorded every 10 steps.
- Probes: sealed set in `data/probes.json` (language continuation + understanding). Evaluated with twin measurement (field vs cold empty router). Certified only if field hits and cold fails.
- Runner: `.github/workflows/train.yml` executes the language stub and uploads the receipt.
- Claim boundary: still a proxy on a tiny slice. Not a real language model.

## Next concrete step

Turn the twin probe results into a hard gate that can reject the run (M2). Then measure whether residual hops improve certified probe accuracy over single-select (path to M3).

## Open design questions (unchanged)

- Router conditioning on residual state while remaining Hamming-exact.
- Exact form of the surprise signal for memory writes.
- When to move from proxy overlap to a real next-token objective.
