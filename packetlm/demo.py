"""Minimal public demo.

Prints a receipted continuation on a communication-style prompt.
Claim boundary explicit.
"""

from __future__ import annotations
import json
from pathlib import Path
from .packets import hash_to_bits
from .router import Router
from .train import load_corpus, window_stories, load_probes

def demo(seed: int = 42) -> dict:
    raw = load_corpus()
    corpus = window_stories(raw)
    packets = [hash_to_bits(s, seed=seed) for s in corpus]
    router = Router(packets)

    # communication-style prompt
    prompt = "Lily thanked her mom. How did they both feel?"
    q = hash_to_bits(prompt)
    union = router.path_union(q, depth=3)
    single = router.select(q, k=1)

    # crude continuation: best overlapping window from corpus
    best = None
    best_ov = -1
    for w in corpus:
        ov = (union or hash_to_bits("")).overlap(hash_to_bits(w)) if union else 0
        if ov > best_ov:
            best_ov = ov
            best = w

    receipt = {
        "prompt": prompt,
        "continuation": best[:120] if best else None,
        "overlap": best_ov,
        "hop_count": len(router.residual_hop(q)),
        "single_score": single[0][1] if single else 0,
        "seed": seed,
        "claim": "toy continuation via packet overlap on TinyStories slice; not a real language model"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/demo_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    demo()
