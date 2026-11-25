"""Closed learning loop.

On a training window, predict the next segment.
If wrong, raise the strength of packets that overlap the correct segment.
Receipt records the updates.
"""

from __future__ import annotations
import json
from pathlib import Path
from .packets import hash_to_bits
from .store import build_from_corpus
from .router import Router
from .train import load_corpus, window_stories
from .nexttoken import split_window, predict_next

def run(seed: int = 0) -> dict:
    raw = load_corpus()
    windows = window_stories(raw)
    if len(windows) < 4:
        windows = windows * 2
    cut = max(1, len(windows) // 5)
    train = windows[:-cut]
    store = build_from_corpus(train)
    candidates = [split_window(w)[1] for w in windows if split_window(w)[1]]
    updates = 0
    for w in train:
        prompt, target = split_window(w)
        if not target:
            continue
        router = Router(store.as_list())
        pred = predict_next(router, prompt, candidates)
        if pred == target:
            continue
        # raise packets that cover the correct segment
        target_p = hash_to_bits(target)
        for sp in store.packets:
            if sp.packet.overlap(target_p) > 0:
                store.update_strength(sp.id, 0.05, "correct_segment")
                updates += 1
    store.save("artifacts/packet_store_learned.json")
    receipt = {
        "train_windows": len(train),
        "strength_updates": updates,
        "top": [
            {"id": sp.id, "strength": round(sp.strength, 3), "hits": sp.hits}
            for sp in store.top_by_strength(5)
        ],
        "claim": "strength raised on packets that covered the correct next segment after a miss; still a proxy"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/learn_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
