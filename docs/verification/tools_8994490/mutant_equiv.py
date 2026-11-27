"""Verifier: is `g57b_drop_keeps_scope` an equivalent mutant? Runs the same sessions on the original
and on the mutated engine (each in its own process, ROOT given), XJ flags, and writes a per-call
trace: replies hash, state hash, which validation ran (scoped/full), the scope's ok flag and
touched count at validation, index validity and ix_check count. Two traces are then compared.
Usage: mutant_equiv.py ROOT N SEED K SNAP OUT"""
import hashlib, json, random, sys, tempfile, shutil
from pathlib import Path
root, N, seed, K, snap, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), sys.argv[6]
sys.path.insert(0, root)
sys.path.insert(1, str(Path(__file__).resolve().parent))
import packetlm.serve as serve  # noqa: E402
assert serve.__file__.startswith(root), serve.__file__
import packetlm.engine as _e  # noqa: E402
assert _e.__file__.startswith(root), _e.__file__
from incr_diff import session, BASE  # noqa: E402
FJ = BASE + ["--indexed", "--incremental"]
H = lambda x: hashlib.sha256(json.dumps(x).encode()).hexdigest()[:16]  # noqa: E731

orig_validate = serve.Server._validate
TRACE = []


def traced(self, o, eng):
    sc = o.memo.scope
    before = dict(o.memo.counts)
    rec = {"ok": sc["ok"], "touched": len(sc["touched"]), "ix_valid": o.memo.ix_valid(eng.state), "since_full": o.since_full}
    try:
        orig_validate(self, o, eng)
    finally:
        rec["path"] = "scoped" if o.memo.counts.get("scoped_validations", 0) > before.get("scoped_validations", 0) else "full"
        TRACE.append(rec)


serve.Server._validate = traced
rng = random.Random(seed)
lines_out = []
for i in range(N):
    calls = session(rng, 0.05, (30, 90))
    d = Path(tempfile.mkdtemp(dir="/tmp"))
    srv = serve.Server(snap, full_every=K)
    for j, c in enumerate(calls):
        if c == ["__drop__"]:
            srv.close(); continue
        if c in (["__crash__"], ["__torn__"]):
            if srv.cur and srv.cur.jfh:
                srv.cur.jfh.close()
            srv = serve.Server(snap, full_every=K); continue
        TRACE.clear()
        try:
            r = srv.call(d / "s.json", FJ, c)
            rh = H(r["replies"])
        except Exception as exc:  # noqa: BLE001
            rh = f"ERR {type(exc).__name__}: {exc}"
            srv = serve.Server(snap, full_every=K)
        st = H(srv.cur.state) if srv.cur else None
        lines_out.append(json.dumps({"s": i, "c": j, "r": rh, "st": st, "v": list(TRACE),
                                     "ix_checks": srv.cur.memo.ix_checks if srv.cur else None}))
    srv.close()
    shutil.rmtree(d)
Path(out).write_text("\n".join(lines_out) + "\n")
print(json.dumps({"root": root, "calls": len(lines_out), "validations": sum(len(json.loads(x)["v"]) for x in lines_out)}))
