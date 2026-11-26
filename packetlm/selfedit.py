"""Self-edit loop.

Proposes a change to the tiny model, measures holdout continuation,
and keeps the change only if the score rises. Receipt records the decision.
"""

from __future__ import annotations
import json
import random
from pathlib import Path
from .tiny import TinyLM, build_vocab, tokenize, ids, holdout_score
from .train import load_corpus, window_stories

def clone_weights(model: TinyLM) -> dict:
    return {
        "E": [row[:] for row in model.E],
        "Wo": [row[:] for row in model.Wo],
    }

def restore(model: TinyLM, snap: dict) -> None:
    model.E = [row[:] for row in snap["E"]]
    model.Wo = [row[:] for row in snap["Wo"]]

def propose_nudge(model: TinyLM, scale: float = 0.02) -> None:
    # nudge a random embedding row
    if not model.E:
        return
    i = random.randrange(len(model.E))
    model.E[i] = [v + (random.random() - 0.5) * scale for v in model.E[i]]

def run() -> dict:
    random.seed(1)
    raw = load_corpus()
    windows = window_stories(raw)
    vocab = build_vocab(windows)
    inv = {i: t for t, i in vocab.items()}
    model = TinyLM(len(vocab))
    # brief warm-up
    pairs = []
    for w in windows:
        toks = tokenize(w)
        for i in range(1, len(toks)):
            pairs.append((ids(toks[max(0, i - 6):i], vocab), vocab.get(toks[i], 1)))
    for _ in range(40):
        if pairs:
            ctx, tgt = random.choice(pairs)
            model.step(ctx, tgt)
    cut = max(1, len(windows) // 5)
    holdout = windows[-cut:]
    before = holdout_score(model, holdout, vocab, inv)
    snap = clone_weights(model)
    propose_nudge(model)
    after = holdout_score(model, holdout, vocab, inv)
    kept = after > before
    if not kept:
        restore(model, snap)
    receipt = {
        "holdout_before": round(before, 3),
        "holdout_after": round(after, 3),
        "kept": kept,
        "claim": "self-edit kept only if holdout continuation rose; otherwise discarded; still tiny, not intelligent"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/selfedit_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
