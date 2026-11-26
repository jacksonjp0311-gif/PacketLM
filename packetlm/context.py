"""Context packets with plasticity.

Router activates one packet.
A hit strengthens it. A miss weakens it.
If total strength runs high, the field scales down.
Unused packets decay a little.
"""

from __future__ import annotations
import json
import random
from pathlib import Path
from .tiny import TinyLM, tokenize, build_vocab, ids, DIM
from .train import load_corpus, window_stories, load_probes
from .nodes import tokens, route, Node

STORE = Path("data/context_packets.json")
CAP = 6.0

def blank_packet(vocab_size: int) -> dict:
    model = TinyLM(vocab_size)
    return {"E": model.E, "Wo": model.Wo, "strength": 1.0, "uses": 0}

def load_store(vocab_size: int, names: list[str]) -> dict:
    if STORE.exists():
        data = json.loads(STORE.read_text())
        if data.get("vocab") == vocab_size:
            for name in names:
                data["packets"].setdefault(name, blank_packet(vocab_size))
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

def write_back(store: dict, name: str, model: TinyLM) -> None:
    store["packets"][name]["E"] = model.E
    store["packets"][name]["Wo"] = model.Wo

def bump(store: dict, name: str, amount: float) -> None:
    pkt = store["packets"][name]
    pkt["strength"] = round(max(0.1, pkt.get("strength", 1.0) + amount), 3)
    pkt["uses"] = pkt.get("uses", 0) + 1

def scale_field(store: dict) -> bool:
    total = sum(p.get("strength", 1.0) for p in store["packets"].values())
    if total <= CAP:
        return False
    factor = CAP / total
    for p in store["packets"].values():
        p["strength"] = round(max(0.1, p.get("strength", 1.0) * factor), 3)
    return True

def decay_unused(store: dict, used: set[str]) -> None:
    for name, p in store["packets"].items():
        if name not in used:
            p["strength"] = round(max(0.1, p.get("strength", 1.0) - 0.02), 3)

def train_on_query(model: TinyLM, query: str, vocab: dict, steps: int = 8) -> None:
    toks = tokenize(query)
    if len(toks) < 2:
        return
    for _ in range(steps):
        i = random.randrange(1, len(toks))
        ctx = ids(toks[max(0, i - 6):i], vocab)
        model.step(ctx, vocab.get(toks[i], 1))

def run() -> dict:
    random.seed(10)
    raw = load_corpus()
    windows = window_stories(raw)
    vocab = build_vocab(windows)
    probes = load_probes()
    expected = {p["expected"].lower() for p in probes}
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
        "a traveler needed shelter before night",
    ]
    inv = {i: t for t, i in vocab.items()}
    routes = []
    used = set()
    for q in queries:
        node, score = route(q, nodes)
        model = activate(store, node.name)
        train_on_query(model, q, vocab)
        gen = [inv.get(i, "<unk>") for i in model.generate(ids(tokenize(q), vocab) or [1], steps=4)]
        write_back(store, node.name, model)
        hit = score > 0 and (any(t in expected for t in gen) or score >= 2)
        bump(store, node.name, 0.1 if hit else -0.05)
        used.add(node.name)
        routes.append({
            "query": q,
            "node": node.name,
            "overlap": score,
            "hit": hit,
            "generated": gen,
            "strength": store["packets"][node.name]["strength"],
        })
    decay_unused(store, used)
    scaled = scale_field(store)
    save_store(store)
    receipt = {
        "strengths": {k: v["strength"] for k, v in store["packets"].items()},
        "scaled": scaled,
        "routes": routes,
        "claim": "hit strengthens, miss weakens, field scales; not an intelligence"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/context_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
