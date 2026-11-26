"""Weight packet primitives. Sparse binary, Hamming identity."""

from __future__ import annotations
import hashlib
from dataclasses import dataclass

BITS = 4096

@dataclass
class Packet:
    bits: bytes
    count: int
    meta: dict | None = None

    def overlap(self, other: Packet) -> int:
        return bin(int.from_bytes(self.bits, "big") & int.from_bytes(other.bits, "big")).count("1")

    def hamming(self, other: Packet) -> int:
        return self.count + other.count - 2 * self.overlap(other)

    def score(self, query: Packet) -> int:
        """2*|q ∧ p| - |p|  ≡  |q| - H(q, p)"""
        return 2 * query.overlap(self) - self.count

    def union(self, other: Packet) -> Packet:
        a = int.from_bytes(self.bits, "big")
        b = int.from_bytes(other.bits, "big")
        u = a | b
        return Packet(bits=u.to_bytes(BITS // 8, "big"), count=bin(u).count("1"))

def _token_bit(token: str) -> int:
    h = hashlib.sha256(token.lower().encode()).digest()
    return int.from_bytes(h[:2], "big") % BITS

def hash_to_bits(text: str, seed: int = 0) -> Packet:
    """Token features plus sentence features spread across all 4096 bits."""
    bits_int = 0
    digest = hashlib.sha256(f"{seed}:{text}".encode()).digest()
    for i in range(8):
        idx = int.from_bytes(digest[i * 2:(i * 2) + 2], "big") % BITS
        bits_int |= 1 << idx
    for token in text.split():
        clean = "".join(c for c in token.lower() if c.isalnum())
        if clean:
            bits_int |= 1 << _token_bit(clean)
    bits = bits_int.to_bytes(BITS // 8, "big")
    return Packet(bits=bits, count=bin(bits_int).count("1"))

def identity_packet(token: str) -> Packet:
    bit = _token_bit(token)
    bits_int = 1 << bit
    return Packet(bits=bits_int.to_bytes(BITS // 8, "big"), count=1)
