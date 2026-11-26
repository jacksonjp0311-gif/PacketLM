"""G38 at scale.

200 random subject-relation-object facts.
Each is queried as subject + relation.
Accuracy is how often the right object ranks first.
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

def run() -> dict:
    random.seed(38)
    subjects = [f"s{i}" for i in range(40)]
    relations = [f"r{i}" for i in range(10)]
    objects = [f"o{i}" for i in range(40)]
    facts = []
    seen = set()
    while len(facts) < 200:
        s = random.choice(subjects)
        r = random.choice(relations)
        o = random.choice(objects)
        if (s, r) in seen:
            continue
        seen.add((s, r))
        facts.append((s, r, o, bind(s, r, o)))
    hits = 0
    for s, r, o, _ in facts:
        q = partial(s, r)
        ranked = max(facts, key=lambda item: item[3].score(q))
        if ranked[2] == o:
            hits += 1
    acc = hits / len(facts)
    receipt = {
        "facts": len(facts),
        "hits": hits,
        "accuracy": round(acc, 4),
        "claim": "partial bind retrieval on 200 random facts; not a mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/bind_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
