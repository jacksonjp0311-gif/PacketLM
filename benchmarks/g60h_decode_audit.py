"""G60H post-run audit (not registered, untimed): in-run capability decode counters of the gate arms.
The registered harness kept only g46's per-task cost keys, so the HDC decode counters of the gate runs
were not in the receipts. The engine is deterministic, so this replays the registered jobs (same seeds,
same code) and records each arm's final cumulative counters (decodes, decode_errors).
Run: python3 benchmarks/g60h_decode_audit.py <margin> <out.json>"""
from __future__ import annotations
import json
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT))
import g56  # noqa: E402
import g60h  # noqa: E402

LAST = {}
_orig = g56.ServeTeacher.__call__


def _call(self, *lines):
    r = _orig(self, *lines)
    st = self.log[-1]["stats"]
    LAST.update({k: v for k, v in st.items() if k.startswith("cum_")})
    return r


g56.ServeTeacher.__call__ = _call


def job(a):
    LAST.clear()
    r = g60h.job(a)
    return {"curriculum": a[0], "seed": a[1], "arm": a[2], "counters": dict(LAST),
            "reply_stream_sha256": r["reply_stream_sha256"]}


if __name__ == "__main__":
    m = int(sys.argv[1])
    for r_ in g56.BASEF:
        g56.BASEF[r_] = g56.BASEF[r_] + [f"--margin={m}"]
    jobs = [(c, s, a + "h", f"/tmp/g60h_audit_m{m}") for c in g60h.SEEDS for s in g60h.SEEDS[c] for a in "CBP"]
    with Pool(4) as p:
        res = p.map(job, jobs)
    tot = {"decodes": sum(x["counters"].get("cum_decodes", 0) for x in res),
           "decode_errors": sum(x["counters"].get("cum_decode_errors", 0) for x in res)}
    Path(sys.argv[2]).write_text(json.dumps({"margin": m, "total": tot, "runs": res}, indent=1))
    print(json.dumps(tot))
