"""G38.1

Decode the object from unbound bits. Do not read the stored label.
Abstain when the best score is not clearly above the rest.
Persist the bound field so a second pass can reload it.
Not a general mind.
"""

from __future__ import annotations
import json
import random
from pathlib import Path
from .packets import Packet, BITS, identity_packet

FIELD = Path("data/bound_field.json")

def rotate(pkt: Packet, k: int) -> Packet:
    n = int.from_bytes(pkt.bits, "big")
    k = k % BITS
    rotated = ((n << k) | (n >> (BITS - k))) & ((1 << BITS) - 1)
    return Packet(bits=rotated.to_bytes(BITS // 8, "big"), count=bin(rotated).count("1"))

def bind(subject: str, relation: str, obj: str) -> Packet:
    parts = [
        rotate(identity_packet(subject), 0),
        rotate(identity_packet(relation), 64),
        rotate(identity_packet(obj), 128),
    ]
    x = 0
    for p in parts:
        x ^= int.from_bytes(p.bits, "big")
    return Packet(bits=x.to_bytes(BITS // 8, "big"), count=bin(x).count("1"))

def partial(subject: str, relation: str) -> Packet:
    x = int.from_bytes(rotate(identity_packet(subject), 0).bits, "big")
    x ^= int.from_bytes(rotate(identity_packet(relation), 64).bits, "big")
    return Packet(bits=x.to_bytes(BITS // 8, "big"), count=bin(x).count("1"))

def xor(a: Packet, b: Packet) -> Packet:
    x = int.from_bytes(a.bits, "big") ^ int.from_bytes(b.bits, "big")
    return Packet(bits=x.to_bytes(BITS // 8, "big"), count=bin(x).count("1"))

def decode_object(bits: Packet, candidates: list[str]) -> str | None:
    """Match unbound bits to an object identity. No stored label."""
    best, best_h = None, BITS + 1
    for name in candidates:
        obj = rotate(identity_packet(name), 128)
        h = bits.hamming(obj)
        if h < best_h:
            best, best_h = name, h
    return best if best_h == 0 else None

def retrieve(field: list[dict], subject: str, relation: str, objects: list[str]) -> dict:
    q = partial(subject, relation)
    scored = []
    for item in field:
        pkt = Packet(bits=bytes.fromhex(item["bits"]), count=item["count"])
        scored.append((item, pkt.score(q), pkt))
    scored.sort(key=lambda x: x[1], reverse=True)
    if not scored:
        return {"abstain": True, "reason": "empty"}
    top_score = scored[0][1]
    second = scored[1][1] if len(scored) > 1 else -BITS
    if top_score <= 0 or top_score - second < 1:
        return {"abstain": True, "reason": "weak", "top": top_score, "second": second}
    left = xor(scored[0][2], q)
    decoded = decode_object(left, objects)
    return {
        "abstain": decoded is None,
        "decoded": decoded,
        "score": top_score,
        "margin": top_score - second,
    }

def run() -> dict:
    random.seed(40)
    subjects = [f"s{i}" for i in range(20)]
    relations = [f"r{i}" for i in range(6)]
    objects = [f"o{i}" for i in range(20)]
    facts = []
    seen = set()
    while len(facts) < 80:
        s, r, o = random.choice(subjects), random.choice(relations), random.choice(objects)
        if (s, r) in seen:
            continue
        seen.add((s, r))
        pkt = bind(s, r, o)
        facts.append({"s": s, "r": r, "o": o, "bits": pkt.bits.hex(), "count": pkt.count})
    FIELD.parent.mkdir(exist_ok=True)
    FIELD.write_text(json.dumps(facts))
    loaded = json.loads(FIELD.read_text())
    # drop labels from the retrieval path
    blind = [{"bits": f["bits"], "count": f["count"]} for f in loaded]
    labels = {(f["s"], f["r"]): f["o"] for f in loaded}
    hits = 0
    decoded_hits = 0
    for (s, r), o in labels.items():
        out = retrieve(blind, s, r, objects)
        if out.get("decoded") == o:
            decoded_hits += 1
        if not out.get("abstain"):
            hits += 1
    # unknown query should abstain
    unknown = retrieve(blind, "no-such", "no-rel", objects)
    receipt = {
        "facts": len(facts),
        "reloaded": len(loaded) == len(facts),
        "decoded": decoded_hits,
        "answered": hits,
        "accuracy": round(decoded_hits / len(facts), 4),
        "unknown_abstained": bool(unknown.get("abstain")),
        "claim": "decoded without the label; abstained on unknown; field reloaded"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/bind_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if not receipt["reloaded"] or not receipt["unknown_abstained"]:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
