"""Mind loop: grow, hold, retrieve.

A novel query grows a packet and seeds it.
A related query routes to that packet.
The answer is the held tokens the query did not say.
That is retrieval, not echo. Not a general mind.
"""

from __future__ import annotations
import json
import random
from pathlib import Path
from .tiny import tokenize, build_vocab
from .train import load_corpus, window_stories
from .nodes import tokens
from .context import load_store, save_store, bump, blank_packet

MEMORY = Path("data/mind_memory.json")
STOP = {"the", "a", "an", "in", "on", "at", "of", "to", "and", "before", "did", "what"}

def content(text: str) -> set[str]:
    return {t for t in tokens(text) if t not in STOP}

def load_memory() -> list[dict]:
    if MEMORY.exists():
        return json.loads(MEMORY.read_text())
    return []

def save_memory(mem: list[dict]) -> None:
    MEMORY.parent.mkdir(exist_ok=True)
    MEMORY.write_text(json.dumps(mem[-32:], indent=2))

def pick(query: str, store: dict) -> tuple[str, int]:
    q = content(query)
    best, best_score = "", 0
    for name, pkt in store["packets"].items():
        s = len(set(pkt.get("keys", [])) & q)
        if s > best_score:
            best, best_score = name, s
    return best, best_score

def grow(store: dict, query: str) -> str:
    name = "pkt-" + str(len(store["packets"]) + 1)
    pkt = blank_packet(store["vocab"])
    pkt["keys"] = sorted(content(query))
    pkt["preferred"] = tokenize(query)
    store["packets"][name] = pkt
    return name

def surplus(preferred: list[str], query: str) -> list[str]:
    q = set(tokenize(query))
    return [t for t in preferred if t not in q and t not in STOP]

def run() -> dict:
    random.seed(18)
    raw = load_corpus()
    windows = window_stories(raw)
    vocab = build_vocab(windows)
    store = load_store(len(vocab), ["language"])
    story = content(" ".join(windows[:8]))
    store["packets"].setdefault("language", blank_packet(len(vocab)))
    store["packets"]["language"]["keys"] = sorted(story)
    memory = load_memory()
    novel = "count the stones in the cold river at dusk"
    related = "stones in the cold river"
    routes = []
    for turn, q in enumerate([novel, related]):
        name, score = pick(q, store)
        grown = score < 2
        if grown:
            name = grow(store, q)
        preferred = store["packets"][name].get("preferred") or []
        extra = surplus(preferred, q)
        bump(store, name, 0.2 if extra else 0.05)
        event = {
            "turn": turn,
            "query": q,
            "packet": name,
            "grown": grown,
            "retrieved": extra,
        }
        memory.append(event)
        routes.append(event)
    save_store(store)
    save_memory(memory)
    same = len(routes) == 2 and routes[1]["packet"] == routes[0]["packet"]
    receipt = {
        "related_same_packet": same,
        "retrieved": routes[1]["retrieved"] if len(routes) > 1 else [],
        "routes": routes,
        "claim": "related query returns held tokens it did not say; retrieval, not a mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/mind_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
