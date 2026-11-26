"""Held-out probe.

Trains on all sealed probes except one.
Scores the held-out probe on cold and trained.
A hit on the unseen probe is transfer. No hit is no transfer.
"""

from __future__ import annotations
import json
import random
from pathlib import Path
from .tiny import TinyLM, build_vocab, tokenize, ids
from .train import load_corpus, window_stories, load_probes
from .iq import score_probes

def run() -> dict:
    random.seed(6)
    raw = load_corpus()
    windows = window_stories(raw)
    vocab = build_vocab(windows)
    probes = load_probes()
    for p in probes:
        for t in tokenize(p["expected"]):
            if t not in vocab:
                vocab[t] = len(vocab)
    inv = {i: t for t, i in vocab.items()}
    hold = probes[-1]
    train_probes = probes[:-1]
    cold = TinyLM(len(vocab))
    trained = TinyLM(len(vocab))
    pairs = []
    for w in windows:
        toks = tokenize(w)
        for i in range(1, len(toks)):
            pairs.append((ids(toks[max(0, i - 6):i], vocab), vocab.get(toks[i], 1)))
    for p in train_probes:
        prompt = tokenize(p["prompt"])
        target = tokenize(p["expected"])
        if prompt and target and target[0] in vocab:
            pairs.append((ids(prompt, vocab), vocab[target[0]]))
    for _ in range(300):
        if pairs:
            ctx, tgt = random.choice(pairs)
            trained.step(ctx, tgt)
    cold_h = score_probes(cold, [hold], vocab, inv)[0]
    trained_h = score_probes(trained, [hold], vocab, inv)[0]
    receipt = {
        "held_out": hold["id"],
        "expected": hold["expected"],
        "cold_hit": cold_h["hit"],
        "trained_hit": trained_h["hit"],
        "trained_generated": trained_h["generated"],
        "transferred": trained_h["hit"] and not cold_h["hit"],
        "claim": "one probe held out of training; a hit is transfer, not intelligence"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/transfer_probe_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
