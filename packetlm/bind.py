"""G38: three partial queries.

Each query is subject and relation only.
The right object must rank first.
If any miss, the run fails.
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

def run() -> dict:
    facts = [
        ("alice", "helps", "bob"),
        ("bob", "helps", "alice"),
        ("mira", "has", "tail"),
        ("lily", "found", "needle"),
        ("needle", "sews", "cloth"),
    ]
    store = [(s, r, o, bind(s, r, o)) for s, r, o in facts]
    queries = [
        ("alice", "helps", "bob"),
        ("bob", "helps", "alice"),
        ("mira", "has", "tail"),
        ("lily", "found", "needle"),
    ]
    rows = []
    for s, r, expected in queries:
        q = partial(s, r)
        ranked = sorted(store, key=lambda item: item[3].score(q), reverse=True)
        top = ranked[0]
        ok = top[0] == s and top[2] == expected
        rows.append({"q": f"{s} {r} ?", "got": top[2], "expected": expected, "ok": ok, "score": top[3].score(q)})
    failed = [row["q"] for row in rows if not row["ok"]]
    receipt = {
        "queries": len(queries),
        "passed": len(failed) == 0,
        "failed": failed,
        "rows": rows,
        "claim": "partial binds retrieve the object by score; not a mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/bind_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
