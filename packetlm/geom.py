"""G43 start.

A mask of live hypotheses.
Evidence is a mask.
AND must match the list filter.
This is bitwise storage, not a proven geometric advantage.
Not a general mind.
"""

from __future__ import annotations
import json
from pathlib import Path

def mask_of(ids, n):
    m = 0
    for i in ids:
        m |= 1 << i
    return m

def bits(m):
    return [i for i in range(m.bit_length()) if m & (1 << i)]

def filter_list(live, supported, undetermined):
    keep = set(supported) | set(undetermined)
    return [i for i in live if i in keep]

def filter_mask(live_mask, supported_mask, undetermined_mask):
    return live_mask & (supported_mask | undetermined_mask)

def run() -> dict:
    n = 8
    live = list(range(n))
    # evidence: 0,2,4,6 supported; 1 undetermined; rest contradicted
    supported = [0, 2, 4, 6]
    undetermined = [1]
    listed = filter_list(live, supported, undetermined)
    masked = bits(filter_mask(mask_of(live, n), mask_of(supported, n), mask_of(undetermined, n)))
    # second evidence kills 2 and 6, 1 still undetermined
    supported2 = [0, 4]
    listed2 = filter_list(listed, supported2, undetermined)
    masked2 = bits(filter_mask(mask_of(listed, n), mask_of(supported2, n), mask_of(undetermined, n)))
    checks = {
        "same": listed == masked == [0, 1, 2, 4, 6],
        "second": listed2 == masked2 == [0, 1, 4],
        "undetermined_kept": 1 in masked2,
        "contradicted_gone": 3 not in masked and 7 not in masked,
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "masked": masked,
        "masked2": masked2,
        "failed": failed,
        "claim": "bitwise filter matches the list; not a proven geometric advantage"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/geom_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
