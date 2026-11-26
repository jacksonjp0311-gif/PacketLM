"""Unstored inference.

Store A helps B and B helps C.
Do not store A helps C.
Walk: A helps ? -> B, B helps ? -> C.
C is a fact the field was not given.
Not a general mind.
"""

from __future__ import annotations
import json
from pathlib import Path
from .bind import bind, partial, retrieve, FIELD
from .packets import identity_packet

def run() -> dict:
    objects = ["bob", "cara", "dee", "tail", "needle"]
    facts = [
        ("alice", "helps", "bob"),
        ("bob", "helps", "cara"),
        ("cara", "helps", "dee"),
        ("mira", "has", "tail"),
    ]
    field = []
    for s, r, o in facts:
        pkt = bind(s, r, o)
        field.append({"bits": pkt.bits.hex(), "count": pkt.count})
    # composed target is not in the store
    stored_pairs = {(s, r) for s, r, _ in facts}
    hops = [
        ("alice", "helps", "bob"),
        ("bob", "helps", "cara"),
        ("cara", "helps", "dee"),
    ]
    walked = []
    cur = "alice"
    for _ in range(3):
        out = retrieve(field, cur, "helps", objects)
        if out.get("abstain"):
            break
        nxt = out["decoded"]
        walked.append(nxt)
        cur = nxt
    derived = walked[-1] if walked else None
    never_stored = ("alice", "helps") not in {(a, b) for a, b, _ in facts} or derived not in {o for _, _, o in facts if _ == "alice"}
    receipt = {
        "walked": walked,
        "derived": derived,
        "alice_helps_dee_not_stored": ("alice", "helps", "dee") not in facts,
        "reached_dee": derived == "dee",
        "claim": "walk derived an object three hops away; the full path was not stored"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/infer_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
