"""A field, not a transformer.

A query routes to a packet by overlap.
The packet answers.
If nothing overlaps, a new packet is grown and bound to the query.
Hits strengthen. Misses weaken. The field scales.
No stacked attention. No single weight file.
"""

from __future__ import annotations
import json
import random
from pathlib import Path
from .tiny import TinyLM, tokenize, build_vocab, ids, DIM
from .train import load_corpus, window_stories
from .nodes import tokens
from .context import load_store, save_store, activate, write_back, bump, scale_field, decay_unused, train_on_query, blank_packet

def pick(query: str, store: dict) -> tuple[str, int]:
    q = tokens(query)
    best = None
    best_score = 0
    for name, pkt in store["packets"].items():
        keys = set(pkt.get("keys", []))
        s = len(keys & q)
        if s > best_score:
            best = name
            best_score = s
    return best or "", best_score

def grow(store: dict, query: str) -> str:
    name = "pkt-" + str(len(store["packets"]) + 1)
    pkt = blank_packet(store["vocab"])
    pkt["keys"] = sorted(tokens(query))
    store["packets"][name] = pkt
    return name

def run() -> dict:
    random.seed(11)
    raw = load_corpus()
    windows = window_stories(raw)
    vocab = build_vocab(windows)
    store = load_store(len(vocab), ["language", "recall", "probe"])
    # seed keys if missing
    story = tokens(" ".join(windows[:8]))
    store["packets"].setdefault("language", blank_packet(len(vocab)))
    store["packets"]["language"].setdefault("keys", sorted(story))
    store["packets"].setdefault("recall", blank_packet(len(vocab)))
    store["packets"]["recall"].setdefault("keys", sorted(story | {"what", "who", "find"}))
    store["packets"].setdefault("probe", blank_packet(len(vocab)))
    store["packets"]["probe"].setdefault("keys", ["feel", "thanked", "fix", "sew"])
    queries = [
        "what did Lily find",
        "how did they feel",
        "a traveler needed shelter before night",
        "count the stones in the river",
    ]
    inv = {i: t for t, i in vocab.items()}
    routes = []
    used = set()
    grown = []
    for q in queries:
        name, score = pick(q, store)
        if score == 0:
            name = grow(store, q)
            grown.append(name)
            score = len(tokens(q))
        model = activate(store, name)
        train_on_query(model, q, vocab)
        gen = [inv.get(i, "<unk>") for i in model.generate(ids(tokenize(q), vocab) or [1], steps=4)]
        write_back(store, name, model)
        hit = score >= 2
        bump(store, name, 0.1 if hit else -0.05)
        used.add(name)
        routes.append({
            "query": q,
            "packet": name,
            "overlap": score,
            "grown": name in grown,
            "generated": gen,
            "strength": store["packets"][name]["strength"],
        })
    decay_unused(store, used)
    scaled = scale_field(store)
    save_store(store)
    receipt = {
        "packets": list(store["packets"].keys()),
        "grown": grown,
        "scaled": scaled,
        "routes": routes,
        "claim": "field of packets; grows when nothing overlaps; not a mind, not a transformer"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/mind_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
