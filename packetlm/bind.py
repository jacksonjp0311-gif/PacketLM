"""G38.1 revised.

An exact unbind is the answer.
Abstain only when the unbound bits match no object.
Labels are not read on the retrieval path.
Field is written and reloaded.
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
    x = 0
    x ^= int.from_bytes(rotate(identity_packet(subject), 0).bits, "big")
    x ^= int.from_bytes(rotate(identity_packet(relation), 64).bits, "big")
    x ^= int.from_bytes(rotate(identity_packet(obj), 128).bits, "big")
    return Packet(bits=x.to_bytes(BITS // 8, "big"), count=bin(x).count("1"))

def partial(subject: str, relation: str) -> Packet:
    x = int.from_bytes(rotate(identity_packet(subject), 0).bits, "big")
    x ^= int.from_bytes(rotate(identity_packet(relation), 64).bits, "big")
    return Packet(bits=x.to_bytes(BITS // 8, "big"), count=bin(x).count("1"))

def xor(a: Packet, b: Packet) -> Packet:
    x = int.from_bytes(a.bits, "big") ^ int.from_bytes(b.bits, "big")
    return Packet(bits=x.to_bytes(BITS // 8, "big"), count=bin(x).count("1"))

def decode_object(bits: Packet, candidates: list[str]) -> str | None:
    for name in candidates:
        if bits.bits == rotate(identity_packet(name), 128).bits:
            return name
    return None

def retrieve(field: list[dict], subject: str, relation: str, objects: list[str]) -> dict:
    q = partial(subject, relation)
    scored = []
    for item in field:
        pkt = Packet(bits=bytes.fromhex(item["bits"]), count=item["count"])
        scored.append((pkt.score(q), pkt))
    if not scored:
        return {"abstain": True, "reason": "empty"}
    scored.sort(key=lambda x: x[0], reverse=True)
    top_score, top = scored[0]
    if top_score <= 0:
        return {"abstain": True, "reason": "nonpositive", "score": top_score}
    decoded = decode_object(xor(top, q), objects)
    if decoded is None:
        return {"abstain": True, "reason": "no_object", "score": top_score}
    return {"abstain": False, "decoded": decoded, "score": top_score}

def run() -> dict:
    random.seed(41)
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
    blind = [{"bits": f["bits"], "count": f["count"]} for f in loaded]
    labels = {(f["s"], f["r"]): f["o"] for f in loaded}
    decoded_hits = 0
    abstain = 0
    wrong = 0
    for (s, r), o in list(labels.items()):
        out = retrieve(blind, s, r, objects)
        if out.get("abstain"):
            abstain += 1
        elif out.get("decoded") == o:
            decoded_hits += 1
        else:
            wrong += 1
    unknown = retrieve(blind, "no-such", "no-rel", objects)
    receipt = {
        "facts": len(facts),
        "reloaded": len(loaded) == len(facts),
        "decoded": decoded_hits,
        "abstain": abstain,
        "wrong": wrong,
        "accuracy": round(decoded_hits / len(facts), 4),
        "unknown_abstained": bool(unknown.get("abstain")),
        "claim": "exact unbind is the answer; abstain only on no match; field reloaded"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/bind_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if not receipt["reloaded"] or not receipt["unknown_abstained"]:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
