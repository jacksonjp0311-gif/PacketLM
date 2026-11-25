"""Next-token measurement with update.

Larger holdout. Predicts the next segment and scores the first token separately.
On a miss, raise strength of packets that cover the correct first token.
Measure segment and first-token accuracy before and after.
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

def first_token(s: str) -> str:
    return s.split()[0] if s else ""

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

def accuracy(store, windows, candidates) -> tuple[float, float]:
    router = Router(store.as_list())
    seg = 0
    tok = 0
    n = 0
    for w in windows:
        prompt, target = split_window(w)
        if not target:
            continue
        n += 1
        pred = predict_next(router, prompt, candidates)
        if pred == target:
            seg += 1
        if pred and first_token(pred) == first_token(target):
            tok += 1
    n = max(n, 1)
    return seg / n, tok / n

def run(seed: int = 0) -> dict:
    raw = load_corpus()
    windows = window_stories(raw)
    if len(windows) < 4:
        windows = windows * 2
    cut = max(1, len(windows) // 3)
    train = windows[:-cut]
    holdout = windows[-cut:]
    store = build_from_corpus(train)
    candidates = [split_window(w)[1] for w in windows if split_window(w)[1]]
    seg_b, tok_b = accuracy(store, holdout, candidates)
    updates = 0
    for w in train:
        prompt, target = split_window(w)
        if not target:
            continue
        router = Router(store.as_list())
        pred = predict_next(router, prompt, candidates)
        if pred and first_token(pred) == first_token(target):
            continue
        target_p = hash_to_bits(first_token(target))
        for sp in store.packets:
            if sp.packet.overlap(target_p) > 0:
                store.update_strength(sp.id, 0.05, "first_token_miss")
                updates += 1
    seg_a, tok_a = accuracy(store, holdout, candidates)
    receipt = {
        "train_windows": len(train),
        "holdout": len(holdout),
        "segment_before": round(seg_b, 3),
        "segment_after": round(seg_a, 3),
        "first_token_before": round(tok_b, 3),
        "first_token_after": round(tok_a, 3),
        "segment_improved": seg_a > seg_b,
        "first_token_improved": tok_a > tok_b,
        "updates": updates,
        "claim": "larger holdout; strength updated from first-token misses; still a proxy"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/nexttoken_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
