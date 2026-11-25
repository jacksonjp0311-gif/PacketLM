"""Next-token measurement with update.

Predict the next short segment by packet overlap.
On a miss, raise strength of packets that cover the correct segment.
Measure accuracy before and after the update on held-out windows.
"""

from __future__ import annotations
import json
from pathlib import Path
from .packets import hash_to_bits
from .store import build_from_corpus
from .router import Router
from .train import load_corpus, window_stories

def split_window(text: str) -> tuple[str, str]:
    words = text.split()
    if len(words) < 4:
        return text, ""
    cut = max(2, len(words) // 2)
    return " ".join(words[:cut]), " ".join(words[cut:cut+4])

def predict_next(router: Router, prompt: str, candidates: list[str]) -> str | None:
    q = hash_to_bits(prompt)
    union = router.path_union(q)
    if not union:
        return None
    best = None
    best_score = -1
    for c in candidates:
        if not c:
            continue
        ov = union.overlap(hash_to_bits(c))
        if ov > best_score:
            best_score = ov
            best = c
    return best

def accuracy(store, windows, candidates) -> float:
    router = Router(store.as_list())
    correct = 0
    n = 0
    for w in windows:
        prompt, target = split_window(w)
        if not target:
            continue
        n += 1
        if predict_next(router, prompt, candidates) == target:
            correct += 1
    return correct / max(n, 1)

def run(seed: int = 0) -> dict:
    raw = load_corpus()
    windows = window_stories(raw)
    if len(windows) < 4:
        windows = windows * 2
    cut = max(1, len(windows) // 5)
    train = windows[:-cut]
    holdout = windows[-cut:]
    store = build_from_corpus(train)
    candidates = [split_window(w)[1] for w in windows if split_window(w)[1]]
    before = accuracy(store, holdout, candidates)
    updates = 0
    for w in train:
        prompt, target = split_window(w)
        if not target:
            continue
        router = Router(store.as_list())
        pred = predict_next(router, prompt, candidates)
        if pred == target:
            continue
        target_p = hash_to_bits(target)
        for sp in store.packets:
            if sp.packet.overlap(target_p) > 0:
                store.update_strength(sp.id, 0.05, "nexttoken_miss")
                updates += 1
    after = accuracy(store, holdout, candidates)
    receipt = {
        "train_windows": len(train),
        "holdout": len(holdout),
        "accuracy_before": round(before, 3),
        "accuracy_after": round(after, 3),
        "improved": after > before,
        "updates": updates,
        "claim": "strength updated from next-segment misses; holdout measured before and after; still a proxy"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/nexttoken_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
