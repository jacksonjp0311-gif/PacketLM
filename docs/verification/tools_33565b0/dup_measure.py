"""Verifier: CPU of the full validation that the K = 64 period adds in the snapshot call (validate_lean
+ ix_check against a fresh build, serve.Server._validate's full branch), measured directly on the
library-scaling states. Usage (PL_ROOT selects the engine): dup_measure.py SEED L ARM_EXTRA"""
import json, os, random, sys, tempfile, time
from pathlib import Path
ROOT = os.environ["PL_ROOT"]; sys.path.insert(0, ROOT)
sys.path.insert(1, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "benchmarks"))
from packetlm import serve  # noqa: E402
import g58_libscale as H  # noqa: E402
seed, L = int(sys.argv[1]), int(sys.argv[2]); extra = sys.argv[3].split() if len(sys.argv) > 3 and sys.argv[3] else []
fl = H.FLAGS + extra
facts, caps = H.lib_padding(random.Random(seed * 7919 + L), L); work = H.workload(random.Random(seed), 10)
p = Path(tempfile.mkdtemp()) / "s.json"; srv = serve.Server()
for k in range(0, len(facts), 2000):
    srv.call(p, fl, facts[k:k + 2000])
for ex in caps:
    srv.call(p, fl, ex)
srv._snapshot(srv.cur)
for t, lines in work:
    srv.call(p, fl, lines)
eng = srv._engine(srv.cur); xs = []
for _ in range(3):
    c = time.process_time()
    serve.validate_lean({"schema": serve.SCHEMA, "checksum": None, "state": eng.state}, checksum_ok=True)
    srv.cur.memo.ix_check(eng.state, serve._fresh_index(eng.state["facts"]))
    xs.append(time.process_time() - c)
c = time.process_time(); srv._snapshot(srv.cur); snap = time.process_time() - c
print(json.dumps({"seed": seed, "L": L, "arm": "r" if extra else ("j0" if "-j0" in ROOT else "j"), "dup_full_validation_s": sorted(xs)[1], "snapshot_s": snap}))
