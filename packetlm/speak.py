"""Language on the route, held to the fact.

The walk picks the packet.
The packet generates.
If the generation misses the surplus, the surplus is spoken.
The route decides. The fact is what is said. Not a general mind.
"""

from __future__ import annotations
import json
import random
from pathlib import Path
from .tiny import tokenize, build_vocab, ids
from .train import load_corpus, window_stories
from .context import load_store, save_store, bump, activate, write_back, train_on_query
from .geometry import ensure, walk

def speak(store, name, prompt, vocab, inv, surplus) -> tuple[list[str], bool]:
    model = activate(store, name)
    preferred = " ".join(store["packets"][name].get("preferred") or [])
    for _ in range(3):
        train_on_query(model, preferred or prompt, vocab, steps=24)
    gen = [inv.get(i, "<unk>") for i in model.generate(ids(tokenize(prompt), vocab) or [1], steps=6)]
    write_back(store, name, model)
    if any(t in gen for t in surplus):
        return gen, False
    return surplus[:6], True

def run() -> dict:
    random.seed(25)
    raw = load_corpus()
    windows = window_stories(raw)
    vocab = build_vocab(windows)
    store = load_store(len(vocab), ["language"])
    facts = [
        ("lily", ["lily", "found", "needle"], "lily found a needle"),
        ("needle", ["needle", "sew", "cloth"], "a needle can sew cloth"),
        ("infer-sew", ["lily", "sew"], "lily can sew"),
        ("dress", ["sew", "dress"], "sew makes a dress"),
        ("river", ["river", "cold", "stones"], "the river is cold and has stones"),
        ("dusk", ["dusk", "dark", "night"], "dusk is dark before night"),
        ("traveler", ["traveler", "shelter", "night"], "a traveler needed shelter before night"),
    ]
    for name, keys, text in facts:
        ensure(store, name, keys, tokenize(text))
    inv = {i: t for t, i in vocab.items()}
    questions = [
        ("what can lily make", "dress"),
        ("what can lily do with a needle", "sew"),
        ("what is in the river", "stones"),
        ("what is dusk", "dark"),
        ("what did the traveler need", "shelter"),
        ("what did lily find", "needle"),
    ]
    results = []
    for q, expected in questions:
        path = walk(q, store)
        if not path:
            results.append({"q": q, "hit": False})
            continue
        name = path[0]["packet"]
        surplus = path[0]["surplus"]
        spoken, held = speak(store, name, q, vocab, inv, surplus)
        hit = expected in spoken or expected in surplus
        bump(store, name, 0.1 if hit else -0.05)
        results.append({
            "q": q,
            "packet": name,
            "surplus": surplus,
            "spoke": spoken,
            "held": held,
            "hit": hit,
        })
    save_store(store)
    receipt = {
        "questions": len(questions),
        "hits": sum(1 for r in results if r.get("hit")),
        "held": sum(1 for r in results if r.get("held")),
        "results": results,
        "claim": "packet speaks surplus when generation misses; not a general mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/speak_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
