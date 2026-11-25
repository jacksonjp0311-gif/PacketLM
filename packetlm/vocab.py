"""Token vocabulary.

Builds a vocabulary of first tokens from the corpus.
Scores prediction by whether the predicted first token matches the target first token.
Counts correct first tokens on a held-out set.
"""

from __future__ import annotations
import json
from pathlib import Path
from .packets import hash_to_bits
from .store import build_from_corpus
from .router import Router
from .train import load_corpus, window_stories
from .nexttoken import split_window, predict_next, first_token

def build_vocab(windows: list[str]) -> list[str]:
    seen = []
    for w in windows:
        _, target = split_window(w)
        tok = first_token(target)
        if tok and tok not in seen:
            seen.append(tok)
    return seen

def run() -> dict:
    raw = load_corpus()
    windows = window_stories(raw)
    if len(windows) < 4:
        windows = windows * 2
    cut = max(1, len(windows) // 3)
    train = windows[:-cut]
    holdout = windows[-cut:]
    vocab = build_vocab(train)
    store = build_from_corpus(train)
    router = Router(store.as_list())
    correct = 0
    n = 0
    details = []
    for w in holdout:
        prompt, target = split_window(w)
        if not target:
            continue
        n += 1
        pred = predict_next(router, prompt, vocab)
        hit = pred == first_token(target)
        if hit:
            correct += 1
        details.append({"target": first_token(target), "pred": pred, "hit": hit})
    receipt = {
        "vocab_size": len(vocab),
        "holdout": n,
        "correct_first_tokens": correct,
        "accuracy": round(correct / max(n, 1), 3),
        "details": details[:8],
        "claim": "first-token prediction against a vocabulary built from training windows; still a proxy"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/vocab_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
