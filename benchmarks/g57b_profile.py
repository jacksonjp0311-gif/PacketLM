"""G57b profiles (descriptive, not a registered result).
1. Part S workload (benchmarks/g57_scale.py) under cProfile at padding N = 0, 1000, 4000, 16000 for
   the given flags: per-function self time per N, and which functions scale with N.
2. Optional (--comp SEED): one comp Ci arm run (benchmarks/g57.py job) with the server under
   cProfile: where the library scan spends its time (sets up G58 routing).
Run: python3 benchmarks/g57b_profile.py OUT_JSON [--flags ...] [--seed 991] [--comp 961]
"""
from __future__ import annotations
import cProfile
import json
import pstats
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT))
import g57_scale  # noqa: E402
from packetlm import serve  # noqa: E402


def part_s(n, flags, seed, tasks=10):
    rng = random.Random(seed * 100003 + n)
    facts, caps = g57_scale.padding(rng, n)
    work = g57_scale.workload(random.Random(seed), tasks)
    pr = cProfile.Profile()
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "s.json"
        srv = serve.Server()
        for k in range(0, len(facts), 2000):
            srv.call(p, flags, facts[k:k + 2000])
        for ex in caps:
            srv.call(p, flags, ex)
        t0 = time.process_time()
        pr.enable()
        for _, lines in work:
            srv.call(p, flags, lines)
        pr.disable()
        cpu = time.process_time() - t0
        srv.close()
    st = pstats.Stats(pr)
    out = {}
    for (fn, line, name), (cc, nc, tt, ct, _) in st.stats.items():
        key = f"{Path(fn).name}:{line}({name})"
        out[key] = {"tottime": round(tt, 5), "cumtime": round(ct, 5), "calls": nc}
    return cpu, out


def comp_profile(seed, flags_extra):
    import g56
    out = Path(tempfile.mkdtemp()) / "prof.out"

    class PS(g56.Server):
        def __init__(self):
            self.p = subprocess.Popen([sys.executable, "-c", f"import cProfile,packetlm.serve as s; cProfile.run('s.main()', '{out}')"],
                                      cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
    g56.Server = PS
    g56.BASEF["C"] = g56.BASEF["C"] + flags_extra
    r = g56.job(("comp", seed, "Cs", tempfile.mkdtemp()))
    st = pstats.Stats(str(out))
    rows = sorted(((v[3], v[2], v[1], f"{Path(k[0]).name}:{k[1]}({k[2]})") for k, v in st.stats.items()), reverse=True)
    return {"cpu_total_all_s": r["cpu_total_all_s"],
            "top_cumulative": [{"fn": f, "cumtime": round(c, 4), "tottime": round(t, 4), "calls": n} for c, t, n, f in rows[:45]],
            "top_self": [{"fn": f, "tottime": round(t, 4), "calls": n}
                         for t, c, n, f in sorted(((v[2], v[3], v[1], f"{Path(k[0]).name}:{k[1]}({k[2]})") for k, v in st.stats.items()), reverse=True)[:30]]}


def main(argv):
    dest = Path(argv[0])
    flags = argv[argv.index("--flags") + 1].split(",") if "--flags" in argv else g57_scale.FLAGS + ["--indexed"]
    seed = int(argv[argv.index("--seed") + 1]) if "--seed" in argv else 991
    sizes = [0, 1000, 4000, 16000]
    res = {"flags": flags, "seed": seed, "sizes": sizes, "cpu": {}, "functions": {}}
    per = {}
    for n in sizes:
        cpu, f = part_s(n, flags, seed)
        res["cpu"][n] = round(cpu, 4)
        per[n] = f
    keys = set().union(*[set(v) for v in per.values()])
    rows = []
    for k in keys:
        t = [per[n].get(k, {}).get("tottime", 0.0) for n in sizes]
        rows.append({"fn": k, "tottime": t, "growth": round(t[-1] - t[0], 4),
                     "calls": [per[n].get(k, {}).get("calls", 0) for n in sizes]})
    rows.sort(key=lambda r: -r["growth"])
    res["scaling"] = rows[:40]
    if "--comp" in argv:
        res["comp_scan"] = comp_profile(int(argv[argv.index("--comp") + 1]), [x for x in flags if x in ("--indexed", "--incremental")])
    dest.write_text(json.dumps(res, indent=1))
    print(json.dumps({"cpu": res["cpu"], "scaling": [(r["fn"], r["tottime"]) for r in rows[:25]]}, indent=0))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
