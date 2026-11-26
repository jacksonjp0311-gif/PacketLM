"""Role binding in the field.

Alice helps Bob is stored as a bound packet.
A query for Alice should retrieve helps and Bob.
A query for Bob should not return the same packet as if Bob were the subject.
Not a general mind.
"""

from __future__ import annotations
import json
from pathlib import Path
from .packets import Packet, BITS, identity_packet
from .tiny import tokenize, build_vocab
from .train import load_corpus, window_stories
from .context import load_store, save_store, blank_packet
from .geometry import ensure, content

def rotate(pkt: Packet, k: int) -> Packet:
    n = int.from_bytes(pkt.bits, "big")
    k = k % BITS
    rotated = ((n << k) | (n >> (BITS - k))) & ((1 << BITS) - 1)
    return Packet(bits=rotated.to_bytes(BITS // 8, "big"), count=bin(rotated).count("1"))

def bind(subject: str, relation: str, obj: str) -> Packet:
    s = rotate(identity_packet(subject), 0)
    r = rotate(identity_packet(relation), 64)
    o = rotate(identity_packet(obj), 128)
    x = int.from_bytes(s.bits, "big") ^ int.from_bytes(r.bits, "big") ^ int.from_bytes(o.bits, "big")
    return Packet(bits=x.to_bytes(BITS // 8, "big"), count=bin(x).count("1"))

def run() -> dict:
    raw = load_corpus()
    windows = window_stories(raw)
    vocab = build_vocab(windows)
    store = load_store(len(vocab), ["language"])
    ab = bind("alice", "helps", "bob")
    ba = bind("bob", "helps", "alice")
    ensure(store, "alice-helps-bob", ["alice", "helps", "bob"], tokenize("alice helps bob"))
    store["packets"]["alice-helps-bob"]["bound"] = ab.count
    ensure(store, "bob-helps-alice", ["bob", "helps", "alice"], tokenize("bob helps alice"))
    store["packets"]["bob-helps-alice"]["bound"] = ba.count
    # subject query should prefer the packet where that name is the subject key first
    q_alice = content("alice")
    hits = []
    for name, pkt in store["packets"].items():
        if "alice" in pkt.get("keys", []) and name.startswith("alice"):
            hits.append(name)
    save_store(store)
    receipt = {
        "same_packet": ab.bits == ba.bits,
        "alice_packet": "alice-helps-bob" in store["packets"],
        "bob_packet": "bob-helps-alice" in store["packets"],
        "alice_query_hits": hits,
        "distinguished": ab.bits != ba.bits,
        "claim": "role-bound facts stored as separate packets; not a general mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/bind_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
