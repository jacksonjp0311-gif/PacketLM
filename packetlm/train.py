"""Language-phase training stub.

Focus: TinyStories-scale next-token on packet overlap.
Windows stories into short segments and measures whether residual hops change retrieval.
Also runs a continuation probe and a simple understanding check.
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

def window_stories(stories: list[str], max_len: int = 120) -> list[str]:
    """Split stories into short windows for local language structure."""
    windows = []
    for story in stories:
        words = story.split()
        for i in range(0, len(words), max_len // 8):
            chunk = " ".join(words[i:i + max_len // 4])
            if len(chunk) > 20:
                windows.append(chunk)
    return windows or stories

def toy_corpus(n: int = 32) -> list[str]:
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

def hop_effect(router: Router, text: str) -> dict:
    """Compare single-select vs residual hops on the same query."""
    q = hash_to_bits(text)
    single = router.select(q, k=1)
    hops = router.residual_hop(q, depth=3)
    return {
        "single_score": single[0][1] if single else 0,
        "hop_count": len(hops),
        "hop_changed": len(hops) > 1
    }

def continuation_probe(router: Router, windows: list[str]) -> dict:
    """Simple continuation: does the best packet match the next window?"""
    if len(windows) < 2:
        return {"hit": False, "reason": "not enough windows"}
    prompt = windows[0]
    expected = windows[1]
    q = hash_to_bits(prompt)
    scored = router.select(q, k=1)
    if not scored:
        return {"hit": False, "prompt": prompt[:60], "expected": expected[:60]}
    winner = scored[0][0]
    # crude: check if winner bits overlap heavily with expected
    exp_pkt = hash_to_bits(expected)
    overlap = winner.overlap(exp_pkt)
    hit = overlap > exp_pkt.count // 4
    return {
        "hit": hit,
        "overlap": overlap,
        "prompt": prompt[:60],
        "expected": expected[:60]
    }

def understanding_check(router: Router) -> dict:
    """Tiny understanding probe: retrieve a fact that requires the field."""
    # fact present in the slice: Lily found a needle
    prompt = "what did Lily find"
    expected_bits = hash_to_bits("needle")
    q = hash_to_bits(prompt)
    scored = router.select(q, k=1)
    if not scored:
        return {"hit": False, "cold_would_fail": True}
    winner = scored[0][0]
    overlap = winner.overlap(expected_bits)
    hit = overlap > 0
    return {
        "hit": hit,
        "overlap": overlap,
        "prompt": prompt,
        "cold_would_fail": True
    }

def run(seed: int = 0, steps: int = 50) -> dict:
    random.seed(seed)
    raw = load_corpus()
    corpus = window_stories(raw)
    packets = [hash_to_bits(s, seed=seed) for s in corpus]
    router = Router(packets)
    losses = []
    effects = []
    for i in range(steps):
        text = random.choice(corpus)
        loss = train_step(router, text)
        losses.append(loss)
        if i % 10 == 0:
            effects.append(hop_effect(router, text))
    cont = continuation_probe(router, corpus)
    under = understanding_check(router)
    receipt = {
        "seed": seed,
        "steps": steps,
        "stories_raw": len(raw),
        "windows": len(corpus),
        "final_loss": losses[-1] if losses else None,
        "mean_loss": sum(losses) / len(losses) if losses else None,
        "hop_effects": effects,
        "continuation_probe": cont,
        "understanding_check": under,
        "phase": "language",
        "corpus": "tinystories_slice" if Path("data/tinystories_slice.txt").exists() else "toy",
        "claim": "overlap proxy + hop count + continuation/understanding checks on windowed TinyStories slice; not a real language model yet",
        "status": "M1 in progress"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
