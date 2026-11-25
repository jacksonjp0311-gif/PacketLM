"""Token-identity with residual injection.

Each vocabulary token is its own packet.
On a miss, the correct token packet is added to the residual path.
The next prediction uses the injected residual.
Holdout first-token accuracy measured before and after injection.
"""

from __future__ import annotations
import json
from pathlib import Path
from .packets import hash_to_bits, Packet, BITS
from .store import PacketStore
from .router import Router
from .train import load_corpus, window_stories
from .nexttoken import split_window, first_token

def build_token_store(windows: list[str]) -> PacketStore:
    store = PacketStore()
    seen = set()
    for w in windows:
        _, target = split_window(w)
        tok = first_token(target)
        if tok and tok not in seen:
            store.add(tok, provenance="token_identity")
            seen.add(tok)
    return store

def predict_token(store: PacketStore, prompt: str, residual: Packet | None = None) -> str | None:
    if not store.packets:
        return None
    q = hash_to_bits(prompt)
    if residual:
        qi = int.from_bytes(q.bits, "big") | int.from_bytes(residual.bits, "big")
        q = Packet(bits=qi.to_bytes(BITS // 8, "big"), count=bin(qi).count("1"))
    router = Router(store.as_list())
    union = router.path_union(q)
    if not union:
        return None
    best = None
    best_ov = -1
    for sp in store.packets:
        ov = union.overlap(sp.packet)
        if ov > best_ov:
            best_ov = ov
            best = sp.text
    return best

def accuracy(store: PacketStore, windows: list[str], residual: Packet | None = None) -> float:
    correct = 0
    n = 0
    for w in windows:
        prompt, target = split_window(w)
        if not target:
            continue
        n += 1
        if predict_token(store, prompt, residual) == first_token(target):
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
    before = accuracy(store, holdout)
    # inject correct tokens that were missed into a residual
    residual_bits = 0
    injected = 0
    for w in train:
        prompt, target = split_window(w)
        tok = first_token(target)
        if not tok:
            continue
        if predict_token(store, prompt) != tok:
            for sp in store.packets:
                if sp.text == tok:
                    residual_bits |= int.from_bytes(sp.packet.bits, "big")
                    injected += 1
                    break
    residual = Packet(
        bits=residual_bits.to_bytes(BITS // 8, "big"),
        count=bin(residual_bits).count("1")
    ) if residual_bits else None
    after = accuracy(store, holdout, residual)
    receipt = {
        "vocab_size": len(store.packets),
        "train": len(train),
        "holdout": len(holdout),
        "accuracy_before": round(before, 3),
        "accuracy_after": round(after, 3),
        "improved": after > before,
        "injected": injected,
        "claim": "correct token packet added to residual on miss; holdout measured with injected residual; still a proxy"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/tokenid_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
