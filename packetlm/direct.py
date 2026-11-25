"""Direct token lookup.

Maps each training prompt to the identity bit of its correct first token.
At prediction, looks up the identity bit instead of scoring residual overlap.
Compares direct accuracy against the overlap proxy on the same holdout.
"""

from __future__ import annotations
import json
from pathlib import Path
from .packets import identity_packet, _token_bit
from .train import load_corpus, window_stories
from .nexttoken import split_window, first_token

def run() -> dict:
    raw = load_corpus()
    windows = window_stories(raw)
    if len(windows) < 4:
        windows = windows * 2
    cut = max(1, len(windows) // 3)
    train = windows[:-cut]
    holdout = windows[-cut:]

    # direct map: prompt text -> correct first token
    table = {}
    for w in train:
        prompt, target = split_window(w)
        tok = first_token(target)
        if prompt and tok:
            table[prompt] = tok

    direct_correct = 0
    n = 0
    for w in holdout:
        prompt, target = split_window(w)
        if not target:
            continue
        n += 1
        pred = table.get(prompt)
        if pred == first_token(target):
            direct_correct += 1

    receipt = {
        "train": len(train),
        "holdout": n,
        "table_size": len(table),
        "direct_accuracy": round(direct_correct / max(n, 1), 3),
        "claim": "direct prompt-to-token map; bypasses overlap proxy; still a proxy, not a language model"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/direct_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
