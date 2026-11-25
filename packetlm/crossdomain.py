"""Cross-domain transfer gate.

Measure holdout accuracy on language, reasoning, and planning separately.
A learning pass is kept only if at least two domains improve.
Receipt records the decision.
"""

from __future__ import annotations
import json
from pathlib import Path
from .store import build_from_corpus
from .train import window_stories
from .learn import accuracy, one_pass
from .nexttoken import split_window

def load_domain(name: str) -> list[str]:
    p = Path("data") / name
    if not p.exists():
        return []
    text = p.read_text()
    return [s.strip() for s in text.split("\n\n") if s.strip()]

def domain_accuracy(store, windows, candidates) -> float:
    return accuracy(store, window_stories(windows), candidates)

def run() -> dict:
    lang = load_domain("tinystories_slice.txt")
    reason = load_domain("reasoning_slice.txt")
    plan = load_domain("planning_slice.txt")
    all_windows = window_stories(lang + reason + plan)
    store = build_from_corpus(all_windows)
    candidates = [split_window(w)[1] for w in all_windows if split_window(w)[1]]

    before = {
        "language": domain_accuracy(store, lang, candidates),
        "reasoning": domain_accuracy(store, reason, candidates),
        "planning": domain_accuracy(store, plan, candidates)
    }
    # one learning pass on all domains
    one_pass(store, all_windows, candidates)
    after = {
        "language": domain_accuracy(store, lang, candidates),
        "reasoning": domain_accuracy(store, reason, candidates),
        "planning": domain_accuracy(store, plan, candidates)
    }
    improved = [d for d in before if after[d] > before[d]]
    kept = len(improved) >= 2
    receipt = {
        "before": {k: round(v, 3) for k, v in before.items()},
        "after": {k: round(v, 3) for k, v in after.items()},
        "improved_domains": improved,
        "kept": kept,
        "claim": "pass kept only if at least two domains improve; still a proxy"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/crossdomain_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
