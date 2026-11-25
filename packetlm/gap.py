"""Gap proposal.

After a residual is built, propose a new packet from the uncovered bits of a holdout window.
Keep the proposal only if it overlaps the residual gap and reduces the uncovered count.
Receipt records the proposal and the decision. Returns the last kept text.
"""

from __future__ import annotations
import json
from pathlib import Path
from .packets import Packet, BITS, hash_to_bits
from .store import build_from_corpus
from .memory import ResidualMemory
from .router import Router
from .train import load_corpus, window_stories

def propose_from_gap(memory: ResidualMemory, text: str) -> Packet | None:
    p = hash_to_bits(text)
    gap = int.from_bytes(p.bits, "big") & ~memory.covered
    if gap == 0:
        return None
    return Packet(bits=gap.to_bytes(BITS // 8, "big"), count=bin(gap).count("1"))

def run() -> dict:
    raw = load_corpus()
    windows = window_stories(raw)
    store = build_from_corpus(windows)
    router = Router(store.as_list())
    mem = ResidualMemory()

    for w in windows[:5]:
        q = hash_to_bits(w)
        union = router.path_union(q, depth=3)
        if union:
            mem.absorb(union)

    before = mem.covered_count()
    proposals = 0
    kept = 0
    last_kept = None
    for w in windows[5:10]:
        prop = propose_from_gap(mem, w)
        if prop is None:
            continue
        proposals += 1
        new_covered = mem.covered | int.from_bytes(prop.bits, "big")
        if bin(new_covered).count("1") > before:
            store.add(w, provenance="gap_proposal")
            mem.covered = new_covered
            kept += 1
            before = bin(new_covered).count("1")
            last_kept = w[:200]

    receipt = {
        "proposals": proposals,
        "kept": kept,
        "last_kept": last_kept,
        "final_covered_bits": mem.covered_count(),
        "store_size": len(store.packets),
        "claim": "new packets proposed from residual gaps and kept only if they cover previously uncovered bits; still a proxy"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/gap_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
