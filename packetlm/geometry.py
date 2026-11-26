"""Multi-question residual training.

Several questions in one run.
Each walks the field.
A hit strengthens every packet on the path.
A miss weakens the first packet.
Pace over one-at-a-time. Not a general mind.
"""

from __future__ import annotations
import json
from pathlib import Path
from .tiny import tokenize, build_vocab
from .train import load_corpus, window_stories
from .nodes import tokens
from .context import load_store, save_store, bump, blank_packet

STOP = {"the", "a", "an", "in", "on", "at", "of", "to", "and", "before", "did", "what", "can", "with", "make", "makes"}

def content(text: str) -> set[str]:
    return {t for t in tokens(text) if t not in STOP}

def ensure(store, name, keys, preferred, strength=1.0):
    if name not in store["packets"]:
        store["packets"][name] = blank_packet(store["vocab"])
    store["packets"][name]["keys"] = sorted(set(keys))
    store["packets"][name]["preferred"] = list(preferred)
    store["packets"][name].setdefault("strength", strength)

def useful(pkt, q):
    return [t for t in pkt.get("preferred", []) if t not in q and t not in STOP]

def best(q, store, used):
    name, score, extra = "", 0.0, []
    for n, pkt in store["packets"].items():
        if n in used or n in {"language", "recall", "probe"}:
            continue
        o = len(q & set(pkt.get("keys", [])))
        if o == 0:
            continue
        s = o * float(pkt.get("strength", 1.0))
        ex = useful(pkt, q)
        if ex and s > score:
            name, score, extra = n, s, ex
    return name, score, extra

def walk(start, store, steps=4):
    residual = content(start)
    used = set()
    path = []
    for _ in range(steps):
        name, score, extra = best(residual, store, used)
        if not name:
            break
        path.append({"packet": name, "score": round(score, 3), "surplus": extra})
        used.add(name)
        residual = content(" ".join(extra))
        if not residual:
            break
    return path

def run() -> dict:
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
    questions = [
        ("what can lily make", "dress"),
        ("what can lily do with a needle", "sew"),
        ("what is in the river", "stones"),
        ("what is dusk", "dark"),
        ("what did the traveler need", "shelter"),
        ("what did lily find", "needle"),
    ]
    results = []
    hits = 0
    for q, expected in questions:
        path = walk(q, store)
        flat = [t for step in path for t in step["surplus"]]
        hit = expected in flat
        if hit:
            hits += 1
            for step in path:
                bump(store, step["packet"], 0.1)
        elif path:
            bump(store, path[0]["packet"], -0.05)
        results.append({"q": q, "expected": expected, "hit": hit, "path": [s["packet"] for s in path]})
    save_store(store)
    receipt = {
        "questions": len(questions),
        "hits": hits,
        "results": results,
        "claim": "multi-question residual training; hits strengthen the path; not a general mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/geometry_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
