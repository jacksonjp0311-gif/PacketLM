"""Retrieval and generation are scored apart.

Retrieved means the expected token was in the surplus.
Generated means the model said it without the fallback.
A fallback is not a generation hit.
"""

from __future__ import annotations
import json
import random
from pathlib import Path
from .tiny import tokenize, build_vocab, ids
from .train import load_corpus, window_stories
from .context import load_store, save_store, bump, activate, write_back, train_on_query
from .geometry import ensure, walk

FACTS = [
    ("lily", ["lily", "found", "needle"], "lily found a needle"),
    ("needle", ["needle", "sew", "cloth"], "a needle can sew cloth"),
    ("dress", ["sew", "dress"], "sew makes a dress"),
    ("river", ["river", "cold", "stones"], "the river is cold and has stones"),
    ("dusk", ["dusk", "dark", "night"], "dusk is dark before night"),
    ("traveler", ["traveler", "shelter", "night"], "a traveler needed shelter before night"),
]

QUESTIONS = [
    ("what can lily make", "dress"),
    ("what can lily do with a needle", "sew"),
    ("what is in the river", "stones"),
    ("what is dusk", "dark"),
    ("what did the traveler need", "shelter"),
    ("what did lily find", "needle"),
]

def generate_only(store, name, prompt, vocab, inv) -> list[str]:
    model = activate(store, name)
    preferred = " ".join(store["packets"][name].get("preferred") or [])
    train_on_query(model, preferred or prompt, vocab, steps=8)
    gen = [inv.get(i, "<unk>") for i in model.generate(ids(tokenize(prompt), vocab) or [1], steps=4)]
    write_back(store, name, model)
    return gen

def run() -> dict:
    random.seed(29)
    raw = load_corpus()
    windows = window_stories(raw)
    vocab = build_vocab(windows)
    store = load_store(len(vocab), ["language"])
    for name, keys, text in FACTS:
        ensure(store, name, keys, tokenize(text))
    inv = {i: t for t, i in vocab.items()}
    rows = []
    for q, expected in QUESTIONS:
        path = walk(q, store)
        name = path[0]["packet"] if path else None
        surplus = path[0]["surplus"] if path else []
        retrieved = expected in surplus
        spoken = generate_only(store, name, q, vocab, inv) if name else []
        generated = expected in spoken
        if retrieved and name:
            bump(store, name, 0.1)
        rows.append({
            "q": q,
            "packet": name,
            "retrieved": retrieved,
            "generated": generated,
            "spoke": spoken,
        })
    save_store(store)
    receipt = {
        "retrieved": sum(1 for r in rows if r["retrieved"]),
        "generated": sum(1 for r in rows if r["generated"]),
        "of": len(QUESTIONS),
        "results": rows,
        "claim": "retrieval and generation scored apart; a fallback is not a generation hit"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/speak_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
