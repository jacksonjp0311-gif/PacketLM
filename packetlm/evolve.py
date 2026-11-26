"""One evolution pass.

Multi-bit identities versus one bit.
Multi-object retrieval for one relation.
Unstored walk.
Abstain on unknown.
Persist and reload.
Not a general mind.
"""

from __future__ import annotations
import json
import hashlib
import random
from pathlib import Path
from .packets import Packet, BITS

FIELD = Path("data/evolve_field.json")

def bits_for(token: str, nbits: int, role: int) -> int:
    h = hashlib.sha256(f"{role}:{token}".encode()).digest()
    acc = 0
    for i in range(nbits):
        idx = int.from_bytes(h[i*2:(i*2)+2], "big") % BITS
        acc |= 1 << idx
    return acc

def pack(n: int) -> Packet:
    return Packet(bits=n.to_bytes(BITS // 8, "big"), count=bin(n).count("1"))

def bind(s: str, r: str, o: str, nbits: int) -> Packet:
    x = bits_for(s, nbits, 0) ^ bits_for(r, nbits, 1) ^ bits_for(o, nbits, 2)
    return pack(x)

def partial(s: str, r: str, nbits: int) -> Packet:
    return pack(bits_for(s, nbits, 0) ^ bits_for(r, nbits, 1))

def decode(left: Packet, objects: list[str], nbits: int) -> str | None:
    for name in objects:
        if left.bits == pack(bits_for(name, nbits, 2)).bits:
            return name
    return None

def collisions(tokens: list[str], nbits: int) -> int:
    seen = {}
    hit = 0
    for t in tokens:
        b = bits_for(t, nbits, 0)
        if b in seen:
            hit += 1
        seen[b] = t
    return hit

def run() -> dict:
    random.seed(42)
    tokens = [f"t{i}" for i in range(500)]
    coll = {"1bit": collisions(tokens, 1), "16bit": collisions(tokens, 16)}
    objects = [f"o{i}" for i in range(30)]
    facts = []
    # multi-object: s0 owns three things
    for o in ["o1", "o2", "o3"]:
        pkt = bind("s0", "owns", o, 8)
        facts.append({"s": "s0", "r": "owns", "o": o, "bits": pkt.bits.hex(), "count": pkt.count})
    seen = set()
    while len(facts) < 60:
        s, r, o = f"s{random.randrange(15)}", f"r{random.randrange(5)}", random.choice(objects)
        if (s, r, o) in seen:
            continue
        seen.add((s, r, o))
        pkt = bind(s, r, o, 8)
        facts.append({"s": s, "r": r, "o": o, "bits": pkt.bits.hex(), "count": pkt.count})
    FIELD.parent.mkdir(exist_ok=True)
    FIELD.write_text(json.dumps(facts))
    loaded = json.loads(FIELD.read_text())
    # multi-object retrieve
    q = partial("s0", "owns", 8)
    owned = []
    for item in loaded:
        pkt = Packet(bits=bytes.fromhex(item["bits"]), count=item["count"])
        if pkt.score(q) > 0:
            left = pack(int.from_bytes(pkt.bits, "big") ^ int.from_bytes(q.bits, "big"))
            name = decode(left, objects + ["o1", "o2", "o3"], 8)
            if name:
                owned.append(name)
    # walk
    chain = [("a", "helps", "b"), ("b", "helps", "c"), ("c", "helps", "d")]
    chain_field = []
    for s, r, o in chain:
        pkt = bind(s, r, o, 8)
        chain_field.append({"bits": pkt.bits.hex(), "count": pkt.count})
    walked = []
    cur = "a"
    for _ in range(3):
        pq = partial(cur, "helps", 8)
        best, best_s = None, 0
        for item in chain_field:
            pkt = Packet(bits=bytes.fromhex(item["bits"]), count=item["count"])
            sc = pkt.score(pq)
            if sc > best_s:
                best, best_s = pkt, sc
        if not best:
            break
        left = pack(int.from_bytes(best.bits, "big") ^ int.from_bytes(pq.bits, "big"))
        nxt = decode(left, ["a", "b", "c", "d"], 8)
        if not nxt:
            break
        walked.append(nxt)
        cur = nxt
    unknown = partial("nope", "nope", 8)
    unk_scores = [
        Packet(bits=bytes.fromhex(i["bits"]), count=i["count"]).score(unknown)
        for i in loaded
    ]
    abstained = max(unk_scores) <= 0 if unk_scores else True
    receipt = {
        "collisions_500": coll,
        "multi_object": sorted(set(owned)),
        "multi_object_ok": set(owned) >= {"o1", "o2", "o3"},
        "walked": walked,
        "reached_d": walked[-1] == "d" if walked else False,
        "reloaded": len(loaded) == len(facts),
        "unknown_abstained": abstained,
        "claim": "one pass: multi-bit, multi-object, walk, abstain, persist; not a mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/evolve_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
