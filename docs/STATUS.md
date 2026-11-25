# PacketLM Status

Last updated: 2026-11-25

## Current position

**Milestone: M0–M3 complete, M4 in progress**

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0 | Stub router + dummy packet | Done |
| M1 | First language training job that produces a receipt artifact | Done |
| M2 | Eval gate that can reject a run | Done (records result instead of failing the job) |
| M3 | Residual loop improves multi-step holdout | Done (gate passed on public run) |
| M4 | Public demo of a receipted loop on a communication task | In progress (two-turn continuation; consistency between turns now measured) |

## The system

A small language model that does not store one dense set of weights. It holds many compressed binary packets. When a question or a continuation is asked, a router selects which packets are relevant for that step, removes what they already covered, and asks again. Later selections can cover parts of the answer the first packet missed. Every training step and every probe is measured against an empty baseline and against the single best packet. The receipt records whether the multi-step path covered at least as much as the first packet and whether any sealed question was answered only when the packets were present. The job itself finishes either way. A short public demonstration produces a two-turn continuation and leaves a receipt that now includes how much of the first turn is still covered by the second. The whole thing runs on ordinary CPU runners. It is still a proxy on a few short stories, not a general language model.

## Next

Confirm the consistency number is positive on a public run. Then decide whether M4 is complete or needs a stronger multi-turn holdout.
