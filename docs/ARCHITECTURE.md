# PacketLM Architecture

## Bitwork identity (inherited)

For a query vector q and prototype p (both sparse binary):

```
overlap = |q ∧ p|
score   = 2 * overlap - |p|   ≡   |q| - H(q, p)
```

Retrieval is exact nearest-neighbor in Hamming space, offset by domain evidence.

## Layers

### 1. Encoder
Tokens → sparse 4096-bit pattern. Feature hashing (lexical + structural). Fixed for a given seed.

### 2. Packet store
- Weight packets: bit set + count
- Storage packets: same shape, addressable for memory
- Splittable / mergeable on consolidation (future)

### 3. Temporal router
Given residual state R, select k packets whose overlap with the projected residual is highest. Conditioning must not break the Hamming identity for the selected packets.

### 4. Residual loop
```
winner = argmax score
residual_bits = residual_bits AND NOT winner_bits
re-query
```
Bounded depth. Each hop logged.

### 5. Memory write
Proposal only. Trigger: residual energy above threshold or explicit surprise signal. Commit only after sealed eval gate. Receipt required.

### 6. Readout
Integer scores → logits (or hard argmax). No floating-point in the hot path for v0.

## Open questions

- How does the router condition on residual state while remaining Hamming-exact?
- Weight sharing across loop iterations vs. per-iteration packets?
- Exact form of the surprise signal for memory writes.

These are design decisions, not implementation details.
