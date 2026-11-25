# Sealed Probes

Pre-registered holdouts for understanding and reasoning.
Cold-start must fail; field must succeed for a certified delta.

## Format

```json
{
  "id": "understand-001",
  "phase": "understanding",
  "prompt": "what did the cat chase",
  "expected": "the dog",
  "seed": 42,
  "cold_must_fail": true
}
```

## Rules

- Written before the training run that claims to solve them.
- Not used for packet construction.
- Twin measurement: cold (empty store) vs field (trained packets).
- Receipt records both arms and the gate result.

## First set (placeholder)

- Language: exact continuation of a toy story sentence.
- Understanding: answer that requires combining two packets.
- Reasoning: two-hop chain that single-hop misses.

Real sealed sets replace these once the language phase produces stable packets.
