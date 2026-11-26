"""Correction and retention.

16-bit identities.
Change one fact. The old object must go. The new object must decode.
An unrelated fact must still decode after the change.
Not a general mind.
"""

from __future__ import annotations
import json
import hashlib
from pathlib import Path
from .packets import Packet, BITS

FIELD = Path("data/evolve_field.json")

def bits_for(token: str, nbits: int, role: int) -> int:
    h = hashlib.sha256(f"{role}:{token}".encode()).digest()
    acc = 0
    for i in range(nbits):
        idx = int.from_bytes(h[i * 2:(i * 2) + 2], "big") % BITS
        acc |= 1 << idx
    return acc

def pack(n: int) -> Packet:
    return Packet(bits=n.to_bytes(BITS // 8, "big"), count=bin(n).count("1"))

def bind(s: str, r: str, o: str) -> Packet:
    return pack(bits_for(s, 16, 0) ^ bits_for(r, 16, 1) ^ bits_for(o, 16, 2))

def partial(s: str, r: str) -> Packet:
    return pack(bits_for(s, 16, 0) ^ bits_for(r, 16, 1))

def decode(left: Packet, objects: list[str]) -> str | None:
    for name in objects:
        if left.bits == pack(bits_for(name, 16, 2)).bits:
            return name
    return None

def ask(field: list[dict], s: str, r: str, objects: list[str]) -> str | None:
    q = partial(s, r)
    best, best_s = None, 0
    for item in field:
        pkt = Packet(bits=bytes.fromhex(item["bits"]), count=item["count"])
        sc = pkt.score(q)
        if sc > best_s:
            best, best_s = pkt, sc
    if not best:
        return None
    left = pack(int.from_bytes(best.bits, "big") ^ int.from_bytes(q.bits, "big"))
    return decode(left, objects)

def run() -> dict:
    objects = ["blue", "green", "tail", "needle", "bob"]
    facts = [
        {"s": "mira", "r": "tail", "o": "blue"},
        {"s": "lily", "r": "found", "o": "needle"},
        {"s": "alice", "r": "helps", "o": "bob"},
    ]
    field = []
    for f in facts:
        pkt = bind(f["s"], f["r"], f["o"])
        field.append({**f, "bits": pkt.bits.hex(), "count": pkt.count})
    before = ask(field, "mira", "tail", objects)
    # correct mira's tail to green: remove old, add new
    field = [f for f in field if not (f["s"] == "mira" and f["r"] == "tail")]
    pkt = bind("mira", "tail", "green")
    field.append({"s": "mira", "r": "tail", "o": "green", "bits": pkt.bits.hex(), "count": pkt.count})
    FIELD.parent.mkdir(exist_ok=True)
    FIELD.write_text(json.dumps(field))
    loaded = json.loads(FIELD.read_text())
    after = ask(loaded, "mira", "tail", objects)
    kept = ask(loaded, "lily", "found", objects)
    receipt = {
        "before": before,
        "after_correction": after,
        "unrelated_kept": kept,
        "corrected": before == "blue" and after == "green",
        "retained": kept == "needle",
        "reloaded": True,
        "claim": "correction replaces one fact; unrelated fact remains; not a mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/evolve_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if not (receipt["corrected"] and receipt["retained"]):
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
