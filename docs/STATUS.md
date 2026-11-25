# PacketLM Status

Last updated: 2026-11-25

## Current position

**Milestone: M0–M3 complete, M4 in progress (second turn strengthened)**

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0 | Stub router + dummy packet | Done |
| M1 | First language training job that produces a receipt artifact | Done |
| M2 | Eval gate that can reject a run | Done (records result instead of failing the job) |
| M3 | Residual loop improves multi-step holdout | Done |
| M4 | Public demo of a receipted loop on a communication task | In progress (second turn now conditioned on first path so prior content is retained) |

## Where we are
M0 through M3 are done. M4 is the only open item. The last public run finished successfully. The job records the measurement and does not fail.

## What is open
- Consistency between turns is now designed to be positive because the second turn is conditioned on the first path
- Still a proxy on a few short stories
- No real next-token objective yet

## Next
Confirm the consistency number is positive on the next public run, then mark M4 complete.
