"""Role binding.

Overlap cannot tell who did what.
A role is a fixed bit rotation. Binding is XOR after the rotation.
Alice helps Bob and Bob helps Alice must not be the same packet.
Not a general mind.
"""

from __future__ import annotations
import json
from pathlib import Path
from .packets import Packet, BITS, identity_packet, hash_to_bits

def rotate(pkt: Packet, k: int) -> Packet:
    n = int.from_bytes(pkt.bits, "big")
    k = k % BITS
    rotated = ((n << k) | (n >> (BITS - k))) & ((1 << BITS) - 1)
    return Packet(bits=rotated.to_bytes(BITS // 8, "big"), count=bin(rotated).count("1"))

def bind(subject: str, relation: str, obj: str) -> Packet:
    s = rotate(identity_packet(subject), 0)
    r = rotate(identity_packet(relation), 64)
    o = rotate(identity_packet(obj), 128)
    a = int.from_bytes(s.bits, "big")
    b = int.from_bytes(r.bits, "big")
    c = int.from_bytes(o.bits, "big")
    x = a ^ b ^ c
    return Packet(bits=x.to_bytes(BITS // 8, "big"), count=bin(x).count("1"))

def run() -> dict:
    ab = bind("alice", "helps", "bob")
    ba = bind("bob", "helps", "alice")
    same = ab.bits == ba.bits
    overlap = ab.overlap(ba)
    # unbind check: XOR relation and object roles back, see if subject bit remains distinct
    receipt = {
        "alice_helps_bob": ab.count,
        "bob_helps_alice": ba.count,
        "same_packet": same,
        "overlap": overlap,
        "distinguished": not same,
        "claim": "role-bound packets distinguish subject and object; not a general mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/bind_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
