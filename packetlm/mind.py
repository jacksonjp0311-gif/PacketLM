"""Mind loop.

Perceive a query. Route to a packet or grow one.
Answer from that packet. Update its weights.
Remember the route. On a repeat, the same packet should do better.
This is a field with memory. It is not a general mind.
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
    bump, scale_field, decay_unused, train_on_query, blank_packet,
)

MEMORY = Path("data/mind_memory.json")

def load_memory() -> list[dict]:
    if MEMORY.exists():
        return json.loads(MEMORY.read_text())
    return []

def save_memory(mem: list[dict]) -> None:
    MEMORY.parent.mkdir(exist_ok=True)
    MEMORY.write_text(json.dumps(mem[-32:], indent=2))

def pick(query: str, store: dict) -> tuple[str, int]:
    q = tokens(query)
    best, best_score = "", 0
    for name, pkt in store["packets"].items():
        s = len(set(pkt.get("keys", [])) & q)
        if s > best_score:
            best, best_score = name, s
    return best, best_score

def grow(store: dict, query: str) -> str:
    name = "pkt-" + str(len(store["packets"]) + 1)
    pkt = blank_packet(store["vocab"])
    pkt["keys"] = sorted(tokens(query))
    store["packets"][name] = pkt
    return name

def answer(store, name, query, vocab, inv) -> list[str]:
    model = activate(store, name)
    train_on_query(model, query, vocab, steps=12)
    gen = [inv.get(i, "<unk>") for i in model.generate(ids(tokenize(query), vocab) or [1], steps=6)]
    write_back(store, name, model)
    return gen

def run() -> dict:
    random.seed(12)
    raw = load_corpus()
    windows = window_stories(raw)
    vocab = build_vocab(windows)
    store = load_store(len(vocab), ["language", "recall", "probe"])
    story = tokens(" ".join(windows[:8]))
    store["packets"].setdefault("language", blank_packet(len(vocab)))
    store["packets"]["language"].setdefault("keys", sorted(story))
    inv = {i: t for t, i in vocab.items()}
    memory = load_memory()
    queries = [
        "what did Lily find",
        "a traveler needed shelter before night",
        "what did Lily find",
    ]
    routes = []
    used = set()
    for q in queries:
        name, score = pick(q, store)
        grown = False
        if score == 0:
            name = grow(store, q)
            grown = True
        gen = answer(store, name, q, vocab, inv)
        # repeat of a remembered query is a hit if the packet is the same
        prior = next((m for m in reversed(memory) if m["query"] == q), None)
        same = prior is not None and prior["packet"] == name
        hit = score >= 2 or same
        bump(store, name, 0.15 if hit else -0.05)
        used.add(name)
        event = {
            "query": q,
            "packet": name,
            "grown": grown,
            "overlap": score,
            "repeat": same,
            "generated": gen,
            "strength": store["packets"][name]["strength"],
        }
        memory.append(event)
        routes.append(event)
    decay_unused(store, used)
    scaled = scale_field(store)
    save_store(store)
    save_memory(memory)
    receipt = {
        "packets": list(store["packets"].keys()),
        "memory": len(memory),
        "scaled": scaled,
        "routes": routes,
        "claim": "field with memory; repeats the same packet; not a general mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/mind_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
