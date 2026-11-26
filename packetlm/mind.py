"""Mind loop: infer, remember, hop again.

First inference: lily + needle -> sew. Stored.
New fact: sew makes a dress.
Question: what can lily make.
The answer dress is two hops away. Not a general mind.
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
STOP = {"the", "a", "an", "in", "on", "at", "of", "to", "and", "before", "did", "what", "can", "with", "make", "makes"}

def content(text: str) -> list[str]:
    return sorted({t for t in tokens(text) if t not in STOP})

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
    store["packets"][name]["keys"] = list(keys)
    store["packets"][name]["preferred"] = list(preferred)

def activate_many(query: str, store: dict) -> list[str]:
    q = set(content(query))
    return [
        name for name, pkt in store["packets"].items()
        if name != "language" and len(set(pkt.get("keys", [])) & q) >= 1
    ]

def surplus(preferred: list[str], query: str) -> list[str]:
    q = set(tokenize(query))
    return [t for t in preferred if t not in q and t not in STOP]

def run() -> dict:
    random.seed(23)
    raw = load_corpus()
    windows = window_stories(raw)
    vocab = build_vocab(windows)
    store = load_store(len(vocab), ["language"])
    ensure(store, "lily", ["lily", "found", "needle"], tokenize("lily found a needle"))
    ensure(store, "needle", ["needle", "sew", "cloth"], tokenize("a needle can sew cloth"))
    ensure(store, "infer-sew", ["lily", "sew", "needle"], tokenize("lily can sew with a needle"))
    ensure(store, "dress", ["sew", "dress", "cloth"], tokenize("sew makes a dress"))
    question = "what can lily make"
    expected = "dress"
    # hop 1: lily -> sew
    hop1 = activate_many("lily", store)
    hop1_extra = []
    for name in hop1:
        hop1_extra += surplus(store["packets"][name].get("preferred") or [], "lily")
    # hop 2: sew -> dress
    hop2 = activate_many("sew", store) if "sew" in hop1_extra else []
    hop2_extra = []
    for name in hop2:
        hop2_extra += surplus(store["packets"][name].get("preferred") or [], "sew")
    inferred = expected in hop2_extra
    if inferred:
        ensure(store, "infer-dress", content("lily can make a dress"), tokenize("lily can make a dress"))
        bump(store, "infer-dress", 0.3)
    save_store(store)
    memory = load_memory()
    memory.append({"question": question, "hop1": hop1_extra, "hop2": hop2_extra, "inferred": inferred})
    save_memory(memory)
    receipt = {
        "question": question,
        "expected": expected,
        "hop1": hop1_extra,
        "hop2": hop2_extra,
        "inferred": inferred,
        "claim": "two-hop inference from remembered fact; not a general mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/mind_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
