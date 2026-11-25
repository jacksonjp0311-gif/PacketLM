"""Language-phase training stub.

Focus: TinyStories-scale next-token on packet overlap.
Produces a simple loss curve artifact for the runner.
"""

from __future__ import annotations
import json
import random
from pathlib import Path
from .packets import hash_to_bits, Packet
from .router import Router

def toy_corpus(n: int = 32) -> list[str]:
    """Tiny synthetic stories for the first language loop."""
    templates = [
        "the {a} {v} the {b}",
        "a {a} and a {b} {v} together",
        "once there was a {a} who {v} a {b}",
    ]
    nouns = ["cat", "dog", "bird", "child", "tree"]
    verbs = ["saw", "chased", "found", "helped", "watched"]
    stories = []
    for _ in range(n):
        t = random.choice(templates)
        stories.append(t.format(
            a=random.choice(nouns),
            b=random.choice(nouns),
            v=random.choice(verbs)
        ))
    return stories

def train_step(router: Router, text: str) -> float:
    """Stub loss: 1 - normalized best overlap. Lower is better."""
    q = hash_to_bits(text)
    scored = router.select(q, k=1)
    if not scored:
        return 1.0
    _, score = scored[0]
    # normalize roughly to [0,1]
    return max(0.0, 1.0 - score / 100.0)

def run(seed: int = 0, steps: int = 50) -> dict:
    random.seed(seed)
    packets = [hash_to_bits(s, seed=seed) for s in toy_corpus(16)]
    router = Router(packets)
    losses = []
    for i in range(steps):
        text = random.choice(toy_corpus(8))
        loss = train_step(router, text)
        losses.append(loss)
    receipt = {
        "seed": seed,
        "steps": steps,
        "final_loss": losses[-1] if losses else None,
        "mean_loss": sum(losses) / len(losses) if losses else None,
        "phase": "language",
        "claim": "toy corpus only; not a real language model yet"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
