"""Temporal router. Selects packets per residual hop.

Score is p.score(residual) = 2*|q ∩ p| - |p|.
That is the Bitwork identity. Larger packets are not favored.
"""

from __future__ import annotations
from .packets import Packet, BITS

class Router:
    def __init__(self, packets: list[Packet]):
        self.packets = packets

    def select(self, residual: Packet, k: int = 4) -> list[tuple[Packet, int]]:
        scored = [(p, p.score(residual)) for p in self.packets]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]

    def residual_hop(self, residual: Packet, depth: int = 3) -> list[Packet]:
        current_bits = int.from_bytes(residual.bits, "big")
        path = []
        seen = set()
        for _ in range(depth):
            current = Packet(
                bits=current_bits.to_bytes(BITS // 8, "big"),
                count=bin(current_bits).count("1")
            )
            scored = [(p, p.score(current)) for p in self.packets if id(p) not in seen]
            if not scored:
                break
            scored.sort(key=lambda x: x[1], reverse=True)
            winner, score = scored[0]
            if score <= 0:
                break
            seen.add(id(winner))
            path.append(winner)
            winner_int = int.from_bytes(winner.bits, "big")
            current_bits = current_bits & ~winner_int
            if current_bits == 0:
                break
        return path

    def path_union(self, residual: Packet, depth: int = 3) -> Packet | None:
        """Union of the residual-hop path. Restored: removed in 6a345a5 while
        gap, memory, demo, train, nexttoken, learn, vocab, crossdomain,
        feedoffer and gaptest still call it."""
        path = self.residual_hop(residual, depth)
        if not path:
            return None
        acc = path[0]
        for p in path[1:]:
            acc = acc.union(p)
        return acc

if __name__ == "__main__":
    from .packets import hash_to_bits
    a = hash_to_bits("lily needle")
    b = hash_to_bits("the river is cold and has many stones at dusk before night")
    q = hash_to_bits("lily needle")
    r = Router([a, b])
    top = r.select(q, k=2)
    print("top", top[0][1], "vs", top[1][1])
