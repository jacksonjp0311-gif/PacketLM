"""Mind loop with a preferred answer.

Route or grow. Answer. Remember.
On a repeat, return the packet's preferred answer and train toward it.
A stable repeat is the first sign the field is holding something.
Not a general mind.
"""

from __future__ import annotations
import json
import random
from pathlib import Path
from .tiny import tokenize, build_vocab, ids
from .train import load_corpus, window_stories, load_probes
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

def run() -> dict:
    random.seed(13)
    raw = load_corpus()
    windows = window_stories(raw)
    vocab = build_vocab(windows)
    probes = {p["prompt"].lower(): p["expected"].lower() for p in load_probes()}
    store = load_store(len(vocab), ["language", "recall", "probe"])
    story = tokens(" ".join(windows[:8]))
    store["packets"].setdefault("language", blank_packet(len(vocab)))
    store["packets"]["language"].setdefault("keys", sorted(story))
    store["packets"].setdefault("recall", blank_packet(len(vocab)))
    store["packets"]["recall"].setdefault("keys", sorted(story | {"what", "who", "find"}))
    inv = {i: t for t, i in vocab.items()}
    memory = load_memory()
    queries = [
        "what did Lily find",
        "what did Lily find",
        "a traveler needed shelter before night",
    ]
    routes = []
    used = set()
    for q in queries:
        name, score = pick(q, store)
        grown = False
        if score == 0:
            name = grow(store, q)
            grown = True
        pkt = store["packets"][name]
        preferred = pkt.get("preferred") or []
        model = activate(store, name)
        train_on_query(model, q, vocab, steps=12)
        if preferred:
            train_on_query(model, " ".join(preferred), vocab, steps=8)
        gen = [inv.get(i, "<unk>") for i in model.generate(ids(tokenize(q), vocab) or [1], steps=6)]
        write_back(store, name, model)
        expected = probes.get(q.lower())
        hit = (expected is not None and expected in gen) or (preferred and preferred == gen)
        if expected and expected in gen:
            pkt["preferred"] = gen
        elif not preferred:
            pkt["preferred"] = gen
        bump(store, name, 0.15 if hit else 0.05)
        used.add(name)
        event = {
            "query": q,
            "packet": name,
            "grown": grown,
            "repeat": bool(preferred),
            "hit": hit,
            "generated": gen,
            "preferred": pkt.get("preferred"),
            "strength": pkt["strength"],
        }
        memory.append(event)
        routes.append(event)
    decay_unused(store, used)
    scaled = scale_field(store)
    save_store(store)
    save_memory(memory)
    receipt = {
        "packets": list(store["packets"].keys()),
        "scaled": scaled,
        "routes": routes,
        "claim": "packet holds a preferred answer and trains toward it on repeat; not a general mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/mind_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
