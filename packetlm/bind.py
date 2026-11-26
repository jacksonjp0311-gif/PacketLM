"""G38 unbind.

Retrieve by partial bind.
XOR the query back out of the winner.
The remaining bits should match the object role.
Not a general mind.
"""

from __future__ import annotations
import json
import random
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

def xor(a: Packet, b: Packet) -> Packet:
    x = int.from_bytes(a.bits, "big") ^ int.from_bytes(b.bits, "big")
    return Packet(bits=x.to_bytes(BITS // 8, "big"), count=bin(x).count("1"))

def run() -> dict:
    random.seed(39)
    facts = []
    seen = set()
    while len(facts) < 100:
        s, r, o = f"s{random.randrange(30)}", f"r{random.randrange(8)}", f"o{random.randrange(30)}"
        if (s, r) in seen:
            continue
        seen.add((s, r))
        facts.append((s, r, o, bind(s, r, o)))
    hits = 0
    unbound = 0
    for s, r, o, pkt in facts:
        q = partial(s, r)
        winner = max(facts, key=lambda item: item[3].score(q))
        if winner[2] != o:
            continue
        hits += 1
        left = xor(winner[3], q)
        obj = rotate(identity_packet(o), 128)
        if left.bits == obj.bits:
            unbound += 1
    receipt = {
        "facts": len(facts),
        "retrieved": hits,
        "unbound_exact": unbound,
        "claim": "unbind recovers the object role bits; not a mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/bind_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
