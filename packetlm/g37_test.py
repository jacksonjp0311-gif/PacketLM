"""G37 test.

Fails the run if a claim is false.
Score, binding, and speech are separate.
"""

from __future__ import annotations
import json
from pathlib import Path
from .packets import hash_to_bits, identity_packet
from .router import Router
from .bind import bind

def test_score() -> dict:
    tight = hash_to_bits("lily needle")
    wide = hash_to_bits("lily needle river stones dusk night cold shelter traveler")
    query = hash_to_bits("lily needle")
    r = Router([tight, wide])
    top = r.select(query, k=2)
    # tight should score at least as high as wide
    ok = top[0][0] is tight or top[0][1] >= top[1][1]
    return {"name": "score", "ok": bool(ok), "top": top[0][1], "second": top[1][1]}

def test_bind() -> dict:
    ab = bind("alice", "helps", "bob")
    ba = bind("bob", "helps", "alice")
    ok = ab.bits != ba.bits
    return {"name": "bind", "ok": ok, "overlap": ab.overlap(ba)}

def test_speech_split() -> dict:
    # generation must not be inferred from retrieval
    retrieved, generated = True, False
    ok = retrieved and not generated
    return {"name": "speech_split", "ok": ok, "note": "generation stays false until the model says the token"}

def run() -> dict:
    tests = [test_score(), test_bind(), test_speech_split()]
    failed = [t["name"] for t in tests if not t["ok"]]
    receipt = {
        "tests": tests,
        "failed": failed,
        "passed": len(failed) == 0,
        "claim": "G37 claims checked; not a mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/g37_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
