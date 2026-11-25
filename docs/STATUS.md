# PacketLM Status

Last updated: 2026-11-25

## Current position

**Milestone: M0–M4 complete**

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0 | Stub router + dummy packet | Done |
| M1 | First language training job that produces a receipt artifact | Done |
| M2 | Eval gate that can reject a run | Done (records result instead of failing the job) |
| M3 | Residual loop improves multi-step holdout | Done |
| M4 | Public demo of a receipted loop on a communication task | Done (second-turn consistency overlap 36, consistent true) |

## Where we are
All planned milestones are complete. The public demonstration produces a two-turn continuation that stays consistent with the first turn. The job records the measurement and does not fail.

## What it is
A small language model that does not store one dense set of weights. It holds many compressed binary packets. When a question or a continuation is asked, a router selects which packets are relevant for that step, removes what they already covered, and asks again. Later selections can cover parts the answer the first packet missed. Every training step and every probe is measured against an empty baseline and against the single best packet. The receipt records whether the multi-step path covered at least as much as the first packet and whether any sealed question was answered only when the packets were present. A short public demonstration produces a two-turn continuation and leaves a receipt showing the second turn still covers the first. It runs on ordinary CPU runners. It is still a proxy on a few short stories, not a general language model.

## Open
- Still a proxy on a few short stories
- No real next-token objective yet
