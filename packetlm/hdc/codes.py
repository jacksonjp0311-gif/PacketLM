"""Sparse block codes (docs/G60H.md §2).

A code has K blocks; each block holds one active position out of L (a one-hot block), so the code is a
sparse binary vector of dimension D = K * L with exactly K ones. It is stored compactly as its K block
indices packed in 8-bit lanes of one Python int (lane j = block j's index, 0 <= index < L <= 128).

- bind(x, y)    blockwise (x_j + y_j) mod L   (invertible; unbind(z, y) = (z_j - y_j) mod L)
- rho(x)        block permutation: block j moves to block j+1 (cyclic); used for roles / positions
- onehot(x)     the D-bit sparse vector itself, as an int (bit j*L + x_j)
- bundle        OR of one-hot vectors (superposition with thinning-free OR); membership of a code c in a
                bundle S is tested on all K blocks: onehot(c) & S == onehot(c)
- decode(S)     cleanup: the items of a codebook whose code is fully contained in S. Candidates come from
                the active positions of two key blocks (at most d^2 lookups in a (v0, v1)-keyed table for a
                bundle of d items), each verified on all K blocks. Cost O(d^2 * K), independent of the
                codebook size; errors are spurious items whose K blocks all collide (rate ~ (d/L)^K per
                candidate), measured in benchmarks/g60h_capacity.py.
Every operation costs O(K) word operations, independent of how much is stored.
"""
from __future__ import annotations
import hashlib
import os

K = int(os.environ.get("PACKETLM_HDC_K", "32"))
L = int(os.environ.get("PACKETLM_HDC_L", "64"))
SEED = os.environ.get("PACKETLM_HDC_SEED", "g60h").encode()
assert 2 <= L <= 128 and K >= 2
LANE = 8
FULL = (1 << (K * LANE)) - 1
MASKV = int.from_bytes(bytes([L - 1]) * K, "little") if (L & (L - 1)) == 0 else None
LS = int.from_bytes(bytes([L]) * K, "little")


def lanes(x: int) -> list:
    return list(x.to_bytes(K, "little"))


def pack(vals) -> int:
    return int.from_bytes(bytes(vals), "little")


def code(name: str) -> int:
    """The item's random code: K block indices drawn from a keyed hash of its name (deterministic)."""
    h = hashlib.blake2b(name.encode(), key=SEED, digest_size=max(K, 16)).digest()
    if K > 64:
        h = b"".join(hashlib.blake2b(name.encode() + bytes([i]), key=SEED, digest_size=64).digest() for i in range(K // 64 + 1))
    return pack(b % L for b in h[:K])


def bind(x: int, y: int) -> int:
    if MASKV is not None:  # L a power of two: lanes never carry (each < 128), the mask is mod L
        return (x + y) & MASKV
    return pack((a + b) % L for a, b in zip(lanes(x), lanes(y)))


def unbind(z: int, y: int) -> int:
    if MASKV is not None:
        return (z + LS - y) & MASKV
    return pack((a - b) % L for a, b in zip(lanes(z), lanes(y)))


def rho(x: int, k: int = 1) -> int:
    k %= K
    if not k:
        return x
    s = k * LANE
    return ((x << s) | (x >> (K * LANE - s))) & FULL


def onehot(x: int) -> int:
    out = 0
    for j, v in enumerate(x.to_bytes(K, "little")):
        out |= 1 << (j * L + v)
    return out


def block_bits(S: int, j: int) -> list:
    """Active positions of block j of the bundle S."""
    b = (S >> (j * L)) & ((1 << L) - 1)
    out = []
    while b:
        low = b & -b
        out.append(low.bit_length() - 1)
        b ^= low
    return out


class Codebook:
    """Item memory + cleanup memory for one kind of item (entities, primitives, ...)."""

    def __init__(self):
        self.code = {}     # name -> code
        self.name = {}     # code -> name (exact cleanup for a clean code)
        self.hot = {}      # name -> onehot(code)
        self.key = {}      # (v0, v1) -> [names]  (cleanup of a bundle)
        self.collisions = 0
        self.collided = set()  # codes shared by two or more names (their cleanup is not unique)

    def add(self, nm: str) -> int:
        c = self.code.get(nm)
        if c is not None:
            return c
        c = code(nm)
        if c in self.name:
            self.collisions += 1  # two names with one code: counted; users of the code fall back to exact copies
            self.collided.add(c)
        else:
            self.name[c] = nm
        self.code[nm] = c
        self.hot[nm] = onehot(c)
        v = c.to_bytes(K, "little")
        self.key.setdefault((v[0], v[1]), []).append(nm)
        return c

    def decode(self, S: int, shift: int = 0, stats=None) -> list:
        """Items whose code, permuted by rho^shift, is fully contained in the bundle S."""
        b0, b1 = block_bits(S, shift % K), block_bits(S, (shift + 1) % K)
        out = []
        for v0 in b0:
            for v1 in b1:
                for nm in self.key.get((v0, v1), ()):
                    h = self.hot[nm] if not shift else onehot(rho(self.code[nm], shift))
                    if stats is not None:
                        stats["cleanup_checks"] = stats.get("cleanup_checks", 0) + 1
                    if h & S == h:
                        out.append(nm)
        return out
