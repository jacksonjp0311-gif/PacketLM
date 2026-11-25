"""Temporal router. Selects packets per residual hop."""

from __future__ import annotations
from .packets import Packet

class Router:
    def __init__(self, packets: list[Packet]):
        self.packets = packets

    def select(self, residual: Packet, k: int = 4) -> list[tuple[Packet, int]]:
        """Return top-k packets by score against residual."""
        scored = [(p, residual.score(p)) for p in self.packets]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]

    def residual_hop(self, residual: Packet, depth: int = 3) -> list[Packet]:
        """AND-NOT winner bits and re-query. Logs each hop."""
        current = residual
        path = []
        for _ in range(depth):
            top = self.select(current, k=1)
            if not top:
                break
            winner, _ = top[0]
            path.append(winner)
            # residual_bits = residual_bits AND NOT winner_bits  (stub)
            # real implementation will mutate the bit vector
            current = winner  # placeholder
        return path

def demo():
    from .packets import hash_to_bits
    p1 = hash_to_bits("hello")
    p2 = hash_to_bits("world")
    r = Router([p1, p2])
    q = hash_to_bits("hello world")
    print("Top packets:", [(p.meta, s) for p, s in r.select(q)])
    print("Hop path length:", len(r.residual_hop(q)))

if __name__ == "__main__":
    demo()
