"""Iterative learning loop with stronger signal.

Multiple passes. Packets that cover the correct next segment gain strength.
Packets that were selected but missed lose a small amount.
Holdout accuracy tracked per pass.
"""

from __future__ import annotations
import json
from pathlib import Path
from .packets import hash_to_bits
from .store import build_from_corpus
from .router import Router
from .train import load_corpus, window_stories
from .nexttoken import split_window, predict_next

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

def one_pass(store, windows, candidates) -> int:
    updates = 0
    for w in windows:
        prompt, target = split_window(w)
        if not target:
            continue
        router = Router(store.as_list())
        pred = predict_next(router, prompt, candidates)
        target_p = hash_to_bits(target)
        if pred == target:
            # reinforce packets that cover the correct segment
            for sp in store.packets:
                if sp.packet.overlap(target_p) > 0:
                    store.update_strength(sp.id, 0.08, "correct")
                    updates += 1
        else:
            # small penalty on packets that overlapped the wrong prediction
            if pred:
                pred_p = hash_to_bits(pred)
                for sp in store.packets:
                    if sp.packet.overlap(pred_p) > 0 and sp.packet.overlap(target_p) == 0:
                        store.update_strength(sp.id, -0.02, "miss")
                        updates += 1
            # still reinforce correct cover
            for sp in store.packets:
                if sp.packet.overlap(target_p) > 0:
                    store.update_strength(sp.id, 0.04, "correct_after_miss")
                    updates += 1
    return updates

def run(seed: int = 0, passes: int = 3) -> dict:
    raw = load_corpus()
    windows = window_stories(raw)
    if len(windows) < 4:
        windows = windows * 2
    cut = max(1, len(windows) // 5)
    train = windows[:-cut]
    holdout = windows[-cut:]
    store = build_from_corpus(train)
    candidates = [split_window(w)[1] for w in windows if split_window(w)[1]]
    history = []
    total_updates = 0
    for i in range(passes):
        before = accuracy(store, holdout, candidates)
        updates = one_pass(store, train, candidates)
        after = accuracy(store, holdout, candidates)
        total_updates += updates
        history.append({
            "pass": i + 1,
            "holdout_before": round(before, 3),
            "holdout_after": round(after, 3),
            "updates": updates,
            "improved": after > before
        })
    store.save("artifacts/packet_store_learned.json")
    receipt = {
        "passes": passes,
        "train_windows": len(train),
        "holdout": len(holdout),
        "total_updates": total_updates,
        "history": history,
        "any_improved": any(h["improved"] for h in history),
        "top": [
            {"id": sp.id, "strength": round(sp.strength, 3), "hits": sp.hits}
            for sp in store.top_by_strength(5)
        ],
        "claim": "gain on correct cover, small loss on miss; holdout tracked; still a proxy"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/learn_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
