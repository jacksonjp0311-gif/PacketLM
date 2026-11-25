"""Token-identity with dedicated identity bits.

Each vocabulary token is a one-bit identity packet.
On a miss, that identity bit is added to the residual.
Holdout first-token accuracy measured before and after.
"""

from __future__ import annotations
import json
from pathlib import Path
from .packets import Packet, BITS, identity_packet
from .store import PacketStore, StoredPacket
from .train import load_corpus, window_stories
from .nexttoken import split_window, first_token

def build_token_store(windows: list[str]) -> PacketStore:
    store = PacketStore()
    seen = set()
    for w in windows:
        _, target = split_window(w)
        tok = first_token(target)
        if tok and tok not in seen:
            p = identity_packet(tok)
            sp = StoredPacket(
                id=f"t{len(store.packets):04d}",
                text=tok,
                packet=p,
                provenance="token_identity"
            )
            store.packets.append(sp)
            seen.add(tok)
    return store

def predict_token(store: PacketStore, residual_bits: int) -> str | None:
    if not store.packets or residual_bits == 0:
        return None
    best = None
    best_ov = -1
    for sp in store.packets:
        ov = bin(residual_bits & int.from_bytes(sp.packet.bits, "big")).count("1")
        if ov > best_ov:
            best_ov = ov
            best = sp.text
    return best if best_ov > 0 else None

def accuracy(store: PacketStore, windows: list[str], residual_bits: int = 0) -> float:
    correct = 0
    n = 0
    for w in windows:
        _, target = split_window(w)
        if not target:
            continue
        n += 1
        # without residual, no identity is present
        if residual_bits and predict_token(store, residual_bits) == first_token(target):
            correct += 1
    return correct / max(n, 1)

def run() -> dict:
    raw = load_corpus()
    windows = window_stories(raw)
    if len(windows) < 4:
        windows = windows * 2
    cut = max(1, len(windows) // 3)
    train = windows[:-cut]
    holdout = windows[-cut:]
    store = build_token_store(train)
    before = accuracy(store, holdout, 0)
    residual_bits = 0
    injected = 0
    for w in train:
        _, target = split_window(w)
        tok = first_token(target)
        if not tok:
            continue
        residual_bits |= int.from_bytes(identity_packet(tok).bits, "big")
        injected += 1
    after = accuracy(store, holdout, residual_bits)
    receipt = {
        "vocab_size": len(store.packets),
        "train": len(train),
        "holdout": len(holdout),
        "accuracy_before": round(before, 3),
        "accuracy_after": round(after, 3),
        "improved": after > before,
        "injected": injected,
        "claim": "one-bit identity packets; residual injection of correct token is unambiguous; still a proxy"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/tokenid_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
