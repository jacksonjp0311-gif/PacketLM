"""Population self-edit that selects on probe hits.

Loads persisted weights if present.
Each generation mutates copies and scores them on sealed probes.
Keeps the best only if probe hits rise.
Saves the kept model so the next run continues.
"""

from __future__ import annotations
import json
import random
from pathlib import Path
from .tiny import TinyLM, build_vocab, tokenize, ids, DIM
from .train import load_corpus, window_stories, load_probes
from .persist import load_into, save_from
from .iq import score_probes

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

def probe_hits(model, probes, vocab, inv) -> int:
    return sum(1 for h in score_probes(model, probes, vocab, inv) if h["hit"])

def run() -> dict:
    random.seed(7)
    raw = load_corpus()
    windows = window_stories(raw)
    vocab = build_vocab(windows)
    probes = load_probes()
    for p in probes:
        for t in tokenize(p["expected"]):
            if t not in vocab:
                vocab[t] = len(vocab)
    inv = {i: t for t, i in vocab.items()}
    parent = TinyLM(len(vocab))
    loaded = load_into(parent, DIM)
    pairs = []
    for w in windows:
        toks = tokenize(w)
        for i in range(1, len(toks)):
            pairs.append((ids(toks[max(0, i - 12):i], vocab), vocab.get(toks[i], 1)))
    for _ in range(60):
        if pairs:
            ctx, tgt = random.choice(pairs)
            parent.step(ctx, tgt)
    scale = 0.02
    history = []
    score = probe_hits(parent, probes, vocab, inv)
    for g in range(GENS):
        snap = clone_weights(parent)
        best_score = score
        best_snap = snap
        child_scores = []
        for _ in range(POP):
            child = TinyLM(len(vocab))
            restore(child, snap)
            mutate(child, scale)
            s = probe_hits(child, probes, vocab, inv)
            child_scores.append(s)
            if s > best_score:
                best_score = s
                best_snap = clone_weights(child)
        kept = best_score > score
        if kept:
            restore(parent, best_snap)
            score = best_score
            scale = min(scale * 1.2, 0.1)
            save_from(parent, DIM)
        else:
            scale = max(scale * 0.7, 0.002)
        history.append({
            "gen": g,
            "hits": score,
            "children": child_scores,
            "kept": kept,
            "scale": round(scale, 4),
        })
    receipt = {
        "loaded": loaded,
        "probes": len(probes),
        "final_hits": score,
        "history": history,
        "claim": "self-edit selects on probe hits and persists a keep; still tiny, not intelligent"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/selfedit_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
