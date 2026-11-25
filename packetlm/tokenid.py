"""Token-identity training.

Each vocabulary token is its own packet.
A prompt is scored by which token packet has the highest overlap with the residual path.
Strength of the correct token packet is raised on a miss.
Holdout first-token accuracy measured before and after.
"""

from __future__ import annotations
import json
from pathlib import Path
from .packets import hash_to_bits
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

def predict_token(store: PacketStore, prompt: str) -> str | None:
    if not store.packets:
        return None
    q = hash_to_bits(prompt)
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

def accuracy(store: PacketStore, windows: list[str]) -> float:
    correct = 0
    n = 0
    for w in windows:
        prompt, target = split_window(w)
        if not target:
            continue
        n += 1
        if predict_token(store, prompt) == first_token(target):
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
    updates = 0
    for w in train:
        prompt, target = split_window(w)
        tok = first_token(target)
        if not tok:
            continue
        pred = predict_token(store, prompt)
        if pred == tok:
            continue
        for sp in store.packets:
            if sp.text == tok:
                store.update_strength(sp.id, 0.1, "token_identity_miss")
                updates += 1
                break
    after = accuracy(store, holdout)
    receipt = {
        "vocab_size": len(store.packets),
        "train": len(train),
        "holdout": len(holdout),
        "accuracy_before": round(before, 3),
        "accuracy_after": round(after, 3),
        "improved": after > before,
        "updates": updates,
        "claim": "token packets trained on identity; first-token accuracy on holdout; still a proxy"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/tokenid_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
