"""Gated residual walk.

Score is overlap times strength.
A packet with no useful surplus is skipped.
After a hop, the residual becomes the surplus.
The walk follows new information, not leftovers. Not a general mind.
"""

from __future__ import annotations
import json
from pathlib import Path
from .tiny import tokenize, build_vocab
from .train import load_corpus, window_stories
from .nodes import tokens
from .context import load_store, blank_packet

STOP = {"the", "a", "an", "in", "on", "at", "of", "to", "and", "before", "did", "what", "can", "with", "make", "makes", "find"}

def content(text: str) -> set[str]:
    return {t for t in tokens(text) if t not in STOP}

def ensure(store, name, keys, preferred, strength=1.0):
    if name not in store["packets"]:
        store["packets"][name] = blank_packet(store["vocab"])
    store["packets"][name]["keys"] = sorted(keys)
    store["packets"][name]["preferred"] = list(preferred)
    store["packets"][name]["strength"] = strength

def useful(pkt: dict, q: set[str]) -> list[str]:
    return [t for t in pkt.get("preferred", []) if t not in q and t not in STOP]

def best(q: set[str], store: dict, used: set[str]) -> tuple[str, float, list[str]]:
    name, score, extra = "", 0.0, []
    for n, pkt in store["packets"].items():
        if n in used or n in {"language", "recall", "probe"}:
            continue
        o = len(q & set(pkt.get("keys", [])))
        if o == 0:
            continue
        s = o * float(pkt.get("strength", 1.0))
        ex = useful(pkt, q)
        if not ex:
            continue
        if s > score:
            name, score, extra = n, s, ex
    return name, score, extra

def walk(start: str, store: dict, steps: int = 4) -> list[dict]:
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
    ensure(store, "lily", {"lily", "found", "needle"}, tokenize("lily found a needle"), 1.2)
    ensure(store, "needle", {"needle", "sew", "cloth"}, tokenize("a needle can sew cloth"), 1.4)
    ensure(store, "infer-sew", {"lily", "sew"}, tokenize("lily can sew"), 1.6)
    ensure(store, "dress", {"sew", "dress"}, tokenize("sew makes a dress"), 1.3)
    path = walk("what can lily make", store)
    flat = [t for step in path for t in step["surplus"]]
    receipt = {
        "start": "what can lily make",
        "path": path,
        "reached_dress": "dress" in flat,
        "gate": "skip empty surplus and old noise packets",
        "claim": "gated residual walk follows new information; not a general mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/geometry_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
