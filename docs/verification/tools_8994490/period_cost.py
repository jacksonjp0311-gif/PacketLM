"""Verifier: with the registered defaults (SNAPSHOT_EVERY = FULL_VALIDATE_EVERY = 64) the K-period
full validation always lands on the same call as the snapshot (since_full <= since, both reset at a
snapshot), so per 64 journaled calls Xj pays validate_lean + ix_check twice (once in _validate, once
in _snapshot/save). part S's R1k_amort charges only the snapshot. This measures the extra
(validate_lean + ix_check) at N = 1000 / 16000 on the part S states (seeds 231-237) and recomputes
R1k_amort with it. Usage: period_cost.py [registered scale dir]"""
import json, sys, time
from pathlib import Path
import random, tempfile
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "benchmarks"))
from packetlm import serve  # noqa: E402
from packetlm.engine import validate_lean, SCHEMA, _fresh_index  # noqa: E402
from g57_scale import padding, workload, FLAGS  # noqa: E402
from stoprule_recompute import boot  # noqa: E402
d = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs/evidence/g57b/scale"
flags = FLAGS + ["--indexed", "--incremental"]
extra = {}
for seed in range(231, 238):
    for n in (1000, 16000):
        rng = random.Random(seed * 100003 + n)
        facts, caps = padding(rng, n)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "s.json"; srv = serve.Server()
            for k in range(0, len(facts), 2000):
                srv.call(p, flags, facts[k:k + 2000])
            for ex in caps:
                srv.call(p, flags, ex)
            for _, lines in workload(random.Random(seed), 10):
                srv.call(p, flags, lines)
            o = srv.cur; st = o.state
            ts = []
            for _ in range(5):
                c0 = time.process_time()
                validate_lean({"schema": SCHEMA, "checksum": None, "state": st}, checksum_ok=True)
                o.memo.ix_check(st, _fresh_index(st["facts"]))
                ts.append(time.process_time() - c0)
            extra[(seed, n)] = sorted(ts)[2]
            srv.close()
amort2 = {}
for seed in range(231, 238):
    for n in (1000, 16000):
        r = json.loads((d / f"s{seed}_n{n}_j.json").read_text())
        amort2[(seed, n)] = r["amort_task_cpu_s"] + r["journaled_calls"] / 10 / 64 * extra[(seed, n)]
print(json.dumps({"extra_validate_plus_ixcheck_ms": {n: round(1000 * sum(extra[(s, n)] for s in range(231, 238)) / 7, 2) for n in (1000, 16000)},
                  "R1k_amort_16000_registered_form": boot([json.loads((d / f"s{s}_n16000_j.json").read_text())["amort_task_cpu_s"] /
                                                           json.loads((d / f"s{s}_n1000_j.json").read_text())["amort_task_cpu_s"] for s in range(231, 238)]),
                  "R1k_amort_16000_with_period_validation": boot([amort2[(s, 16000)] / amort2[(s, 1000)] for s in range(231, 238)])}))
