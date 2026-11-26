"""G37.1 qualification.

The score test asserts the tight packet is selected.
It does not accept 'top score is highest' as a pass.
"""

from __future__ import annotations
import json
from pathlib import Path
from .packets import hash_to_bits
from .router import Router
from .bind import bind

def test_score() -> dict:
    tight = hash_to_bits("lily needle")
    wide = hash_to_bits("lily needle river stones dusk night cold shelter traveler")
    query = hash_to_bits("lily needle")
    r = Router([tight, wide])
    top = r.select(query, k=2)
    winner = top[0][0]
    ok = winner is tight
    return {
        "name": "score",
        "ok": ok,
        "winner_is_tight": ok,
        "tight_score": tight.score(query),
        "wide_score": wide.score(query),
    }

def test_bind() -> dict:
    ab = bind("alice", "helps", "bob")
    ba = bind("bob", "helps", "alice")
    ok = ab.bits != ba.bits and ab.hamming(ba) > 0
    return {"name": "bind", "ok": ok, "hamming": ab.hamming(ba)}

def run() -> dict:
    tests = [test_score(), test_bind()]
    failed = [t["name"] for t in tests if not t["ok"]]
    receipt = {
        "tests": tests,
        "failed": failed,
        "passed": len(failed) == 0,
        "claim": "G37.1 asserts the tight packet wins; not a mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/g37_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
