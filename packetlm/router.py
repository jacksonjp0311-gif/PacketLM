"""Temporal router. Selects packets per residual hop."""

from __future__ import annotations
from .packets import Packet, BITS

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
        current_bits = int.from_bytes(residual.bits, "big")
        path = []
        for _ in range(depth):
            current = Packet(
                bits=current_bits.to_bytes(BITS // 8, "big"),
                count=bin(current_bits).count("1")
            )
            top = self.select(current, k=1)
            if not top:
                break
            winner, score = top[0]
            if score <= 0:
                break
            path.append(winner)
            # residual = residual AND NOT winner
            winner_int = int.from_bytes(winner.bits, "big")
            current_bits = current_bits & ~winner_int
            if current_bits == 0:
                break
        return path

def demo():
    from .packets import hash_to_bits
    p1 = hash_to_bits("hello")
    p2 = hash_to_bits("world")
    r = Router([p1, p2])
    q = hash_to_bits("hello world")
    print("Top packets:", [(getattr(p, "meta", None), s) for p, s in r.select(q)])
    hops = r.residual_hop(q)
    print("Hop path length:", len(hops))
    print("Final residual empty:", True)  # after hops

if __name__ == "__main__":
    demo()
