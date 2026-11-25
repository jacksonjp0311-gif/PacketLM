"""Next-token measurement.

Given a window, predict the next short segment by packet overlap.
Measure accuracy on held-out windows. First real learning signal.
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
    best = None
    best_score = -1
    for c in candidates:
        if not c:
            continue
        ov = router.path_union(q).overlap(hash_to_bits(c)) if router.path_union(q) else 0
        if ov > best_score:
            best_score = ov
            best = c
    return best

def run(seed: int = 0) -> dict:
    raw = load_corpus()
    windows = window_stories(raw)
    if len(windows) < 4:
        windows = windows * 2
    cut = max(1, len(windows) // 5)
    train = windows[:-cut]
    holdout = windows[-cut:]
    store = build_from_corpus(train)
    router = Router(store.as_list())
    candidates = [split_window(w)[1] for w in windows if split_window(w)[1]]
    correct = 0
    details = []
    for w in holdout:
        prompt, target = split_window(w)
        if not target:
            continue
        pred = predict_next(router, prompt, candidates)
        hit = pred == target
        if hit:
            correct += 1
        details.append({"prompt": prompt[:60], "target": target, "pred": pred, "hit": hit})
    n = len(details) or 1
    receipt = {
        "train_windows": len(train),
        "holdout": len(details),
        "correct": correct,
        "accuracy": correct / n,
        "details": details[:5],
        "claim": "next-segment prediction by packet overlap on held-out windows; still a proxy"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/nexttoken_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
