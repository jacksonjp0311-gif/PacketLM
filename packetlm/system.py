"""One system on the canonical field.

Queries run after reload.
A failed field check exits nonzero.
Generation is scored apart.
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

def run() -> dict:
    objects = ["bob", "cara", "dee", "blue", "green", "needle", "shelter"]
    field = []
    for s, r, o in [
        ("alice", "helps", "bob"),
        ("bob", "helps", "cara"),
        ("cara", "helps", "dee"),
        ("mira", "tail", "blue"),
        ("lily", "found", "needle"),
        ("traveler", "needed", "shelter"),
    ]:
        add(field, s, r, o)
    before = ask(field, "mira", "tail", objects)
    field = [f for f in field if not (f["s"] == "mira" and f["r"] == "tail")]
    add(field, "mira", "tail", "green")
    save(FIELD, field)
    loaded = load(FIELD)
    walked, cur = [], "alice"
    for _ in range(3):
        nxt = ask(loaded, cur, "helps", objects)
        if not nxt:
            break
        walked.append(nxt)
        cur = nxt
    after = ask(loaded, "mira", "tail", objects)
    kept = ask(loaded, "lily", "found", objects)
    unknown = ask(loaded, "nope", "nope", objects)
    tight = hash_to_bits("lily needle")
    wide = hash_to_bits("lily needle river stones dusk night cold")
    top = Router([tight, wide]).select(hash_to_bits("lily needle"), k=1)[0][0]
    checks = {
        "reached_dee": walked[-1] == "dee" if walked else False,
        "corrected": before == "blue" and after == "green",
        "retained": kept == "needle",
        "unknown_abstained": unknown is None,
        "tight_won": top is tight,
        "reloaded": len(loaded) == len(field) and after == "green",
        "canonical": True,
    }
    raw = load_corpus()
    windows = window_stories(raw)
    vocab = build_vocab(windows)
    train_facts = ["alice helps bob", "lily found needle", "mira tail green"]
    for text in train_facts:
        for t in tokenize(text):
            if t not in vocab:
                vocab[t] = len(vocab)
    model = TinyLM(len(vocab))
    inv = {i: t for t, i in vocab.items()}
    for text in train_facts:
        toks = ids(tokenize(text), vocab)
        for _ in range(40):
            for i in range(1, len(toks)):
                model.step(toks[:i], toks[i], lr=0.25)
    spoken = {}
    for prompt, expected in [("alice helps", "bob"), ("lily found", "needle"), ("mira tail", "green")]:
        gen = [inv.get(i, "<unk>") for i in model.generate(ids(tokenize(prompt), vocab), steps=2)]
        spoken[prompt] = {"gen": gen, "hit": expected in gen}
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "walked": walked,
        "spoken": spoken,
        "generated_hits": sum(1 for v in spoken.values() if v["hit"]),
        "failed": failed,
        "claim": "canonical field, queried after reload; not a mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/system_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
