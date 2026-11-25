# PacketLM Status

Last updated: 2026-11-25

## Current position

**Milestone: M0 complete, M1 in progress (language phase)**

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0 | Stub router + dummy packet | Done |
| M1 | First language training job that produces a receipt artifact | In progress |
| M2 | Eval gate that can reject a run | Not started |
| M3 | Residual loop improves multi-step holdout | Not started |
| M4 | Public demo of a receipted loop on a communication task | Not started |

## What is running today

- Corpus: small TinyStories slice (`data/tinystories_slice.txt`), windowed into short segments.
- Training: overlap-proxy steps on the windows. Receipt written to `artifacts/receipt.json`.
- Measurement: hop effect (single-select vs residual hop count) recorded every 10 steps.
- Runner: `.github/workflows/train.yml` executes the language stub and uploads the receipt.
- Claim boundary: still a proxy on a tiny slice. Not a real language model.

## Next concrete step

Add a continuation probe and a first understanding check into the training run so the receipt shows whether the field retrieves the right next window and whether residual hops change that retrieval. Then seal the probe set.

## Open design questions (unchanged)

- Router conditioning on residual state while remaining Hamming-exact.
- Exact form of the surprise signal for memory writes.
- When to move from proxy overlap to a real next-token objective.
