"""Canonical geometric field.

One bind. One ask. One persist.
A packet that does not decode is skipped.
Save replaces the file, it does not truncate it first.
Not a general mind.
"""

from __future__ import annotations
import json
import hashlib
import os
from functools import lru_cache
from pathlib import Path
from .packets import Packet, BITS

@lru_cache(maxsize=None)  # pure function of its arguments
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
    scored = []
    for item in field:
        pkt = Packet(bits=bytes.fromhex(item["bits"]), count=item["count"])
        scored.append((pkt.score(q), pkt))
    for _, pkt in sorted(scored, key=lambda pair: pair[0], reverse=True):
        if _ <= 0:
            break
        left = pack(int.from_bytes(pkt.bits, "big") ^ int.from_bytes(q.bits, "big"))
        found = decode(left, objects)
        if found:
            return found
    return None

def add(field: list[dict], s: str, r: str, o: str) -> None:
    pkt = bind(s, r, o)
    field.append({"s": s, "r": r, "o": o, "bits": pkt.bits.hex(), "count": pkt.count})

def save(path: Path, field) -> None:
    path.parent.mkdir(exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(field))
    os.replace(tmp, path)

def load(path: Path):
    return json.loads(path.read_text())
