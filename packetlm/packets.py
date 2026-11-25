"""Weight packet primitives. Sparse binary, Hamming identity."""

from __future__ import annotations
import hashlib
from dataclasses import dataclass

BITS = 4096

@dataclass
class Packet:
    bits: bytes          # packed bit vector, length BITS//8
    count: int           # popcount
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
    """Deterministic bit index for a content token."""
    h = hashlib.sha256(token.lower().encode()).digest()
    return int.from_bytes(h[:2], "big") % BITS

def hash_to_bits(text: str, seed: int = 0) -> Packet:
    """Deterministic packet with token feature bits.
    Any window containing a token will overlap that token's packet.
    """
    bits_int = 0
    h = hashlib.sha256(f"{seed}:{text}".encode()).digest()
    for i in range(0, min(len(h), 32)):
        bits_int |= (1 << (h[i] % BITS))
    for token in text.split():
        clean = "".join(c for c in token.lower() if c.isalnum())
        if clean:
            bits_int |= (1 << _token_bit(clean))
    bits = bits_int.to_bytes(BITS // 8, "big")
    count = bin(bits_int).count("1")
    return Packet(bits=bits, count=count)

def identity_packet(token: str) -> Packet:
    """One unique bit for a token. Residual injection of this packet is unambiguous."""
    bit = _token_bit(token)
    bits_int = 1 << bit
    return Packet(bits=bits_int.to_bytes(BITS // 8, "big"), count=1)
