"""Mind loop: grow, repeat, score stability.

A query with no overlap grows a packet.
The same query is asked again.
The second answer is scored against the first.
Stability on a new thing is the signal. Not a general mind.
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
    pkt["preferred"] = []
    store["packets"][name] = pkt
    return name

def respond(store, name, query, vocab, inv) -> list[str]:
    pkt = store["packets"][name]
    model = activate(store, name)
    train_on_query(model, query, vocab, steps=12)
    if pkt.get("preferred"):
        train_on_query(model, " ".join(pkt["preferred"]), vocab, steps=8)
    gen = [inv.get(i, "<unk>") for i in model.generate(ids(tokenize(query), vocab) or [1], steps=6)]
    write_back(store, name, model)
    return gen

def overlap_answers(a: list[str], b: list[str]) -> int:
    return len(set(a) & set(b))

def run() -> dict:
    random.seed(14)
    raw = load_corpus()
    windows = window_stories(raw)
    vocab = build_vocab(windows)
    store = load_store(len(vocab), ["language"])
    story = tokens(" ".join(windows[:8]))
    store["packets"].setdefault("language", blank_packet(len(vocab)))
    store["packets"]["language"].setdefault("keys", sorted(story))
    inv = {i: t for t, i in vocab.items()}
    memory = load_memory()
    novel = "count the stones in the cold river at dusk"
    routes = []
    first = None
    for turn, q in enumerate([novel, novel]):
        name, score = pick(q, store)
        grown = False
        if score == 0:
            name = grow(store, q)
            grown = True
        gen = respond(store, name, q, vocab, inv)
        stable = 0
        if first is not None:
            stable = overlap_answers(first, gen)
            store["packets"][name]["preferred"] = first
        else:
            first = gen
            store["packets"][name]["preferred"] = gen
        bump(store, name, 0.1 if stable else 0.05)
        event = {
            "turn": turn,
            "query": q,
            "packet": name,
            "grown": grown,
            "generated": gen,
            "stable_overlap": stable,
        }
        memory.append(event)
        routes.append(event)
    save_store(store)
    save_memory(memory)
    receipt = {
        "novel": novel,
        "packet": routes[-1]["packet"] if routes else None,
        "stable_overlap": routes[-1]["stable_overlap"] if routes else 0,
        "routes": routes,
        "claim": "new query grows a packet; repeat scored against first answer; not a general mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/mind_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
