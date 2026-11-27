"""Verifier: where the snapshot CPU goes at L = 1024 (G58.md §12 claim: the increase over j0 is the
extended ix_check). Pads like g58_libscale.run_one (seed, L), runs the workload, then times
`_snapshot` 5x: as is, with Memo.ix_check replaced by a no-op, and with cProfile (top functions).
Run with PL_ROOT=<tree> to choose the engine; ARM flags via argv[3] ('' or --routed)."""
import cProfile, io, json, os, pstats, random, sys, tempfile, time
from pathlib import Path
ROOT = os.environ.get("PL_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
sys.path.insert(0, ROOT)
sys.path.insert(1, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "benchmarks"))
from packetlm import serve, engine as E  # noqa: E402
import g58_libscale as H  # noqa: E402  (harness of 33565b0; only lib_padding/workload are used)
seed, L = int(sys.argv[1]), int(sys.argv[2]); extra = sys.argv[3].split() if len(sys.argv) > 3 and sys.argv[3] else []
flags = H.FLAGS + extra
rng = random.Random(seed * 7919 + L); facts, caps = H.lib_padding(rng, L); work = H.workload(random.Random(seed), 10)
d = tempfile.mkdtemp(); p = Path(d) / "s.json"; srv = serve.Server()
for k in range(0, len(facts), 2000):
    srv.call(p, flags, facts[k:k + 2000])
for ex in caps:
    srv.call(p, flags, ex)
srv._snapshot(srv.cur)
for t, lines in work:
    srv.call(p, flags, lines)
def tm(n=5):
    xs = []
    for _ in range(n):
        c = time.process_time(); srv._snapshot(srv.cur); xs.append(time.process_time() - c)
    return round(1000 * sorted(xs)[n // 2], 2)
out = {"root": ROOT, "flags": flags, "facts": len(srv.cur.state["facts"]), "caps": len(srv.cur.state["capabilities"])}
out["snapshot_ms_median"] = tm()
if hasattr(E.Memo, "ix_check"):
    orig = E.Memo.ix_check; E.Memo.ix_check = lambda self, st, fr: None
    out["snapshot_ms_no_ix_check"] = tm(); E.Memo.ix_check = orig
    m = srv.cur.memo
    if m is not None and m.ix is not None and m.ix_valid(srv.cur.state):
        c = time.process_time()
        for _ in range(5):
            m.ix_check(srv.cur.state, E._fresh_index(srv.cur.state["facts"]))
        out["ix_check_plus_fresh_ms"] = round(1000 * (time.process_time() - c) / 5, 2)
pr = cProfile.Profile(); pr.enable(); srv._snapshot(srv.cur); pr.disable()
s = io.StringIO(); pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(14)
out["profile_top"] = [l for l in s.getvalue().splitlines() if l.strip()][4:22]
print(json.dumps(out, indent=1))
