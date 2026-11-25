"""Self-improvement step.

Propose a strength change. Keep it only if the packet helps a sealed probe
more than the empty baseline. Record the receipt.
"""

from __future__ import annotations
import json
from pathlib import Path
from .packets import hash_to_bits
from .store import PacketStore, build_from_corpus
from .train import load_corpus, window_stories, load_probes
from .router import Router

def probe_overlap(store: PacketStore, probe: dict) -> int:
    if not store.packets:
        return 0
    q = hash_to_bits(probe["prompt"])
    exp = hash_to_bits(probe["expected"])
    router = Router(store.as_list())
    scored = router.select(q, k=1)
    if not scored:
        return 0
    return scored[0][0].overlap(exp)

def improve_once(store: PacketStore, probes: list[dict]) -> dict:
    """For each packet, measure cold vs field on probes. Raise strength if field helps."""
    cold = PacketStore()
    changes = []
    for sp in list(store.packets):
        # temporary field with this packet only
        field = PacketStore()
        field.packets = [sp]
        field_score = sum(probe_overlap(field, p) for p in probes)
        cold_score = sum(probe_overlap(cold, p) for p in probes)
        if field_score > cold_score:
            delta = 0.1 * (field_score - cold_score)
            store.update_strength(sp.id, delta, f"probe_help:{field_score}>{cold_score}")
            changes.append({"id": sp.id, "delta": delta, "field": field_score, "cold": cold_score})
    return {"changes": changes, "packets": len(store.packets)}

def run() -> dict:
    raw = load_corpus()
    corpus = window_stories(raw)
    store = build_from_corpus(corpus)
    probes = load_probes()
    result = improve_once(store, probes)
    store.save()
    receipt = {
        "packets": len(store.packets),
        "changes": result["changes"],
        "top": [
            {"id": sp.id, "strength": sp.strength, "hits": sp.hits, "text": sp.text[:60]}
            for sp in store.top_by_strength(5)
        ],
        "claim": "strength raised only when a packet helps a sealed probe more than empty; still a proxy"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/improve_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
