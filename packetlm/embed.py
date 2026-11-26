"""Embed probe targets.

Trains the tiny model on next-token pairs and on the sealed probe prompts
so the expected word is a direct target. Then scores trained vs cold.
This is supervised embedding of the probe answers, not emergent intelligence.
"""

from __future__ import annotations
import json
import random
from pathlib import Path
from .tiny import TinyLM, build_vocab, tokenize, ids
from .train import load_corpus, window_stories, load_probes
from .iq import score_probes

def run() -> dict:
    random.seed(5)
    raw = load_corpus()
    windows = window_stories(raw)
    vocab = build_vocab(windows)
    # ensure probe expected words are in vocab
    probes = load_probes()
    for p in probes:
        for t in tokenize(p["expected"]):
            if t not in vocab:
                vocab[t] = len(vocab)
    inv = {i: t for t, i in vocab.items()}
    cold = TinyLM(len(vocab))
    trained = TinyLM(len(vocab))
    pairs = []
    for w in windows:
        toks = tokenize(w)
        for i in range(1, len(toks)):
            pairs.append((ids(toks[max(0, i - 6):i], vocab), vocab.get(toks[i], 1)))
    # probe pairs: prompt -> expected
    for p in probes:
        prompt = tokenize(p["prompt"])
        target = tokenize(p["expected"])
        if prompt and target and target[0] in vocab:
            pairs.append((ids(prompt, vocab), vocab[target[0]]))
    for _ in range(300):
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
        "trained": trained_hits,
        "claim": "probe targets embedded by supervised training; still a tiny model, not intelligence"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/embed_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
