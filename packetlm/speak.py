"""Generation bar.

The packet is trained only on its own fact.
A hit is the model saying the expected token.
Retrieval is reported separately and does not count.
Not a general mind.
"""

from __future__ import annotations
import json
import random
from pathlib import Path
from .tiny import tokenize, build_vocab, ids, TinyLM
from .train import load_corpus, window_stories
from .context import load_store, save_store, blank_packet
from .geometry import ensure, walk

FACTS = [
    ("lily", ["lily", "found", "needle"], "lily found a needle"),
    ("needle", ["needle", "sew", "cloth"], "a needle can sew cloth"),
    ("dress", ["sew", "dress"], "sew makes a dress"),
    ("river", ["river", "cold", "stones"], "the river is cold and has stones"),
    ("dusk", ["dusk", "dark", "night"], "dusk is dark before night"),
]

QUESTIONS = [
    ("lily found", "needle"),
    ("needle can", "sew"),
    ("sew makes", "dress"),
    ("river is", "cold"),
    ("dusk is", "dark"),
]

def train_fact(model: TinyLM, fact: str, vocab: dict) -> None:
    toks = tokenize(fact)
    ids_ = ids(toks, vocab)
    for _ in range(40):
        for i in range(1, len(ids_)):
            model.step(ids_[:i], ids_[i], lr=0.2)

def run() -> dict:
    random.seed(30)
    raw = load_corpus()
    windows = window_stories(raw)
    vocab = build_vocab(windows)
    # make sure fact tokens are in vocab
    for _, _, text in FACTS:
        for t in tokenize(text):
            if t not in vocab:
                vocab[t] = len(vocab)
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
        spoken = []
        generated = False
        if name:
            model = TinyLM(len(vocab))
            fact = " ".join(store["packets"][name].get("preferred") or [])
            train_fact(model, fact, vocab)
            spoken = [inv.get(i, "<unk>") for i in model.generate(ids(tokenize(q), vocab) or [1], steps=4)]
            generated = expected in spoken
        rows.append({
            "q": q,
            "packet": name,
            "retrieved": retrieved,
            "generated": generated,
            "spoke": spoken,
        })
    receipt = {
        "retrieved": sum(1 for r in rows if r["retrieved"]),
        "generated": sum(1 for r in rows if r["generated"]),
        "of": len(QUESTIONS),
        "results": rows,
        "claim": "generation hit only if the model says the token; not a general mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/speak_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
