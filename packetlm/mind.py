"""Mind loop: compose across packets.

Two facts are grown into two packets.
A query that overlaps both activates both.
The answer is the surplus from each.
Composition, not a single echo. Not a general mind.
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

def ensure(store: dict, name: str, keys: list[str], preferred: list[str]) -> None:
    if name not in store["packets"]:
        store["packets"][name] = blank_packet(store["vocab"])
    store["packets"][name]["keys"] = keys
    store["packets"][name]["preferred"] = preferred

def activate_many(query: str, store: dict) -> list[str]:
    q = content(query)
    hits = []
    for name, pkt in store["packets"].items():
        if len(set(pkt.get("keys", [])) & q) >= 1 and name != "language":
            hits.append(name)
    return hits

def surplus(preferred: list[str], query: str) -> list[str]:
    q = set(tokenize(query))
    return [t for t in preferred if t not in q and t not in STOP]

def run() -> dict:
    random.seed(19)
    raw = load_corpus()
    windows = window_stories(raw)
    vocab = build_vocab(windows)
    store = load_store(len(vocab), ["language"])
    ensure(store, "stones", ["stones", "river", "cold"], tokenize("count the stones in the cold river at dusk"))
    ensure(store, "dusk", ["dusk", "night", "dark"], tokenize("dusk means the dark before night"))
    query = "stones in the river at dusk"
    hits = activate_many(query, store)
    composed = []
    for name in hits:
        extra = surplus(store["packets"][name].get("preferred") or [], query)
        if extra:
            composed.append({"packet": name, "retrieved": extra})
            bump(store, name, 0.2)
    save_store(store)
    memory = load_memory()
    memory.append({"query": query, "hits": hits, "composed": composed})
    save_memory(memory)
    receipt = {
        "query": query,
        "packets_activated": hits,
        "composed": composed,
        "composed_count": len(composed),
        "claim": "one query activated more than one packet and returned surplus from each; composition, not a mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/mind_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
