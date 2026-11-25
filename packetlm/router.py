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
        """AND-NOT winner bits and re-query. Keeps pulling until depth or residual empty."""
        current_bits = int.from_bytes(residual.bits, "big")
        path = []
        seen = set()
        for _ in range(depth):
            current = Packet(
                bits=current_bits.to_bytes(BITS // 8, "big"),
                count=bin(current_bits).count("1")
            )
            top = self.select(current, k=4)
            if not top:
                break
            added = False
            for winner, score in top:
                wid = id(winner)
                if wid in seen:
                    continue
                # allow zero or negative after first hop so we keep covering residual
                if score <= 0 and path:
                    continue
                seen.add(wid)
                path.append(winner)
                winner_int = int.from_bytes(winner.bits, "big")
                current_bits = current_bits & ~winner_int
                added = True
                break
            if not added or current_bits == 0:
                break
        return path

    def path_union(self, residual: Packet, depth: int = 3) -> Packet | None:
        """Union of packets collected by residual hop. Stronger cover."""
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
    print("Top packets:", [(getattr(p, "meta", None), s) for p, s in r.select(q)])
    hops = r.residual_hop(q)
    print("Hop path length:", len(hops))
    u = r.path_union(q)
    print("Union count:", u.count if u else 0)

if __name__ == "__main__":
    demo()
