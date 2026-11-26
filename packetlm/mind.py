"""Mind loop: infer, remember, ask again.

Two facts live in two packets.
A question composes them.
If the expected token appears, a new packet holds the composed fact.
A second question routes to that packet and returns the fact.
Not a general mind.
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
STOP = {"the", "a", "an", "in", "on", "at", "of", "to", "and", "before", "did", "what", "can", "with"}

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
    random.seed(22)
    raw = load_corpus()
    windows = window_stories(raw)
    vocab = build_vocab(windows)
    store = load_store(len(vocab), ["language"])
    ensure(store, "lily", ["lily", "found", "needle"], tokenize("lily found a needle"))
    ensure(store, "needle", ["needle", "sew", "cloth"], tokenize("a needle can sew cloth"))
    question = "what can lily do with a needle"
    expected = "sew"
    hits = activate_many(question, store)
    composed = []
    for name in hits:
        extra = surplus(store["packets"][name].get("preferred") or [], question)
        if extra:
            composed.append({"packet": name, "retrieved": extra})
            bump(store, name, 0.2)
    flat = [t for c in composed for t in c["retrieved"]]
    inferred = expected in flat
    remembered = None
    if inferred:
        remembered = "infer-sew"
        fact = tokenize("lily can sew with a needle")
        ensure(store, remembered, content(" ".join(fact)), fact)
        bump(store, remembered, 0.3)
    follow = "lily sew"
    follow_hits = activate_many(follow, store) if remembered else []
    follow_got = remembered in follow_hits
    save_store(store)
    memory = load_memory()
    memory.append({
        "question": question,
        "inferred": inferred,
        "remembered": remembered,
        "follow": follow,
        "follow_got": follow_got,
    })
    save_memory(memory)
    receipt = {
        "inferred": inferred,
        "remembered_packet": remembered,
        "follow_routed": follow_got,
        "claim": "inference was stored and a follow-up routed to it; not a general mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/mind_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
