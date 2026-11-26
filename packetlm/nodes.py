"""Nodes and a Bitwork-style router.

A query becomes a token set. Overlap picks a node.
Each node has a job: language, recall, or probe.
The answer and the route are receipted.
Stories are the language node's data, not the whole system.
"""

from __future__ import annotations
import json
from pathlib import Path
from .train import load_corpus, window_stories, load_probes
from .tiny import tokenize

def tokens(text: str) -> set[str]:
    return {t for t in text.lower().split() if t}

class Node:
    def __init__(self, name: str, job: str, keys: set[str], answer: str):
        self.name = name
        self.job = job
        self.keys = keys
        self.answer = answer

    def overlap(self, query: set[str]) -> int:
        return len(self.keys & query)

def build_nodes() -> list[Node]:
    raw = load_corpus()
    windows = window_stories(raw)
    story_keys = tokens(" ".join(windows[:8]))
    probes = load_probes()
    probe_keys = tokens(" ".join(p["prompt"] + " " + p["expected"] for p in probes))
    return [
        Node("language", "next-word on stories", story_keys, "language node: stories are my data"),
        Node("recall", "what was seen", story_keys | {"what", "who", "find", "found"}, "recall node: I return what the stories contain"),
        Node("probe", "sealed questions", probe_keys, "probe node: I answer only what a sealed probe names"),
    ]

def route(query: str, nodes: list[Node]) -> tuple[Node, int]:
    q = tokens(query)
    best = nodes[0]
    best_score = -1
    for n in nodes:
        s = n.overlap(q)
        if s > best_score:
            best = n
            best_score = s
    return best, best_score

def run() -> dict:
    nodes = build_nodes()
    queries = [
        "One day a little girl named Lily found a needle",
        "what did Lily find",
        "Lily thanked her mom how did they feel",
        "a traveler needed shelter",
    ]
    routes = []
    for q in queries:
        node, score = route(q, nodes)
        routes.append({
            "query": q,
            "node": node.name,
            "job": node.job,
            "overlap": score,
            "answer": node.answer,
        })
    receipt = {
        "nodes": [n.name for n in nodes],
        "routes": routes,
        "claim": "nodes routed by overlap; stories are one node's data; not an intelligence"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/nodes_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
