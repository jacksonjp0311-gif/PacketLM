"""Offer a language packet.

Writes a versioned, receipted language packet that an external system can pull.
Does not push into NOMAD. PacketLM remains the authority on its own store.
"""

from __future__ import annotations
import json
from pathlib import Path
from .store import build_from_corpus
from .train import load_corpus, window_stories
from .learn import run as learn_run

def offer() -> dict:
    # ensure store has been through at least one learning pass
    learn_receipt = learn_run(passes=2)
    raw = load_corpus()
    windows = window_stories(raw)
    store = build_from_corpus(windows)
    top = store.top_by_strength(1)
    packet = None
    if top:
        sp = top[0]
        packet = {
            "id": sp.id,
            "text": sp.text,
            "strength": round(sp.strength, 3),
            "provenance": sp.provenance,
            "source": "PacketLM",
            "claim": "language window packet; strength from sealed-probe and next-segment updates; still a proxy"
        }
    out = {
        "offered": packet is not None,
        "packet": packet,
        "learn_any_improved": learn_receipt.get("any_improved"),
        "learn_history": learn_receipt.get("history"),
        "note": "local offer only; no write into NOMAD"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/feedoffer_receipt.json").write_text(json.dumps(out, indent=2))
    Path("feed").mkdir(exist_ok=True)
    Path("feed/latest_language.json").write_text(json.dumps(packet or {}, indent=2))
    print(json.dumps(out, indent=2))
    return out

if __name__ == "__main__":
    offer()
