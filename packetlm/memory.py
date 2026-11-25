"""Persistent residual memory.

Accumulates covered bits across turns.
The next selection excludes what was already covered and scores against the residual.
Receipt records what was retained and what was excluded.
"""

from __future__ import annotations
import json
from pathlib import Path
from .packets import Packet, BITS, hash_to_bits
from .router import Router
from .train import load_corpus, window_stories

class ResidualMemory:
    def __init__(self):
        self.covered = 0  # integer bit mask of what has been covered
        self.turns = 0

    def absorb(self, packet: Packet) -> None:
        self.covered |= int.from_bytes(packet.bits, "big")
        self.turns += 1

    def residual_query(self, query: Packet) -> Packet:
        """Query with already-covered bits removed."""
        q = int.from_bytes(query.bits, "big")
        residual = q & ~self.covered
        return Packet(
            bits=residual.to_bytes(BITS // 8, "big"),
            count=bin(residual).count("1")
        )

    def covered_count(self) -> int:
        return bin(self.covered).count("1")

def run() -> dict:
    raw = load_corpus()
    corpus = window_stories(raw)
    packets = [hash_to_bits(s) for s in corpus]
    router = Router(packets)
    mem = ResidualMemory()

    # turn 1: no memory
    q1 = hash_to_bits("Lily thanked her mom. How did they both feel?")
    path1 = router.residual_hop(q1, depth=3)
    union1 = router.path_union(q1, depth=3)
    if union1:
        mem.absorb(union1)

    # turn 2: residual query excludes covered
    q2 = hash_to_bits("What did they do next?")
    residual_q = mem.residual_query(q2)
    path2 = router.residual_hop(residual_q, depth=3)
    union2 = router.path_union(residual_q, depth=3)

    # measure difference: did memory change the path
    path2_no_mem = router.residual_hop(q2, depth=3)
    changed = [p for p in path2 if p not in path2_no_mem] or (len(path2) != len(path2_no_mem))

    receipt = {
        "turn1_hops": len(path1),
        "covered_bits": mem.covered_count(),
        "turn2_hops_with_memory": len(path2),
        "turn2_hops_without_memory": len(path2_no_mem),
        "path_changed": bool(changed),
        "claim": "persistent residual excludes covered bits on the next query; path change measured; still a proxy"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/memory_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
