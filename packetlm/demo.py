"""Minimal public demo.

Prints a receipted continuation on a communication-style prompt.
Continuation is selected by the residual path union, not a post-hoc match.
Claim boundary explicit.
"""

from __future__ import annotations
import json
from pathlib import Path
from .packets import hash_to_bits
from .router import Router
from .train import load_corpus, window_stories

def demo(seed: int = 42) -> dict:
    raw = load_corpus()
    corpus = window_stories(raw)
    packets = [hash_to_bits(s, seed=seed) for s in corpus]
    router = Router(packets)

    prompt = "Lily thanked her mom. How did they both feel?"
    q = hash_to_bits(prompt)
    path = router.residual_hop(q, depth=3)
    union = router.path_union(q, depth=3)
    single = router.select(q, k=1)

    # continuation chosen by residual path union overlap
    best = None
    best_ov = -1
    if union:
        for w in corpus:
            ov = union.overlap(hash_to_bits(w))
            if ov > best_ov:
                best_ov = ov
                best = w

    receipt = {
        "prompt": prompt,
        "continuation": best[:120] if best else None,
        "overlap": best_ov,
        "hop_count": len(path),
        "path_produced_continuation": union is not None and best is not None,
        "single_score": single[0][1] if single else 0,
        "seed": seed,
        "claim": "continuation selected by residual path union on TinyStories slice; not a real language model"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/demo_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    demo()
