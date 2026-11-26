"""Field geometry with a residual walk.

Score is overlap times strength.
After a hop, the packet's keys are removed from the residual.
The next hop sees only what is left.
That is the Bitwork residual. Not a general mind.
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

def overlap(q: set[str], p: set[str]) -> int:
    return len(q & p)

def ensure(store, name, keys, preferred, strength=1.0):
    if name not in store["packets"]:
        store["packets"][name] = blank_packet(store["vocab"])
    store["packets"][name]["keys"] = sorted(keys)
    store["packets"][name]["preferred"] = list(preferred)
    store["packets"][name]["strength"] = strength

def best(q: set[str], store: dict, used: set[str]) -> tuple[str, float]:
    name, score = "", 0.0
    for n, pkt in store["packets"].items():
        if n == "language" or n in used:
            continue
        o = overlap(q, set(pkt.get("keys", [])))
        s = o * float(pkt.get("strength", 1.0))
        if s > score:
            name, score = n, s
    return name, score

def residual_walk(start: str, store: dict, steps: int = 4) -> list[dict]:
    residual = content(start)
    used = set()
    path = []
    for _ in range(steps):
        name, score = best(residual, store, used)
        if not name or score == 0:
            break
        pkt = store["packets"][name]
        keys = set(pkt.get("keys", []))
        extra = [t for t in pkt.get("preferred", []) if t not in residual and t not in STOP]
        path.append({
            "packet": name,
            "score": round(score, 3),
            "residual_before": sorted(residual),
            "surplus": extra,
        })
        used.add(name)
        residual = residual - keys
        if extra:
            residual |= content(extra[0])
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
    ensure(store, "infer-sew", {"lily", "sew", "needle"}, tokenize("lily can sew"), 1.6)
    ensure(store, "dress", {"sew", "dress", "cloth"}, tokenize("sew makes a dress"), 1.3)
    path = residual_walk("what can lily make", store)
    flat = [t for step in path for t in step["surplus"]]
    receipt = {
        "start": "what can lily make",
        "path": path,
        "reached_dress": "dress" in flat,
        "score": "overlap * strength",
        "claim": "residual walk; used bits removed; not a general mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/geometry_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
