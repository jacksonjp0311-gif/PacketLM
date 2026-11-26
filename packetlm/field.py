"""Canonical geometric field.

One bind. One ask. One persist.
16-bit role-conditioned identities.
Other modules should use this, not a copy.
"""

from __future__ import annotations
import json
import hashlib
from pathlib import Path
from .packets import Packet, BITS

def bits_for(token: str, role: int, nbits: int = 16) -> int:
    h = hashlib.sha256(f"{role}:{token}".encode()).digest()
    acc = 0
    for i in range(nbits):
        acc |= 1 << (int.from_bytes(h[i * 2:(i * 2) + 2], "big") % BITS)
    return acc

def pack(n: int) -> Packet:
    return Packet(bits=n.to_bytes(BITS // 8, "big"), count=bin(n).count("1"))

def bind(s: str, r: str, o: str) -> Packet:
    return pack(bits_for(s, 0) ^ bits_for(r, 1) ^ bits_for(o, 2))

def partial(s: str, r: str) -> Packet:
    return pack(bits_for(s, 0) ^ bits_for(r, 1))

def decode(left: Packet, objects: list[str]) -> str | None:
    for name in objects:
        if left.bits == pack(bits_for(name, 2)).bits:
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

def add(field: list[dict], s: str, r: str, o: str) -> None:
    pkt = bind(s, r, o)
    field.append({"s": s, "r": r, "o": o, "bits": pkt.bits.hex(), "count": pkt.count})

def save(path: Path, field: list[dict]) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(field))

def load(path: Path) -> list[dict]:
    return json.loads(path.read_text())
