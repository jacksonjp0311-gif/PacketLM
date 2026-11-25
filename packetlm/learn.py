"""Iterative learning loop with cross-domain gate.

Multiple passes. Packets gain on correct cover and lose a little on miss.
A pass is kept only if at least two domains improve.
Holdout accuracy tracked per pass and per domain.
"""

from __future__ import annotations
import json
from pathlib import Path
from .packets import hash_to_bits
from .store import build_from_corpus, PacketStore
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
            for sp in store.packets:
                if sp.packet.overlap(target_p) > 0:
                    store.update_strength(sp.id, 0.08, "correct")
                    updates += 1
        else:
            if pred:
                pred_p = hash_to_bits(pred)
                for sp in store.packets:
                    if sp.packet.overlap(pred_p) > 0 and sp.packet.overlap(target_p) == 0:
                        store.update_strength(sp.id, -0.02, "miss")
                        updates += 1
            for sp in store.packets:
                if sp.packet.overlap(target_p) > 0:
                    store.update_strength(sp.id, 0.04, "correct_after_miss")
                    updates += 1
    return updates

def domain_scores(store, domains, candidates) -> dict:
    return {name: round(accuracy(store, windows, candidates), 3) for name, windows in domains.items()}

def run(seed: int = 0, passes: int = 3) -> dict:
    raw = load_corpus()
    windows = window_stories(raw)
    if len(windows) < 4:
        windows = windows * 2
    # split by domain if possible
    domains = {}
    for name, file in (("language", "tinystories_slice.txt"), ("reasoning", "reasoning_slice.txt"), ("planning", "planning_slice.txt")):
        p = Path("data") / file
        if p.exists():
            text = p.read_text()
            domains[name] = window_stories([s.strip() for s in text.split("\n\n") if s.strip()])
    if not domains:
        domains = {"all": windows}
    cut = max(1, len(windows) // 5)
    train = windows[:-cut]
    store = build_from_corpus(train)
    candidates = [split_window(w)[1] for w in windows if split_window(w)[1]]
    history = []
    kept_passes = 0
    for i in range(passes):
        before = domain_scores(store, domains, candidates)
        # snapshot strengths
        snapshot = [(sp.id, sp.strength) for sp in store.packets]
        one_pass(store, train, candidates)
        after = domain_scores(store, domains, candidates)
        improved = [d for d in before if after[d] > before[d]]
        keep = len(improved) >= 2
        if keep:
            kept_passes += 1
        else:
            # revert strengths
            for sp, (sid, strength) in zip(store.packets, snapshot):
                if sp.id == sid:
                    sp.strength = strength
        history.append({
            "pass": i + 1,
            "before": before,
            "after": after,
            "improved_domains": improved,
            "kept": keep
        })
    store.save("artifacts/packet_store_learned.json")
    receipt = {
        "passes": passes,
        "kept_passes": kept_passes,
        "history": history,
        "any_kept": kept_passes > 0,
        "top": [
            {"id": sp.id, "strength": round(sp.strength, 3), "hits": sp.hits}
            for sp in store.top_by_strength(5)
        ],
        "claim": "pass kept only if at least two domains improve; otherwise strengths reverted; still a proxy"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/learn_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
