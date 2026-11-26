"""Canonical field plus a composition rule.

Ancestor is transitive. A walk may derive an unstored link.
Helps is not. A walk is not a claim that Alice helps Dee.
Failed field checks exit nonzero.
Not a general mind.
"""

from __future__ import annotations
import json
from pathlib import Path
from .field import add, ask, save, load
from .packets import hash_to_bits
from .router import Router
from .tiny import TinyLM, tokenize, build_vocab, ids
from .train import load_corpus, window_stories

FIELD = Path("data/system_field.json")
TRANSITIVE = {"ancestor"}

def compose(field, start, relation, objects, steps=3) -> list[str]:
    if relation not in TRANSITIVE:
        return []
    walked, cur = [], start
    for _ in range(steps):
        nxt = ask(field, cur, relation, objects)
        if not nxt:
            break
        walked.append(nxt)
        cur = nxt
    return walked

def run() -> dict:
    objects = ["bob", "cara", "dee", "green", "needle", "ann", "bea", "cy"]
    field = []
    for s, r, o in [
        ("ann", "ancestor", "bea"),
        ("bea", "ancestor", "cy"),
        ("alice", "helps", "bob"),
        ("bob", "helps", "cara"),
        ("lily", "found", "needle"),
        ("mira", "tail", "green"),
    ]:
        add(field, s, r, o)
    save(FIELD, field)
    loaded = load(FIELD)
    derived = compose(loaded, "ann", "ancestor", objects)
    helps_composed = compose(loaded, "alice", "helps", objects)
    kept = ask(loaded, "lily", "found", objects)
    unknown = ask(loaded, "nope", "nope", objects)
    tight = hash_to_bits("lily needle")
    wide = hash_to_bits("lily needle river stones dusk")
    top = Router([tight, wide]).select(hash_to_bits("lily needle"), k=1)[0][0]
    checks = {
        "derived_cy": derived[-1] == "cy" if derived else False,
        "helps_not_composed": helps_composed == [],
        "retained": kept == "needle",
        "unknown_abstained": unknown is None,
        "tight_won": top is tight,
        "reloaded": len(loaded) == len(field),
    }
    raw = load_corpus()
    windows = window_stories(raw)
    vocab = build_vocab(windows)
    train_facts = ["lily found needle", "mira tail green"]
    for text in train_facts:
        for t in tokenize(text):
            if t not in vocab:
                vocab[t] = len(vocab)
    model = TinyLM(len(vocab))
    inv = {i: t for t, i in vocab.items()}
    for text in train_facts:
        toks = ids(tokenize(text), vocab)
        for _ in range(30):
            for i in range(1, len(toks)):
                model.step(toks[:i], toks[i], lr=0.25)
    spoken = {}
    for prompt, expected in [("lily found", "needle"), ("mira tail", "green")]:
        gen = [inv.get(i, "<unk>") for i in model.generate(ids(tokenize(prompt), vocab), steps=2)]
        spoken[prompt] = {"gen": gen, "hit": expected in gen}
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "derived": derived,
        "spoken": spoken,
        "generated_hits": sum(1 for v in spoken.values() if v["hit"]),
        "failed": failed,
        "claim": "only transitive relations compose; helps does not; not a mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/system_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
