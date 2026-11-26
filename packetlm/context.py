"""Context packets.

Each node is a packet of weights, not one shared file.
The router picks a node by overlap.
Only that node's weights are used to answer.
A successful use raises the node's strength.
"""

from __future__ import annotations
import json
import random
from pathlib import Path
from .tiny import TinyLM, tokenize, build_vocab, ids, DIM
from .train import load_corpus, window_stories, load_probes
from .nodes import tokens, route, Node

STORE = Path("data/context_packets.json")

def blank_packet(vocab_size: int) -> dict:
    model = TinyLM(vocab_size)
    return {"E": model.E, "Wo": model.Wo, "strength": 1.0}

def load_store(vocab_size: int, names: list[str]) -> dict:
    if STORE.exists():
        data = json.loads(STORE.read_text())
        if data.get("vocab") == vocab_size:
            return data
    return {
        "vocab": vocab_size,
        "dim": DIM,
        "packets": {name: blank_packet(vocab_size) for name in names},
    }

def save_store(store: dict) -> None:
    STORE.parent.mkdir(exist_ok=True)
    STORE.write_text(json.dumps(store))

def activate(store: dict, name: str) -> TinyLM:
    pkt = store["packets"][name]
    model = TinyLM(store["vocab"])
    model.E = pkt["E"]
    model.Wo = pkt["Wo"]
    return model

def strengthen(store: dict, name: str, amount: float = 0.1) -> None:
    store["packets"][name]["strength"] = round(
        store["packets"][name].get("strength", 1.0) + amount, 3
    )

def run() -> dict:
    random.seed(8)
    raw = load_corpus()
    windows = window_stories(raw)
    vocab = build_vocab(windows)
    probes = load_probes()
    story_keys = tokens(" ".join(windows[:8]))
    probe_keys = tokens(" ".join(p["prompt"] for p in probes))
    nodes = [
        Node("language", "stories", story_keys, ""),
        Node("recall", "seen", story_keys | {"what", "who", "find"}, ""),
        Node("probe", "sealed", probe_keys, ""),
    ]
    store = load_store(len(vocab), [n.name for n in nodes])
    queries = [
        "One day a little girl named Lily found a needle",
        "what did Lily find",
        "how did they feel",
    ]
    routes = []
    for q in queries:
        node, score = route(q, nodes)
        model = activate(store, node.name)
        gen_ids = model.generate(ids(tokenize(q), vocab) or [1], steps=4)
        inv = {i: t for t, i in vocab.items()}
        gen = [inv.get(i, "<unk>") for i in gen_ids]
        # a use that overlaps the node's keys strengthens the pathway
        if score > 0:
            strengthen(store, node.name)
        routes.append({
            "query": q,
            "node": node.name,
            "overlap": score,
            "activated": True,
            "generated": gen,
            "strength": store["packets"][node.name]["strength"],
        })
    save_store(store)
    receipt = {
        "packets": list(store["packets"].keys()),
        "strengths": {k: v["strength"] for k, v in store["packets"].items()},
        "routes": routes,
        "claim": "weights live in nodes; router activates one packet; use strengthens it; not an intelligence"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/context_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
