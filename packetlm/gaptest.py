"""Gap packet capability test.

Measure a sealed probe on the base store and on the store after a kept gap packet.
Record whether the gap packet improved a probe the base store missed.
"""

from __future__ import annotations
import json
from pathlib import Path
from .packets import hash_to_bits
from .store import build_from_corpus
from .router import Router
from .train import load_corpus, window_stories, load_probes
from .gap import run as gap_run

def probe_hit(store, probe) -> bool:
    if not store.packets:
        return False
    q = hash_to_bits(probe["prompt"])
    exp = hash_to_bits(probe["expected"])
    router = Router(store.as_list())
    scored = router.select(q, k=1)
    if not scored:
        return False
    return scored[0][0].overlap(exp) > 0

def run() -> dict:
    raw = load_corpus()
    windows = window_stories(raw)
    base = build_from_corpus(windows)
    probes = load_probes()
    base_hits = {p["id"]: probe_hit(base, p) for p in probes}

    gap = gap_run()
    improved = []
    if gap.get("last_kept"):
        base.add(gap["last_kept"], provenance="gap_proposal")
        for p in probes:
            after = probe_hit(base, p)
            if after and not base_hits.get(p["id"]):
                improved.append(p["id"])

    receipt = {
        "base_hits": base_hits,
        "probes_improved_by_gap": improved,
        "any_new_capability": len(improved) > 0,
        "gap_kept": gap.get("kept", 0),
        "claim": "gap packet tested for new sealed-probe hits the base store missed; still a proxy"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/gaptest_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
