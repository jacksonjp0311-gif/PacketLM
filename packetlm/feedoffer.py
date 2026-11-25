"""Offer a language packet only if the cross-domain gate kept a pass
and residual coverage increased.

Writes a versioned receipted packet for external use.
Does not push into NOMAD.
"""

from __future__ import annotations
import json
from pathlib import Path
from .store import build_from_corpus
from .train import load_corpus, window_stories
from .learn import run as learn_run
from .gap import run as gap_run

def offer() -> dict:
    learn_receipt = learn_run(passes=2)
    gap_receipt = gap_run()
    kept = learn_receipt.get("any_kept", False)
    residual_reduced = gap_receipt.get("kept", 0) > 0
    packet = None
    if kept and residual_reduced:
        raw = load_corpus()
        windows = window_stories(raw)
        store = build_from_corpus(windows)
        top = store.top_by_strength(1)
        if top:
            sp = top[0]
            packet = {
                "id": sp.id,
                "text": sp.text,
                "strength": round(sp.strength, 3),
                "provenance": sp.provenance,
                "source": "PacketLM",
                "gate": "two_domain+residual",
                "claim": "language window packet; offered only after a kept cross-domain pass and residual reduction; still a proxy"
            }
    out = {
        "offered": packet is not None,
        "gate_kept": kept,
        "residual_reduced": residual_reduced,
        "packet": packet,
        "learn_history": learn_receipt.get("history"),
        "gap": {"proposals": gap_receipt.get("proposals"), "kept": gap_receipt.get("kept")},
        "note": "local offer only; offered only if gate kept a pass and residual reduced; no write into NOMAD"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/feedoffer_receipt.json").write_text(json.dumps(out, indent=2))
    Path("feed").mkdir(exist_ok=True)
    Path("feed/latest_language.json").write_text(json.dumps(packet or {}, indent=2))
    print(json.dumps(out, indent=2))
    return out

if __name__ == "__main__":
    offer()
