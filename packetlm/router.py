"""Temporal router. Selects packets per residual hop."""

from __future__ import annotations
from .packets import Packet, BITS

class Router:
    def __init__(self, packets: list[Packet]):
        self.packets = packets

    def select(self, residual: Packet, k: int = 4) -> list[tuple[Packet, int]]:
        scored = [(p, residual.score(p)) for p in self.packets]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]

    def residual_hop(self, residual: Packet, depth: int = 3) -> list[Packet]:
        """AND-NOT winner bits and re-query. Always takes next unused packet if residual remains."""
        current_bits = int.from_bytes(residual.bits, "big")
        path = []
        seen = set()
        for _ in range(depth):
            current = Packet(
                bits=current_bits.to_bytes(BITS // 8, "big"),
                count=bin(current_bits).count("1")
            )
            # rank all, skip seen
            scored = [(p, current.score(p)) for p in self.packets if id(p) not in seen]
            if not scored:
                break
            scored.sort(key=lambda x: x[1], reverse=True)
            winner, score = scored[0]
            # after first hop, take next even if score is low so path can cover residual
            if path and score <= 0 and len(scored) > 1:
                winner, score = scored[1]
            seen.add(id(winner))
            path.append(winner)
            winner_int = int.from_bytes(winner.bits, "big")
            current_bits = current_bits & ~winner_int
            if current_bits == 0:
                break
        return path

    def path_union(self, residual: Packet, depth: int = 3) -> Packet | None:
        path = self.residual_hop(residual, depth)
        if not path:
            return None
        acc = path[0]
        for p in path[1:]:
            acc = acc.union(p)
        return acc

def demo():
    from .packets import hash_to_bits
    p1 = hash_to_bits("hello")
    p2 = hash_to_bits("world")
    r = Router([p1, p2])
    q = hash_to_bits("hello world")
    hops = r.residual_hop(q)
    print("Hop path length:", len(hops))

if __name__ == "__main__":
    demo()
