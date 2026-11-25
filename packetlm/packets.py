"""Weight packet primitives. Sparse binary, Hamming identity."""

from __future__ import annotations
import hashlib
from dataclasses import dataclass
from typing import Iterable

BITS = 4096

@dataclass
class Packet:
    bits: bytes          # packed bit vector, length BITS//8
    count: int           # popcount
    meta: dict | None = None

    def overlap(self, other: Packet) -> int:
        # popcount of AND
        return bin(int.from_bytes(self.bits, "big") & int.from_bytes(other.bits, "big")).count("1")

    def hamming(self, other: Packet) -> int:
        return self.count + other.count - 2 * self.overlap(other)

    def score(self, query: Packet) -> int:
        """2*|q ∧ p| - |p|  ≡  |q| - H(q, p)"""
        return 2 * query.overlap(self) - self.count

def hash_to_bits(text: str, seed: int = 0) -> Packet:
    """Deterministic sparse feature hash → 4096-bit packet. Stub."""
    h = hashlib.sha256(f"{seed}:{text}".encode()).digest()
    # expand to 512 bytes then thin — real encoder later
    bits = (h * (BITS // 256))[: BITS // 8]
    count = bin(int.from_bytes(bits, "big")).count("1")
    return Packet(bits=bits, count=count)
