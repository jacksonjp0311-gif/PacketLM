"""Minimal public demo.

Prints a receipted two-turn continuation on a communication-style prompt.
Each turn is selected by the residual path union.
Measures whether the second turn stays consistent with the first.
Claim boundary explicit.
"""

from __future__ import annotations
import json
from pathlib import Path
from .packets import hash_to_bits
from .router import Router
from .train import load_corpus, window_stories

def best_window(union, corpus):
    if not union:
        return None, -1
    best = None
    best_ov = -1
    for w in corpus:
        ov = union.overlap(hash_to_bits(w))
        if ov > best_ov:
            best_ov = ov
            best = w
    return best, best_ov

def demo(seed: int = 42) -> dict:
    raw = load_corpus()
    corpus = window_stories(raw)
    packets = [hash_to_bits(s, seed=seed) for s in corpus]
    router = Router(packets)

    # turn 1
    prompt1 = "Lily thanked her mom. How did they both feel?"
    q1 = hash_to_bits(prompt1)
    path1 = router.residual_hop(q1, depth=3)
    union1 = router.path_union(q1, depth=3)
    cont1, ov1 = best_window(union1, corpus)

    # turn 2 (conditioned on first continuation)
    prompt2 = (cont1 or prompt1) + " What did they do next?"
    q2 = hash_to_bits(prompt2)
    path2 = router.residual_hop(q2, depth=3)
    union2 = router.path_union(q2, depth=3)
    cont2, ov2 = best_window(union2, corpus)

    # consistency: how much of turn 1's continuation is still covered by turn 2's path
    consistency = 0
    if cont1 and union2:
        consistency = union2.overlap(hash_to_bits(cont1))

    receipt = {
        "turns": [
            {
                "prompt": prompt1,
                "continuation": cont1[:120] if cont1 else None,
                "overlap": ov1,
                "hop_count": len(path1),
                "path_produced": union1 is not None and cont1 is not None
            },
            {
                "prompt": prompt2[:80],
                "continuation": cont2[:120] if cont2 else None,
                "overlap": ov2,
                "hop_count": len(path2),
                "path_produced": union2 is not None and cont2 is not None
            }
        ],
        "multi_step": cont1 is not None and cont2 is not None,
        "consistency_overlap": consistency,
        "consistent": consistency > 0,
        "seed": seed,
        "claim": "two-turn continuation selected by residual path union; consistency measured by overlap of second path with first continuation; not a real language model"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/demo_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    demo()
