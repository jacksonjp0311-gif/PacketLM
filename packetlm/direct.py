"""Direct token lookup with nearest-prompt generalization.

Exact match first. If the prompt is unseen, pick the training prompt
that shares the most tokens and use its first-token label.
Measures exact and nearest accuracy on holdout.
"""

from __future__ import annotations
import json
from pathlib import Path
from .train import load_corpus, window_stories
from .nexttoken import split_window, first_token

def tokens(text: str) -> set[str]:
    return {t for t in text.lower().split() if t}

def nearest(prompt: str, table: dict[str, str]) -> str | None:
    if prompt in table:
        return table[prompt]
    q = tokens(prompt)
    if not q:
        return None
    best = None
    best_score = 0
    for p, tok in table.items():
        score = len(q & tokens(p))
        if score > best_score:
            best_score = score
            best = tok
    return best

def run() -> dict:
    raw = load_corpus()
    windows = window_stories(raw)
    if len(windows) < 4:
        windows = windows * 2
    cut = max(1, len(windows) // 3)
    train = windows[:-cut]
    holdout = windows[-cut:]

    table = {}
    for w in train:
        prompt, target = split_window(w)
        tok = first_token(target)
        if prompt and tok:
            table[prompt] = tok

    exact = 0
    near = 0
    n = 0
    for w in holdout:
        prompt, target = split_window(w)
        if not target:
            continue
        n += 1
        if table.get(prompt) == first_token(target):
            exact += 1
        if nearest(prompt, table) == first_token(target):
            near += 1

    receipt = {
        "train": len(train),
        "holdout": n,
        "table_size": len(table),
        "exact_accuracy": round(exact / max(n, 1), 3),
        "nearest_accuracy": round(near / max(n, 1), 3),
        "generalized": near > exact,
        "claim": "exact map plus nearest-prompt by shared tokens; still a proxy, not a language model"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/direct_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
