"""G59: differential test of `--partitioned` against the G58 engine (docs/G59.md §3).

The G58 protocol (packetlm/g58_diff.py: serve.Server in-process, replies and in-memory state text
compared after every call, final snapshots byte-compared, the audit on), with --indexed
--incremental --routed as the reference and --partitioned added. `dense=True` draws every code
from 128 bit positions instead of 4096 (engine.bits_for patched for the run), so geometric
crosstalk -- packets of unrelated facts passing the recall test -- is common, which real codes
almost never produce; `dense="blocks"` builds every code from 2 of 12 blocks of 8 bits, so such
packets also decode to a name (an unrelated fact changes a recall's answer).
Run: python3 -m packetlm.g59_diff [N_SESSIONS] [SEED] [dense]
"""
from __future__ import annotations
import json
import random
import sys

from . import engine, field
from . import g58_diff

BASE = g58_diff.NEW
NEW = BASE + ["--partitioned"]

# recall crosstalk and growth: many entities over few relations, asks at known and unknown subjects
SCENARIOS = g58_diff.SCENARIOS + [
    [[f"fact e{i} p e{(i * 7) % 23}" for i in range(23)], [f"what is e{i} p" for i in range(0, 23, 3)],
     ["example zz: e1 -> e7", "example zz: e2 -> e14"], ["fact e30 p e1", "what is e30 zz", "what is e31 p"],
     ["retract e1 p e7"], ["what is e1 p", "what is e1 zz"]],
    [g58_diff.CHAIN, g58_diff.ZZ, [f"fact x{i} q y{i}" for i in range(30)], ["what is x3 q", "what is a zz"],
     ["fact a q y3"], ["what is a q", "complete a"], ["what is a q"]],
]


def _dense(tok, role, _c={}):
    k = (tok, role)
    if k not in _c:
        rr = random.Random(f"{tok}/{role}")
        _c[k] = sum(1 << b for b in rr.sample(range(128), 16))
    return _c[k]


def _blocks(tok, role, _c={}):
    """Codes made of 2 of 12 blocks of 8 bits: XORs cancel whole blocks, so packets of unrelated facts
    often differ from q by exactly one name's code (crosstalk that decodes)."""
    k = (tok, role)
    if k not in _c:
        rr = random.Random(f"b{tok}/{role}")
        _c[k] = sum(((1 << 8) - 1) << (8 * b) for b in rr.sample(range(12), 2))
    return _c[k]


def run(n=40, seed=0, dense=False, ref_flags=None, new_flags=None, audit=True) -> dict:
    old_sc = g58_diff.SCENARIOS
    real, realf = engine.bits_for, field.bits_for
    if dense:  # every user of the codes: the engine's index and the query (field.partial)
        engine.bits_for = field.bits_for = _blocks if dense == "blocks" else _dense
    engine._CODE_BITS.clear()
    g58_diff.SCENARIOS = SCENARIOS
    try:
        r = g58_diff.run(n=n, seed=seed, ref_flags=ref_flags or BASE, new_flags=new_flags or NEW, audit=audit)
        r["dense"] = dense
        return r
    finally:
        g58_diff.SCENARIOS = old_sc
        engine.bits_for, field.bits_for = real, realf
        engine._CODE_BITS.clear()


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    print(json.dumps(run(n, seed, dense=len(sys.argv) > 3), indent=1))
