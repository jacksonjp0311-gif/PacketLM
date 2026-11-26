"""Field geometry.

A query and a packet are sets.
Overlap o(q, p) = |q ∩ p|.
For indicator vectors this is |q| - H(q, p), the Bitwork form.
Surplus is what the packet holds that the query did not say.
A hop takes the highest-overlap surplus token as the next query.
The walk is the inference. Not a general mind.
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

def hamming(q: set[str], p: set[str]) -> int:
    return len(q ^ p)

def ensure(store, name, keys, preferred):
    if name not in store["packets"]:
        store["packets"][name] = blank_packet(store["vocab"])
    store["packets"][name]["keys"] = sorted(keys)
    store["packets"][name]["preferred"] = list(preferred)

def best(q: set[str], store: dict) -> tuple[str, int]:
    name, score = "", 0
    for n, pkt in store["packets"].items():
        if n == "language":
            continue
        s = overlap(q, set(pkt.get("keys", [])))
        if s > score:
            name, score = n, s
    return name, score

def surplus(pkt: dict, q: set[str]) -> list[str]:
    return [t for t in pkt.get("preferred", []) if t not in q and t not in STOP]

def walk(start: str, store: dict, steps: int = 3) -> list[dict]:
    q = content(start)
    seen = set()
    path = []
    for _ in range(steps):
        name, score = best(q, store)
        if not name or name in seen or score == 0:
            break
        seen.add(name)
        extra = surplus(store["packets"][name], q)
        path.append({"packet": name, "overlap": score, "surplus": extra})
        if not extra:
            break
        # next query is the surplus token with the most packet overlap
        nxt = max(extra, key=lambda t: best(content(t), store)[1])
        q = content(nxt) | {nxt}
    return path

def run() -> dict:
    raw = load_corpus()
    windows = window_stories(raw)
    vocab = build_vocab(windows)
    store = load_store(len(vocab), ["language"])
    ensure(store, "lily", {"lily", "found", "needle"}, tokenize("lily found a needle"))
    ensure(store, "needle", {"needle", "sew", "cloth"}, tokenize("a needle can sew cloth"))
    ensure(store, "infer-sew", {"lily", "sew", "needle"}, tokenize("lily can sew"))
    ensure(store, "dress", {"sew", "dress", "cloth"}, tokenize("sew makes a dress"))
    path = walk("lily", store)
    tokens_out = [t for step in path for t in step["surplus"]]
    receipt = {
        "start": "lily",
        "path": path,
        "reached_dress": "dress" in tokens_out,
        "identity": "overlap = |q| - H(q, p) on indicators",
        "claim": "scored walk across packets; not a general mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/geometry_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
