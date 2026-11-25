"""Packet store. Addressable units with strength and provenance.

Packets improve only when they help a sealed probe more than the empty baseline.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from .packets import Packet, hash_to_bits

@dataclass
class StoredPacket:
    id: str
    text: str
    packet: Packet
    strength: float = 1.0
    provenance: str = "corpus"
    hits: int = 0

class PacketStore:
    def __init__(self):
        self.packets: list[StoredPacket] = []

    def add(self, text: str, provenance: str = "corpus") -> StoredPacket:
        p = hash_to_bits(text)
        sp = StoredPacket(
            id=f"p{len(self.packets):04d}",
            text=text[:200],
            packet=p,
            provenance=provenance
        )
        self.packets.append(sp)
        return sp

    def as_list(self) -> list[Packet]:
        return [sp.packet for sp in self.packets]

    def update_strength(self, packet_id: str, delta: float, reason: str) -> None:
        for sp in self.packets:
            if sp.id == packet_id:
                sp.strength = max(0.1, min(10.0, sp.strength + delta))
                sp.hits += 1
                sp.provenance = f"{sp.provenance}|{reason}"
                return

    def top_by_strength(self, k: int = 5) -> list[StoredPacket]:
        return sorted(self.packets, key=lambda x: x.strength, reverse=True)[:k]

    def save(self, path: str = "artifacts/packet_store.json") -> None:
        Path(path).parent.mkdir(exist_ok=True)
        data = [
            {
                "id": sp.id,
                "text": sp.text,
                "strength": sp.strength,
                "provenance": sp.provenance,
                "hits": sp.hits
            }
            for sp in self.packets
        ]
        Path(path).write_text(json.dumps(data, indent=2))

def build_from_corpus(texts: list[str]) -> PacketStore:
    store = PacketStore()
    for t in texts:
        store.add(t, provenance="corpus")
    return store
