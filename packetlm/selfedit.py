"""Population self-edit.

Makes 4 mutated copies of the tiny model, scores each on holdout
continuation, and keeps the best only if it beats the parent.
Receipt records the population and the keep/discard.
"""

from __future__ import annotations
import json
import random
from pathlib import Path
from .tiny import TinyLM, build_vocab, tokenize, ids, holdout_score
from .train import load_corpus, window_stories

POP = 4
SCALE = 0.02

def clone_weights(model: TinyLM) -> dict:
    return {
        "E": [row[:] for row in model.E],
        "Wo": [row[:] for row in model.Wo],
    }

def restore(model: TinyLM, snap: dict) -> None:
    model.E = [row[:] for row in snap["E"]]
    model.Wo = [row[:] for row in snap["Wo"]]

def mutate(model: TinyLM, scale: float = SCALE) -> None:
    if not model.E:
        return
    i = random.randrange(len(model.E))
    model.E[i] = [v + (random.random() - 0.5) * scale for v in model.E[i]]

def run() -> dict:
    random.seed(2)
    raw = load_corpus()
    windows = window_stories(raw)
    vocab = build_vocab(windows)
    inv = {i: t for t, i in vocab.items()}
    parent = TinyLM(len(vocab))
    pairs = []
    for w in windows:
        toks = tokenize(w)
        for i in range(1, len(toks)):
            pairs.append((ids(toks[max(0, i - 6):i], vocab), vocab.get(toks[i], 1)))
    for _ in range(40):
        if pairs:
            ctx, tgt = random.choice(pairs)
            parent.step(ctx, tgt)
    cut = max(1, len(windows) // 5)
    holdout = windows[-cut:]
    parent_score = holdout_score(parent, holdout, vocab, inv)
    parent_snap = clone_weights(parent)
    scores = []
    best_score = parent_score
    best_snap = parent_snap
    for _ in range(POP):
        child = TinyLM(len(vocab))
        restore(child, parent_snap)
        mutate(child)
        s = holdout_score(child, holdout, vocab, inv)
        scores.append(round(s, 3))
        if s > best_score:
            best_score = s
            best_snap = clone_weights(child)
    kept = best_score > parent_score
    if kept:
        restore(parent, best_snap)
    receipt = {
        "population": POP,
        "parent": round(parent_score, 3),
        "children": scores,
        "best": round(best_score, 3),
        "kept": kept,
        "claim": "population self-edit; kept only if best child beat parent on holdout; still tiny, not intelligent"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/selfedit_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
