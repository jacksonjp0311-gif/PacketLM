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

    def union(self, other: Packet) -> Packet:
        """Bitwise OR. Used by residual path accumulation."""
        a = int.from_bytes(self.bits, "big")
        b = int.from_bytes(other.bits, "big")
        u = a | b
        return Packet(bits=u.to_bytes(BITS // 8, "big"), count=bin(u).count("1"))

def hash_to_bits(text: str, seed: int = 0) -> Packet:
    """Deterministic sparse feature hash → 4096-bit packet.
    Sparser than before so residual hops can cover remaining bits."""
    h = hashlib.sha256(f"{seed}:{text}".encode()).digest()
    # take only every 4th bit to keep density low
    raw = int.from_bytes(h * (BITS // 256), "big")
    bits_int = 0
    for i in range(BITS):
        if (raw >> (i * 4)) & 1:
            bits_int |= (1 << i)
    bits = bits_int.to_bytes(BITS // 8, "big")
    count = bin(bits_int).count("1")
    return Packet(bits=bits, count=count)
