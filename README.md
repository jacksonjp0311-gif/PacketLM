# PacketLM

![Field](docs/field.jpg)

PacketLM is a non-transformer **Bitwork** learning engine. Knowledge lives in sparse binary geometric representations. A query activates only what matches; the rest stays closed. There is no transformer and no external LLM runtime.

It is a research engine, not a general intelligence and not a mind.

## The question

Can a system get cheaper at learning the more it learns?

That is measured as **learning amortization**:

```text
A = 1 − C_cont / C_base
```

`C_cont` is the full cost of a continual learner on a task sequence. `C_base` is the cost of a reference learner (starting empty) on the same sequence, at matched accuracy. `A > 0` means past learning paid for part of later learning. `A < 0` means the learned material costs more to keep and consult than it saves.

The instrument and the paper are in [learning-amortization](https://github.com/jacksonjp0311-gif/learning-amortization) (working paper v0.1). PacketLM runs pin the instrument at tag [`instrument-v1`](https://github.com/jacksonjp0311-gif/learning-amortization/tree/instrument-v1) (commit `70297af`), used unmodified.

## How results are produced

- Predictions and decision rules are **pre-registered** before a registered run.
- Registered runs use **fresh seeds**. Dev-seed numbers are not evidence.
- **Failures are kept**, not rerun away.
- A **builder** and an independent **verifier** work separately. Verifier reports live on `verify-*` branches.
- Engine modes that claim to be cheaper must stay **byte-exact**: the same replies and, where required, the same saved state as the prior mode.

## Current status

As of 27 November 2026 (America/New_York): **no registered experiment has shown positive learning amortization.** **G59** gate: **HOLD** (no positive amortization qualified, comp A −0.52, deepest stratum at break-even). The switch rule triggered. An alternative representation (hyperdimensional codes) prototype is under way. Results are in [`docs/G59.md`](https://github.com/jacksonjp0311-gif/PacketLM/blob/main/docs/G59.md); independent check on branch [`verify-80cfb17`](https://github.com/jacksonjp0311-gif/PacketLM/tree/verify-80cfb17).

Active development is on branch [`g44-canonical-engine`](https://github.com/jacksonjp0311-gif/PacketLM/tree/g44-canonical-engine), opened as [PR #1](https://github.com/jacksonjp0311-gif/PacketLM/pull/1). This `main` branch still holds the earlier packet-field demo described further below.

### Results, G51–G58

The figures below are taken from the registered-result sections of `docs/G51.md`–`docs/G58.md` on `g44-canonical-engine` (G58 results registered at `33565b0`; later commits on that branch add a G58 erratum and the G59 pre-registration). Cost ratio is `1 − A = C_cont / C_base` for the primary contrast of the persistent learner with maintenance against the empty-state learner. A ratio above 1 means the persistent learner is more expensive. Seeds and engine flags change between gates, so these are the official figure from each pre-registered run, not one continuous experiment.

| Gate | What was tested | Comp. L1 ratio | Unrel. L3 ratio | Official decision |
|------|-----------------|----------------|-----------------|-------------------|
| [G51](https://github.com/jacksonjp0311-gif/PacketLM/blob/g44-canonical-engine/docs/G51.md) | Qualified capabilities feed later acquisition | **3.87×** (A = −2.872) | **6.08×** (A = −5.080) | No L1 claim. Utility problem stated. |
| [G52](https://github.com/jacksonjp0311-gif/PacketLM/blob/g44-canonical-engine/docs/G52.md) | Soundness fixes; G50-A replication | — | — | 9/11 thresholds; FC2 and D1 fail. Not an amortization measurement. |
| [G53](https://github.com/jacksonjp0311-gif/PacketLM/blob/g44-canonical-engine/docs/G53.md) | Exact `--bounded` library mechanism | **1.89×** (A = −0.885) | **6.06×** (A = −5.065) | M claimed on comp (53% cut vs unbounded C, identical replies). No L1 claim. |
| [G54](https://github.com/jacksonjp0311-gif/PacketLM/blob/g44-canonical-engine/docs/G54.md) | Exact `--lean` per-call bounds | **1.85×** (A = −0.845) | **4.31×** (A = −3.312) | M claimed on both curricula. No L1 claim. |
| [G55](https://github.com/jacksonjp0311-gif/PacketLM/blob/g44-canonical-engine/docs/G55.md) | Closed-world guard budget | — | — | Registered run failed (timeout). No registered result. Seeds not rerun. |
| [G56](https://github.com/jacksonjp0311-gif/PacketLM/blob/g44-canonical-engine/docs/G56.md) | Long-lived `serve` protocol, charged equally | **2.13×** (A = −1.126) | **18.0×** (A = −16.99) | Ms claimed (the protocol is cheaper for every arm). The gap to empty-state widened because the reference also lost process overhead. No L1s claim. |
| [G57](https://github.com/jacksonjp0311-gif/PacketLM/blob/g44-canonical-engine/docs/G57.md) | `--indexed` state-proportional cost | **1.80×** (A = −0.803) | **6.87×** (A = −5.867) | Mi claimed. Rule F (flat in unrelated state) not claimed. No L1i claim. |
| [G57b](https://github.com/jacksonjp0311-gif/PacketLM/blob/g44-canonical-engine/docs/G57b.md) | `--incremental` work on unrelated state | **1.68×** (A = −0.677) | **3.21×** (A = −2.213) | Material yes (at 16k unrelated facts, mean task CPU 205.6 → 8.6 ms vs G57). Rule F not claimed. No L1j claim. |
| [G58](https://github.com/jacksonjp0311-gif/PacketLM/blob/g44-canonical-engine/docs/G58.md) | Exact `--routed` capability routing | **1.744×** (A = −0.744) | **2.898×** (A = −1.898) | Library-scaling stop rule passed; not flat. No L1r claim. |

The G58 ratios 1.744× and 2.898× are `1 − A` from the published A values (the G58 write-up reports A, not the × form).

**G58 library scaling** (seeds 261–267; mean task CPU): as the library grew from 64 to 1,024 capabilities, the routed engine's growth ratio was **R64_1024 = 1.99** [1.55, 2.31], against **14.74** [13.01, 15.89] for the G57b baseline (commit `8994490`). At 1,024 capabilities, mean task CPU fell from **136.2 ms to 6.30 ms** (21.6×). The stricter flatness target (interval upper bound ≤ 1.25) was not met. An independent verification on [`verify-33565b0`](https://github.com/jacksonjp0311-gif/PacketLM/tree/verify-33565b0) reproduced the registered result and noted that a duplicate integrity check, if charged in the amortized form, would put that secondary ratio above the half-threshold. The official stop rule was registered on task CPU and is unchanged.

### Where to read more

- Milestone write-ups and receipts: [`docs/`](https://github.com/jacksonjp0311-gif/PacketLM/tree/g44-canonical-engine/docs) on `g44-canonical-engine` (`docs/G*.md`, `docs/evidence/`)
- Independent checks: `verify-*` branches
- Invariant analysis and emergence log: [`docs/invariants`](https://github.com/jacksonjp0311-gif/PacketLM/tree/invariants-analysis/docs/invariants) on `invariants-analysis` (the emergence log is also on `g44-canonical-engine`)

On the research branch, `python -m packetlm.suite` runs the module suite in fresh processes. The long-lived engine is `python -m packetlm.serve`. Details are in [`docs/G44.md`](https://github.com/jacksonjp0311-gif/PacketLM/blob/g44-canonical-engine/docs/G44.md) and later milestone docs.

```bash
git clone -b g44-canonical-engine https://github.com/jacksonjp0311-gif/PacketLM
cd PacketLM
python -m packetlm.suite
```

## The field demo on this branch (`main`)

`main` is an earlier packet-field prototype. Most systems are a single brain: you ask, the whole thing runs, you get an answer. This demo is a set of small packets. Each packet holds one piece of knowledge and its own weights. A query wakes only the packets that match. The rest stay closed.

### What it does

1. A query becomes a set of content words.
2. Overlap picks the packet. Only that packet activates.
3. If nothing matches, a new packet is grown and seeded with the query.
4. A repeat holds what the packet already has.
5. A related query returns the tokens it did not say. That is retrieval.
6. One query can open more than one packet. That is composition.
7. If the answer lives in a second packet, the field returns it. That is inference.
8. A successful inference is written into a new packet, so the field remembers what it composed.
9. A hit strengthens a packet. A miss weakens it. Unused packets decay. The field scales so one packet cannot dominate.

### What happened

The field was given two facts in two packets: Lily found a needle, and a needle can sew. Asked what Lily can do with a needle, it opened both and returned sew. The answer was not in the question. It came from the other packet. The inference was then stored as its own packet.

That is receipted. It is not a mind. It is a field that selects, holds, composes, and keeps what it composed.

### Claim

PacketLM is a packet-routed field focused on language, retrieval, and composition. It is not AGI. It is not conscious. Every keep is gated. Every run leaves a receipt.

### Run

The field trains and routes on a public GitHub runner. Pure Python, no external dependencies.

```bash
git clone https://github.com/jacksonjp0311-gif/PacketLM
cd PacketLM
python -m packetlm.mind
```

Receipts land in `artifacts/`. Packets and memory persist in `data/`.

---

Local-first. Evidence-gated. The center is the field.
