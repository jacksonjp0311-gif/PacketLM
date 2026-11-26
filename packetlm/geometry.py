"""Field geometry on the Bitwork score.

Score is 2|q ∩ p| - |p|.
A larger packet is not favored just for being larger.
Surplus is still what the packet holds that the query did not say.
Not a general mind.
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

def bitwork(q: set[str], p: set[str]) -> int:
    overlap = len(q & p)
    return 2 * overlap - len(p)

def ensure(store, name, keys, preferred, strength=1.0):
    if name not in store["packets"]:
        store["packets"][name] = blank_packet(store["vocab"])
    store["packets"][name]["keys"] = sorted(set(keys))
    store["packets"][name]["preferred"] = list(preferred)
    store["packets"][name].setdefault("strength", strength)

def useful(pkt, q):
    return [t for t in pkt.get("preferred", []) if t not in q and t not in STOP]

def best(q, store, used):
    name, score, extra = "", -10**9, []
    for n, pkt in store["packets"].items():
        if n in used or n in {"language", "recall", "probe"}:
            continue
        keys = set(pkt.get("keys", []))
        s = bitwork(q, keys) * float(pkt.get("strength", 1.0))
        ex = useful(pkt, q)
        if ex and s > score:
            name, score, extra = n, s, ex
    if score <= 0:
        return "", 0.0, []
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
        ("dress", ["sew", "dress"], "sew makes a dress"),
        ("river", ["river", "cold", "stones"], "the river is cold and has stones"),
        ("dusk", ["dusk", "dark", "night"], "dusk is dark before night"),
        ("traveler", ["traveler", "shelter", "night"], "a traveler needed shelter before night"),
        ("wide", ["lily", "found", "needle", "river", "stones", "dusk", "night", "cold"], "a wide packet that should lose"),
    ]
    for name, keys, text in facts:
        ensure(store, name, keys, tokenize(text))
    questions = [
        ("what can lily make", "dress"),
        ("what is in the river", "stones"),
        ("what is dusk", "dark"),
        ("what did lily find", "needle"),
    ]
    results = []
    wide_won = 0
    for q, expected in questions:
        path = walk(q, store)
        flat = [t for step in path for t in step["surplus"]]
        winner = path[0]["packet"] if path else None
        if winner == "wide":
            wide_won += 1
        results.append({"q": q, "winner": winner, "hit": expected in flat})
    receipt = {
        "score": "2|q∩p|-|p|",
        "wide_packet_wins": wide_won,
        "results": results,
        "claim": "field walk uses Bitwork score; a wide packet should not win on size"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/geometry_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
