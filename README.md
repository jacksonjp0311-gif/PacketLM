# PacketLM

![Field](docs/field.jpg)

A field of weight packets. Not one big model.

Most systems are a single brain. You ask, the whole thing runs, you get an answer. PacketLM is a set of small packets. Each packet holds one piece of knowledge and its own weights. A query wakes only the packets that match. The rest stay closed.

## What it does

1. A query becomes a set of content words.
2. Overlap picks the packet. Only that packet activates.
3. If nothing matches, a new packet is grown and seeded with the query.
4. A repeat holds what the packet already has.
5. A related query returns the tokens it did not say. That is retrieval.
6. One query can open more than one packet. That is composition.
7. If the answer lives in a second packet, the field returns it. That is inference.
8. A successful inference is written into a new packet, so the field remembers what it composed.
9. A hit strengthens a packet. A miss weakens it. Unused packets decay. The field scales so one packet cannot dominate.

## What happened

The field was given two facts in two packets: Lily found a needle, and a needle can sew. Asked what Lily can do with a needle, it opened both and returned sew. The answer was not in the question. It came from the other packet. The inference was then stored as its own packet.

That is receipted. It is not a mind. It is a field that selects, holds, composes, and keeps what it composed.

## Claim

PacketLM is a packet-routed field focused on language, retrieval, and composition. It is not AGI. It is not conscious. Every keep is gated. Every run leaves a receipt.

## Run

The field trains and routes on a public GitHub runner.

```bash
git clone https://github.com/jacksonjp0311-gif/PacketLM
cd PacketLM
python -m packetlm.mind
```

Receipts land in `artifacts/`. Packets and memory persist in `data/`.

---

Local-first. Evidence-gated. The center is the field.
