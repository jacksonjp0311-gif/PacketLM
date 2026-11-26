"""Intelligence probe.

Scores a cold model and a trained model on sealed probes.
A hit is the expected word appearing in the generated continuation.
This is a test, not a claim of intelligence.
"""

from __future__ import annotations
import json
import random
from pathlib import Path
from .tiny import TinyLM, build_vocab, tokenize, ids
from .train import load_corpus, window_stories, load_probes

def score_probes(model, probes, vocab, inv) -> list[dict]:
    out = []
    for p in probes:
        prompt = tokenize(p["prompt"])
        gen_ids = model.generate(ids(prompt, vocab) or [1], steps=6)
        gen = [inv.get(i, "<unk>") for i in gen_ids]
        expected = p["expected"].lower()
        hit = expected in gen or expected in " ".join(gen)
        out.append({
            "id": p["id"],
            "phase": p["phase"],
            "expected": expected,
            "generated": gen,
            "hit": hit,
        })
    return out

def run() -> dict:
    random.seed(4)
    raw = load_corpus()
    windows = window_stories(raw)
    vocab = build_vocab(windows)
    inv = {i: t for t, i in vocab.items()}
    probes = load_probes()
    # novel probe not in the slice
    probes = probes + [{
        "id": "novel-001",
        "phase": "novel",
        "prompt": "A traveler needed shelter before night. What should they do first?",
        "expected": "shelter",
    }]
    cold = TinyLM(len(vocab))
    trained = TinyLM(len(vocab))
    pairs = []
    for w in windows:
        toks = tokenize(w)
        for i in range(1, len(toks)):
            pairs.append((ids(toks[max(0, i - 6):i], vocab), vocab.get(toks[i], 1)))
    for _ in range(200):
        if pairs:
            ctx, tgt = random.choice(pairs)
            trained.step(ctx, tgt)
    cold_hits = score_probes(cold, probes, vocab, inv)
    trained_hits = score_probes(trained, probes, vocab, inv)
    cold_n = sum(1 for h in cold_hits if h["hit"])
    trained_n = sum(1 for h in trained_hits if h["hit"])
    receipt = {
        "probes": len(probes),
        "cold_hits": cold_n,
        "trained_hits": trained_n,
        "trained_better": trained_n > cold_n,
        "cold": cold_hits,
        "trained": trained_hits,
        "claim": "sealed probe: trained vs cold; a hit is the expected word in the continuation; not a claim of intelligence"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/iq_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
