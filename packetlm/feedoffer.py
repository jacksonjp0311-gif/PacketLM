"""Offer a kept gap packet only if the cross-domain gate kept a pass
and residual coverage increased.

The offered packet is the last kept gap proposal, not a corpus window.
Does not push into NOMAD.
"""

from __future__ import annotations
import json
from pathlib import Path
from .learn import run as learn_run
from .gap import run as gap_run

def offer() -> dict:
    learn_receipt = learn_run(passes=2)
    gap_receipt = gap_run()
    kept = learn_receipt.get("any_kept", False)
    residual_reduced = gap_receipt.get("kept", 0) > 0
    packet = None
    if kept and residual_reduced and gap_receipt.get("last_kept"):
        packet = {
            "id": "gap_kept",
            "text": gap_receipt["last_kept"],
            "source": "PacketLM",
            "gate": "two_domain+residual+gap",
            "provenance": "gap_proposal",
            "claim": "kept gap packet; offered only after a kept cross-domain pass and residual reduction; still a proxy"
        }
    out = {
        "offered": packet is not None,
        "gate_kept": kept,
        "residual_reduced": residual_reduced,
        "packet": packet,
        "learn_history": learn_receipt.get("history"),
        "gap": {
            "proposals": gap_receipt.get("proposals"),
            "kept": gap_receipt.get("kept"),
            "last_kept": gap_receipt.get("last_kept")
        },
        "note": "local offer only; offered packet is a kept gap proposal; no write into NOMAD"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/feedoffer_receipt.json").write_text(json.dumps(out, indent=2))
    Path("feed").mkdir(exist_ok=True)
    Path("feed/latest_language.json").write_text(json.dumps(packet or {}, indent=2))
    print(json.dumps(out, indent=2))
    return out

if __name__ == "__main__":
    offer()
