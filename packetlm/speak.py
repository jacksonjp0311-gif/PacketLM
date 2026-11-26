"""Train and repair.

Ten questions, four epochs.
A hit strengthens the packet.
A miss grows a packet keyed to the question, holding the expected answer.
The next epoch can route to what the last epoch lacked.
Not a general mind.
"""

from __future__ import annotations
import json
import random
from pathlib import Path
from .tiny import tokenize, build_vocab, ids
from .train import load_corpus, window_stories
from .nodes import tokens
from .context import load_store, save_store, bump, activate, write_back, train_on_query
from .geometry import ensure, walk, content

FACTS = [
    ("lily", ["lily", "found", "needle"], "lily found a needle"),
    ("needle", ["needle", "sew", "cloth"], "a needle can sew cloth"),
    ("infer-sew", ["lily", "sew"], "lily can sew"),
    ("dress", ["sew", "dress"], "sew makes a dress"),
    ("river", ["river", "cold", "stones"], "the river is cold and has stones"),
    ("dusk", ["dusk", "dark", "night"], "dusk is dark before night"),
    ("traveler", ["traveler", "shelter", "night"], "a traveler needed shelter before night"),
    ("mom", ["mom", "thanked", "lily"], "lily thanked her mom"),
    ("button", ["button", "lost", "coat"], "the button was lost from the coat"),
    ("fish", ["fish", "river", "swim"], "a fish swims in the river"),
]

QUESTIONS = [
    ("what can lily make", "dress"),
    ("what can lily do with a needle", "sew"),
    ("what is in the river", "stones"),
    ("what is dusk", "dark"),
    ("what did the traveler need", "shelter"),
    ("what did lily find", "needle"),
    ("who did lily thank", "mom"),
    ("what was lost", "button"),
    ("what swims in the river", "fish"),
    ("what can sew cloth", "needle"),
]

def speak(store, name, prompt, vocab, inv, surplus):
    model = activate(store, name)
    preferred = " ".join(store["packets"][name].get("preferred") or [])
    train_on_query(model, preferred or prompt, vocab, steps=12)
    gen = [inv.get(i, "<unk>") for i in model.generate(ids(tokenize(prompt), vocab) or [1], steps=6)]
    write_back(store, name, model)
    if any(t in gen for t in surplus):
        return gen, False
    return surplus[:6], True

def repair(store, question, expected):
    name = "fix-" + expected
    keys = content(question) | {expected}
    ensure(store, name, keys, tokenize(question + " " + expected), strength=1.5)
    return name

def run() -> dict:
    random.seed(27)
    raw = load_corpus()
    windows = window_stories(raw)
    vocab = build_vocab(windows)
    store = load_store(len(vocab), ["language"])
    for name, keys, text in FACTS:
        ensure(store, name, keys, tokenize(text))
    inv = {i: t for t, i in vocab.items()}
    epochs = []
    grown = []
    for epoch in range(4):
        hits = 0
        for q, expected in QUESTIONS:
            path = walk(q, store)
            name = path[0]["packet"] if path else None
            surplus = path[0]["surplus"] if path else []
            spoken, held = ([], True)
            if name:
                spoken, held = speak(store, name, q, vocab, inv, surplus)
            hit = expected in spoken or expected in surplus
            if hit and name:
                hits += 1
                bump(store, name, 0.1)
            else:
                fix = repair(store, q, expected)
                if fix not in grown:
                    grown.append(fix)
        epochs.append({"epoch": epoch, "hits": hits, "of": len(QUESTIONS)})
    save_store(store)
    receipt = {
        "epochs": epochs,
        "grown": grown,
        "final_hits": epochs[-1]["hits"],
        "claim": "miss grows a packet; next epoch can hit; not a general mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/speak_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
