"""Population self-edit with adaptive step size.

Several generations. Each generation makes 4 mutated copies.
Keeps the best only if it beats the parent.
Shrinks the mutation size when nothing is kept. Grows it slightly when something is.
"""

from __future__ import annotations
import json
import random
from pathlib import Path
from .tiny import TinyLM, build_vocab, tokenize, ids, holdout_score
from .train import load_corpus, window_stories

POP = 4
GENS = 3

def clone_weights(model: TinyLM) -> dict:
    return {
        "E": [row[:] for row in model.E],
        "Wo": [row[:] for row in model.Wo],
    }

def restore(model: TinyLM, snap: dict) -> None:
    model.E = [row[:] for row in snap["E"]]
    model.Wo = [row[:] for row in snap["Wo"]]

def mutate(model: TinyLM, scale: float) -> None:
    if not model.E:
        return
    i = random.randrange(len(model.E))
    model.E[i] = [v + (random.random() - 0.5) * scale for v in model.E[i]]

def run() -> dict:
    random.seed(3)
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
    scale = 0.02
    history = []
    score = holdout_score(parent, holdout, vocab, inv)
    for g in range(GENS):
        snap = clone_weights(parent)
        best_score = score
        best_snap = snap
        child_scores = []
        for _ in range(POP):
            child = TinyLM(len(vocab))
            restore(child, snap)
            mutate(child, scale)
            s = holdout_score(child, holdout, vocab, inv)
            child_scores.append(round(s, 3))
            if s > best_score:
                best_score = s
                best_snap = clone_weights(child)
        kept = best_score > score
        if kept:
            restore(parent, best_snap)
            score = best_score
            scale = min(scale * 1.2, 0.1)
        else:
            scale = max(scale * 0.7, 0.002)
        history.append({
            "gen": g,
            "parent": round(score if kept else history[-1]["parent"] if history else score, 3),
            "children": child_scores,
            "kept": kept,
            "scale": round(scale, 4),
        })
    receipt = {
        "population": POP,
        "generations": GENS,
        "final_score": round(score, 3),
        "final_scale": round(scale, 4),
        "history": history,
        "claim": "adaptive population self-edit; mutation shrinks when nothing is kept; still tiny, not intelligent"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/selfedit_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
