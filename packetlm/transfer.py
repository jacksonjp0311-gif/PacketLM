"""Transfer test.

A prompt that does not appear in the corpus.
Measure whether the store can still cover the expected answer better than an empty store.
"""

from __future__ import annotations
import json
from pathlib import Path
from .packets import hash_to_bits
from .store import build_from_corpus, PacketStore
from .router import Router
from .train import load_corpus, window_stories

def run() -> dict:
    raw = load_corpus()
    windows = window_stories(raw)
    store = build_from_corpus(windows)
    cold = PacketStore()

    # novel prompt not present in the slice files
    prompt = "A traveler needed shelter before night. What should they do first?"
    expected = "find shelter"
    q = hash_to_bits(prompt)
    exp = hash_to_bits(expected)

    def cover(s):
        if not s.packets:
            return 0
        router = Router(s.as_list())
        scored = router.select(q, k=1)
        return scored[0][0].overlap(exp) if scored else 0

    field = cover(store)
    empty = cover(cold)
    receipt = {
        "prompt": prompt,
        "expected": expected,
        "field_overlap": field,
        "cold_overlap": empty,
        "transferred": field > empty,
        "claim": "novel prompt not in corpus; field vs cold overlap; still a proxy"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/transfer_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
