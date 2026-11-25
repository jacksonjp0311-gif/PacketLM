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

def load_corpus() -> list[str]:
    """Prefer real TinyStories slice; fall back to toy."""
    slice_path = Path("data/tinystories_slice.txt")
    if slice_path.exists():
        text = slice_path.read_text()
        stories = [s.strip() for s in text.split("\n\n") if s.strip()]
        if stories:
            return stories
    return toy_corpus()

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
    return max(0.0, 1.0 - score / 100.0)

def run(seed: int = 0, steps: int = 50) -> dict:
    random.seed(seed)
    corpus = load_corpus()
    packets = [hash_to_bits(s, seed=seed) for s in corpus]
    router = Router(packets)
    losses = []
    for i in range(steps):
        text = random.choice(corpus)
        loss = train_step(router, text)
        losses.append(loss)
    receipt = {
        "seed": seed,
        "steps": steps,
        "stories": len(corpus),
        "final_loss": losses[-1] if losses else None,
        "mean_loss": sum(losses) / len(losses) if losses else None,
        "phase": "language",
        "corpus": "tinystories_slice" if Path("data/tinystories_slice.txt").exists() else "toy",
        "claim": "overlap proxy on small slice; not a real language model yet"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
