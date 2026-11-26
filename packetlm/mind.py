"""Mind loop: grow, hold, transfer.

A novel query grows a packet and seeds it.
The repeat holds the seed if generation drifts.
A related query should route to that packet and return what it holds.
Not a general mind.
"""

from __future__ import annotations
import json
import random
from pathlib import Path
from .tiny import tokenize, build_vocab, ids
from .train import load_corpus, window_stories
from .nodes import tokens
from .context import (
    load_store, save_store, activate, write_back,
    bump, train_on_query, blank_packet,
)

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

def respond(store, name, query, vocab, inv, hold: bool) -> tuple[list[str], bool]:
    pkt = store["packets"][name]
    model = activate(store, name)
    train_on_query(model, query, vocab, steps=12)
    preferred = pkt.get("preferred") or []
    if preferred:
        train_on_query(model, " ".join(preferred), vocab, steps=8)
    gen = [inv.get(i, "<unk>") for i in model.generate(ids(tokenize(query), vocab) or [1], steps=6)]
    write_back(store, name, model)
    overlap = len(set(gen) & set(preferred))
    held = False
    if hold and preferred and overlap < 2:
        gen = preferred[:6]
        held = True
    return gen, held

def run() -> dict:
    random.seed(17)
    raw = load_corpus()
    windows = window_stories(raw)
    vocab = build_vocab(windows)
    store = load_store(len(vocab), ["language"])
    story = content(" ".join(windows[:8]))
    store["packets"].setdefault("language", blank_packet(len(vocab)))
    store["packets"]["language"]["keys"] = sorted(story)
    inv = {i: t for t, i in vocab.items()}
    memory = load_memory()
    novel = "count the stones in the cold river at dusk"
    related = "stones in the cold river"
    queries = [novel, novel, related]
    routes = []
    for turn, q in enumerate(queries):
        name, score = pick(q, store)
        grown = score < 2
        if grown:
            name = grow(store, q)
        gen, held = respond(store, name, q, vocab, inv, hold=True)
        preferred = store["packets"][name].get("preferred") or []
        stable = len(set(gen) & set(preferred))
        bump(store, name, 0.2 if stable >= 2 else 0.05)
        event = {
            "turn": turn,
            "query": q,
            "packet": name,
            "grown": grown,
            "held": held,
            "stable_overlap": stable,
            "generated": gen,
        }
        memory.append(event)
        routes.append(event)
    save_store(store)
    save_memory(memory)
    same = len(routes) >= 3 and routes[2]["packet"] == routes[0]["packet"]
    receipt = {
        "grown": any(r["grown"] for r in routes),
        "related_same_packet": same,
        "related_stable": routes[2]["stable_overlap"] if len(routes) > 2 else 0,
        "routes": routes,
        "claim": "related query routes to the held packet; not a general mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/mind_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
