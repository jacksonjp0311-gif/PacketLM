"""G38: retrieve from a partial bind.

Store full role-bound facts.
Query with subject and relation only.
The matching fact should rank first by Bitwork score.
Not a general mind.
"""

from __future__ import annotations
import json
from pathlib import Path
from .packets import Packet, BITS, identity_packet

def rotate(pkt: Packet, k: int) -> Packet:
    n = int.from_bytes(pkt.bits, "big")
    k = k % BITS
    rotated = ((n << k) | (n >> (BITS - k))) & ((1 << BITS) - 1)
    return Packet(bits=rotated.to_bytes(BITS // 8, "big"), count=bin(rotated).count("1"))

def bind(subject: str, relation: str, obj: str) -> Packet:
    s = rotate(identity_packet(subject), 0)
    r = rotate(identity_packet(relation), 64)
    o = rotate(identity_packet(obj), 128)
    x = int.from_bytes(s.bits, "big") ^ int.from_bytes(r.bits, "big") ^ int.from_bytes(o.bits, "big")
    return Packet(bits=x.to_bytes(BITS // 8, "big"), count=bin(x).count("1"))

def partial(subject: str, relation: str) -> Packet:
    s = rotate(identity_packet(subject), 0)
    r = rotate(identity_packet(relation), 64)
    x = int.from_bytes(s.bits, "big") ^ int.from_bytes(r.bits, "big")
    return Packet(bits=x.to_bytes(BITS // 8, "big"), count=bin(x).count("1"))

def as_hex(pkt: Packet) -> str:
    return pkt.bits.hex()

def from_hex(h: str) -> Packet:
    raw = bytes.fromhex(h)
    return Packet(bits=raw, count=bin(int.from_bytes(raw, "big")).count("1"))

def run() -> dict:
    facts = [
        ("alice", "helps", "bob"),
        ("bob", "helps", "alice"),
        ("mira", "has", "tail"),
        ("lily", "found", "needle"),
    ]
    store = [{"s": s, "r": r, "o": o, "bits": as_hex(bind(s, r, o))} for s, r, o in facts]
    query = partial("alice", "helps")
    ranked = []
    for item in store:
        pkt = from_hex(item["bits"])
        ranked.append((item["s"], item["r"], item["o"], pkt.score(query)))
    ranked.sort(key=lambda x: x[3], reverse=True)
    top = ranked[0]
    ok = top[0] == "alice" and top[2] == "bob"
    receipt = {
        "query": "alice helps ?",
        "top": {"subject": top[0], "object": top[2], "score": top[3]},
        "ranked": [{"s": a, "o": c, "score": s} for a, _, c, s in ranked],
        "retrieved_bob": ok,
        "claim": "partial bind retrieves the object by score; not a mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/bind_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if not ok:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
