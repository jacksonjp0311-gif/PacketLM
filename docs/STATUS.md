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
| M4 | Public demo of a receipted loop on a communication task | In progress (two-turn continuation; consistency between turns measured; latest run succeeded) |

## Status
- M0–M3 complete
- M4 in progress
- Latest public run succeeded
- Measurement is recorded; the job finishes either way

## Capabilities
- Holds many compressed binary packets instead of one dense weight set
- Selects relevant packets per step, removes what they covered, and asks again
- Later selections can cover parts the first packet missed
- Measures every probe against an empty baseline and against the single best packet
- Records whether the multi-step path covered at least as much as the first packet
- Records whether any sealed question was answered only when the packets were present
- Produces a two-turn continuation and measures how much of the first turn is still covered by the second
- Runs on ordinary CPU runners
- Leaves an inspectable receipt
- Still a proxy on a few short stories, not a general language model

## Next
Confirm the consistency number is positive on the public artifact, then decide if M4 is complete or needs a stronger multi-turn holdout.
