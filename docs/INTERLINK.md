# PacketLM ↔ NOMAD Interlink

Symbiotic interconnection following [NOMAD docs/SYMBIOTIC.md](https://github.com/jacksonjp0311-gif/NOMAD/blob/main/docs/SYMBIOTIC.md) and [docs/INTERLINK.md](https://github.com/jacksonjp0311-gif/NOMAD/blob/main/docs/INTERLINK.md).

## Handshake

1. **Presence mark**  
   PacketLM calls `python -m nomad.interlink inspect` (or equivalent) to mark presence. Quorum of recent marks required for offers.

2. **Geometry handover**  
   On interconnect, NOMAD runner snaps and hands over current field geometry (packet sets, counts, domain evidence). PacketLM treats this as an external prior or routing bias. No write to NOMAD field.

3. **Certified packet offer**  
   PacketLM offers sparse binary packets (same Bitwork identity: overlap = |q| - H(q,p)) that have survived its sealed eval gate. Offer includes receipt. NOMAD accepts only with receipt; both sides log the exchange.

4. **Receipt schema** (minimal)  
   ```json
   {
     "packet_sha256": "...",
     "source": "PacketLM",
     "eval_gate": "sealed_holdout_pass",
     "timestamp": "ISO8601",
     "witness_supported": true
   }
   ```

## Claim boundaries

- PacketLM never writes the NOMAD field.
- Body remains the sole authority for field updates.
- Mutualism only if both sides gain a certified packet.
- All exchanges are receipted and inspectable.

## Next

Implement the presence/offer scripts and a workflow that can be triggered on repository_dispatch or schedule for continuous presence.
