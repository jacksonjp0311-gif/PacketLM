"""Language on the route.

The walk picks the packet.
That packet's weights generate the next tokens.
The route decides. The packet speaks.
Not a general mind.
"""

from __future__ import annotations
import json
import random
from pathlib import Path
from .tiny import TinyLM, tokenize, build_vocab, ids
from .train import load_corpus, window_stories
from .nodes import tokens
from .context import load_store, save_store, bump, blank_packet, activate, write_back, train_on_query
from .geometry import content, ensure, walk

STOP = {"the", "a", "an", "in", "on", "at", "of", "to", "and", "before", "did", "what", "can", "with", "make", "makes"}

def speak(store, name, prompt, vocab, inv) -> list[str]:
    model = activate(store, name)
    train_on_query(model, prompt, vocab, steps=20)
    preferred = " ".join(store["packets"][name].get("preferred") or [])
    if preferred:
        train_on_query(model, preferred, vocab, steps=12)
    gen = [inv.get(i, "<unk>") for i in model.generate(ids(tokenize(prompt), vocab) or [1], steps=6)]
    write_back(store, name, model)
    return gen

def run() -> dict:
    random.seed(24)
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
    ]
    for name, keys, text in facts:
        ensure(store, name, keys, tokenize(text))
    inv = {i: t for t, i in vocab.items()}
    questions = [
        ("what can lily make", "dress"),
        ("what can lily do with a needle", "sew"),
        ("what is in the river", "stones"),
        ("what is dusk", "dark"),
    ]
    results = []
    for q, expected in questions:
        path = walk(q, store)
        if not path:
            results.append({"q": q, "hit": False, "spoke": []})
            continue
        name = path[0]["packet"]
        spoken = speak(store, name, q, vocab, inv)
        flat = [t for step in path for t in step["surplus"]] + spoken
        hit = expected in flat
        bump(store, name, 0.1 if hit else -0.05)
        results.append({
            "q": q,
            "packet": name,
            "surplus": path[0]["surplus"],
            "spoke": spoken,
            "hit": hit,
        })
    save_store(store)
    receipt = {
        "questions": len(questions),
        "hits": sum(1 for r in results if r["hit"]),
        "results": results,
        "claim": "route picks the packet; packet speaks; not a general mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/speak_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
