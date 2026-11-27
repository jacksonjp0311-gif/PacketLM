"""Verifier: does the K = 64 period full validation still coincide with the snapshot (Low 3 of
verify-8994490, stated not fixed) and run ix_check twice in that call? Append-only fact calls on a
padded state (L capabilities), registered defaults (snapshot every 64, K = 64), --routed."""
import json, os, random, sys, tempfile
from pathlib import Path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, ROOT); sys.path.insert(1, os.path.join(ROOT, "benchmarks"))
from packetlm import serve  # noqa: E402
import g58_libscale as H  # noqa: E402
L = int(sys.argv[1]) if len(sys.argv) > 1 else 256
fl = H.FLAGS + ["--routed"]
facts, caps = H.lib_padding(random.Random(1), L)
p = Path(tempfile.mkdtemp()) / "s.json"; srv = serve.Server()
for k in range(0, len(facts), 2000):
    srv.call(p, fl, facts[k:k + 2000])
for ex in caps:
    srv.call(p, fl, ex)
rows = []
for i in range(200):
    m = srv.cur.memo; c0, f0, s0 = m.ix_checks, m.counts["full_validations"], srv.cur.since
    srv.call(p, fl, [f"fact zq{i} w0 zq{i + 1}"])
    m = srv.cur.memo
    if m.ix_checks != c0:
        rows.append({"call": i, "ix_checks": m.ix_checks - c0, "full_validation": m.counts["full_validations"] - f0, "snapshot": srv.cur.since < s0 + 1, "since_full": srv.cur.since_full})
print(json.dumps({"L": L, "facts": len(srv.cur.state["facts"]), "calls_with_ix_check": rows}, indent=0))
