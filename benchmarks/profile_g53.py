"""G53 diagnostic profile (docs/G53.md): where does the persistent learner's CPU go?
Runs the G51 arms (C, P, B; comp and unrel) on diagnostic seeds through prof_engine.py and
aggregates per arm, per call kind, per engine function (cumulative, nested). Not a registered run.
Run: python3 benchmarks/profile_g53.py --comp-seeds 941,942 --unrel-seeds 943 --out g53_profile"""
from __future__ import annotations
import json
import os
import subprocess
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT))
import g51  # noqa: E402
import g53  # noqa: E402
import packetlm.g45_test as g45t  # noqa: E402

SHIM = str(ROOT / "benchmarks" / "prof_engine.py")


class _Sub:
    """subprocess stand-in for the Teacher: same call, engine run through the profiling shim."""
    def __getattr__(self, k):
        return getattr(subprocess, k)

    @staticmethod
    def run(cmd, **kw):
        if cmd[1:3] == ["-m", "packetlm.engine"]:
            cmd = [cmd[0], SHIM] + cmd[3:]
        return subprocess.run(cmd, **kw)


def job(args):
    cur, seed, arm, out = args
    prof = Path(out) / f"prof_{cur}_{seed}_{arm}.jsonl"
    if prof.exists():
        prof.unlink()
    os.environ["PL_PROF_OUT"] = str(prof)
    g45t.subprocess = _Sub()
    import g46
    g46.subprocess = _Sub()
    r = (g53.job if arm in g53.FLAGS and arm not in g51.FLAGS else g51.job)((cur, seed, arm, out))
    return {"cur": cur, "seed": seed, "arm": arm, "cpu_total_all_s": r.get("cpu_total_all_s"), "prof": str(prof)}


def main(argv):
    get = lambda f, d: [int(x) for x in argv[argv.index(f) + 1].split(",")] if f in argv else d  # noqa: E731
    seeds = {"comp": get("--comp-seeds", [941, 942]), "unrel": get("--unrel-seeds", [943])}
    arms = argv[argv.index("--arms") + 1].split(",") if "--arms" in argv else ["C", "P", "B"]
    out = ROOT / "artifacts" / (argv[argv.index("--out") + 1] if "--out" in argv else "g53_profile")
    out.mkdir(parents=True, exist_ok=True)
    jobs = [(c, s, a, str(out)) for c in seeds for s in seeds[c] for a in arms]
    with Pool(8) as pool:
        res = pool.map(job, jobs)
    summary = {}
    for r in res:
        recs = [json.loads(l) for l in Path(r["prof"]).read_text().splitlines()]
        key = f"{r['cur']}:{r['arm']}"
        s = summary.setdefault(key, {"seeds": 0, "calls": 0, "cpu_total_s": 0.0, "startup_s": 0.0, "by_kind": {},
                                     "funcs": {}, "state_bytes_max": 0, "cpu_total_all_s_unprofiled_equiv": 0.0})
        s["seeds"] += 1
        for x in recs:
            s["calls"] += 1
            s["cpu_total_s"] += x["cpu_total_s"]
            s["startup_s"] += x["cpu_pre_profile_s"]
            k = s["by_kind"].setdefault(x["kind"], {"calls": 0, "cpu_total_s": 0.0})
            k["calls"] += 1
            k["cpu_total_s"] += x["cpu_total_s"]
            s["state_bytes_max"] = max(s["state_bytes_max"], x["state_bytes"])
            for f, (t, n) in x["funcs"].items():
                ff = s["funcs"].setdefault(f, [0.0, 0])
                ff[0] += t
                ff[1] += n
    for s in summary.values():
        tot = s["cpu_total_s"]
        s["funcs_share"] = {f: round(v[0] / tot, 4) for f, v in sorted(s["funcs"].items(), key=lambda kv: -kv[1][0])}
        s["funcs"] = {f: [round(v[0], 3), v[1]] for f, v in s["funcs"].items()}
        s["cpu_total_s"] = round(tot, 3)
        s["startup_s"] = round(s["startup_s"], 3)
        for k in s["by_kind"].values():
            k["cpu_total_s"] = round(k["cpu_total_s"], 3)
    (out / "profile_summary.json").write_text(json.dumps({"seeds": seeds, "arms": arms, "summary": summary}, indent=1))
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
