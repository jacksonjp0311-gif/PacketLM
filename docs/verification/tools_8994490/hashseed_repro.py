"""Verifier: replay one generated session (incr_diff.session, mutant_equiv's settings) up to a call
and print the replies/state hash per call, so two processes with different PYTHONHASHSEED can be
compared. Usage: PYTHONHASHSEED=x hashseed_repro.py SEED SESSION_INDEX FLAGSET(ref|xi|xj) [K] [SNAP] [--inproc]"""
import hashlib, json, random, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2])); sys.path.insert(1, str(HERE))
from packetlm import serve  # noqa: E402
from incr_diff import session, BASE  # noqa: E402
seed, idx, fs = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
K = int(sys.argv[4]) if len(sys.argv) > 4 else 64
snap = int(sys.argv[5]) if len(sys.argv) > 5 else 64
FL = {"ref": BASE, "xi": BASE + ["--indexed"], "xj": BASE + ["--indexed", "--incremental"]}[fs]
rng = random.Random(seed)
for i in range(idx + 1):
    calls = session(rng, 0.05, (30, 90))
d = Path(tempfile.mkdtemp(dir="/tmp"))
srv = serve.Server(snap, full_every=K)
H = lambda x: hashlib.sha256(json.dumps(x).encode()).hexdigest()[:12]  # noqa: E731
for j, c in enumerate(calls):
    if c == ["__drop__"]:
        srv.close(); continue
    if c in (["__crash__"], ["__torn__"]):
        if srv.cur and srv.cur.jfh:
            srv.cur.jfh.close()
        srv = serve.Server(snap, full_every=K); continue
    r = srv.call(d / "s.json", FL, c)
    print(json.dumps({"c": j, "lines": c, "replies": r["replies"], "st": H(srv.cur.state)}))
