"""G51: learning amortization with qualified capabilities (docs/G51.md, registered before the run).
Every arm uses the G50 `complete` teacher (K: --answers, PX statements, `complete s` for every
answered subject), so qualified capabilities exist and can feed later acquisition.
Curricula: compositional (G46 worlds) and unrelated (G46-U worlds).
Arms: C  persistent, library of qualified + provisional capabilities (as G46 C)
      Q  persistent, library of QUALIFIED capabilities only (--qualified-library)
      B  empty state per task, no library (reference learner)
      P  persistent, no library (primitive-only)
      F  frozen after phase A (compositional only; on G46-U it would equal C)
Cost: whole-process CPU (cpu_total_s) incl. startup, with maintenance charged (<arm>+maint),
exported with benchmarks/la_export.py --total and read with the instrument pinned at 70297af.
Run: python3 benchmarks/g51.py [--out g51] [--dev] [--comp-seeds ...] [--unrel-seeds ...]
"""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT))
import g46  # noqa: E402
import g46u  # noqa: E402
import g48  # noqa: E402
from la_export import export  # noqa: E402
from px import g46_th  # noqa: E402

INSTRUMENT = Path("/workspace/vendor/learning-amortization")
PIN = "70297af"
FLAGS = {"C": ["--answers"], "Q": ["--answers", "--qualified-library"], "B": ["--answers", "--no-library"],
         "P": ["--answers", "--no-library"], "F": ["--answers"]}
CURRICULA = {"comp": (g46.world, ["C", "Q", "B", "P", "F"]), "unrel": (g46u.world_unrelated, ["C", "Q", "B", "P"])}
COMP_SEEDS = [71, 72, 73, 74, 75, 76, 77]
UNREL_SEEDS = [81, 82, 83, 84, 85, 86, 87]
BOOT = 5000


def job(args):
    cur, seed, arm, out = args
    g46.FLAGS.update(FLAGS)
    g46.RICH = set(FLAGS)
    g46.COMPLETE = set(FLAGS)
    g46.world = CURRICULA[cur][0]
    g46.OUT = Path(out) / cur
    d = g46.OUT / f"seed{seed}"
    d.mkdir(parents=True, exist_ok=True)
    for p in list(d.glob(f"{arm}.json*")) + list(d.glob(f"result_{arm}.json")) + list(d.glob(f"{arm}_*.json*")):
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    r = g46.run_arm((seed, arm))
    r["curriculum"] = cur
    return r


def instrument(csv, cont, base, n):
    env = dict(os.environ, PYTHONPATH=str(INSTRUMENT))
    p = subprocess.run([sys.executable, "-m", "amortization", str(csv), "--cont", cont, "--base", base, "--n", str(n),
                        "--bootstrap", str(BOOT)], capture_output=True, text=True, env=env, cwd=ROOT)
    return {"cont": cont, "base": base, "n": n, "rc": p.returncode, "report": p.stdout.strip(), "err": p.stderr.strip()[-400:]}


def main(argv):
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    pin = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=INSTRUMENT, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=INSTRUMENT, capture_output=True, text=True).stdout.strip()
    get = lambda f, d: [int(x) for x in argv[argv.index(f) + 1].split(",")] if f in argv else d  # noqa: E731
    seeds = {"comp": get("--comp-seeds", COMP_SEEDS), "unrel": get("--unrel-seeds", UNREL_SEEDS)}
    name = "g51_dev" if "--dev" in argv else (argv[argv.index("--out") + 1] if "--out" in argv else "g51")
    OUT = ROOT / "artifacts" / name
    OUT.mkdir(parents=True, exist_ok=True)
    sha0 = g48.source_hash()
    jobs = [(c, s, a, str(OUT)) for c, (_, arms) in CURRICULA.items() for s in seeds[c] for a in arms]
    with Pool(8) as pool:
        res = pool.map(job, jobs)
    runs = {(r["curriculum"], r["seed"], r["arm"]): r for r in res}
    rep = {"started": started, "head": head, "instrument": {"path": str(INSTRUMENT), "head": pin, "pinned": pin == PIN,
                                                             "unmodified": dirty == ""},
           "seeds": seeds, "source_sha256": sha0, "engine_sha256": g48.engine_hash(), "curricula": {}}
    for c, (_, arms) in CURRICULA.items():
        raw = {f"{s}:{a}": runs[(c, s, a)] for s in seeds[c] for a in arms}
        (OUT / f"{c}_raw.json").write_text(json.dumps(raw, default=str))
        csv = OUT / f"{c}_total.csv"
        export(raw, csv, None, "cpu_total_s")
        n = len(runs[(c, seeds[c][0], "C")]["tasks"])
        contrasts = [("C+maint", "B"), ("Q+maint", "B"), ("C", "P"), ("C+maint", "P+maint"), ("Q+maint", "C+maint")]
        if "F" in arms:
            contrasts.append(("C+maint", "F+maint"))
        per = {}
        for s in seeds[c]:
            per[s] = {}
            for a in arms:
                t = runs[(c, s, a)]["tasks"]
                m, th = g46_th(runs[(c, s, a)]) if a != "B" else (None, None)
                per[s][a] = {"tasks": len(t), "acquired": sum(x["acquired"] for x in t),
                             "solved": sum(x["correct"] == x["n_sealed"] for x in t),
                             "qualified": sum(x["status"] == "qualified" for x in t),
                             "uses_library": sum(x["uses_library"] for x in t),
                             "uses_library_qualified": sum(x["uses_library"] and x["status"] == "qualified" for x in t),
                             "wrong_qualified_sealed": sum(r["wrong_qualified"] for x in t for r in x["rows"]),
                             "cpu_total_all_s": runs[(c, s, a)].get("cpu_total_all_s"),
                             "g46_thresholds": th}
        rep["curricula"][c] = {"n": n, "per_seed": per,
                               "instrument": [instrument(csv, a, b, n) for a, b in contrasts]}
    q = rep["curricula"]
    rep["guards"] = {"no_wrong_qualified_C_Q": all(v[a]["wrong_qualified_sealed"] == 0 for c in q.values()
                                                  for v in c["per_seed"].values() for a in ("C", "Q")),
                     "instrument_pinned_unmodified": rep["instrument"]["pinned"] and rep["instrument"]["unmodified"],
                     "all_reports_ran": all(x["rc"] == 0 for c in q.values() for x in c["instrument"]),
                     "source_unchanged": sha0 == g48.source_hash()}
    (OUT / f"{name}_receipt.json").write_text(json.dumps(rep, indent=1, default=str))
    print(json.dumps({"guards": rep["guards"], **{c: {"reports": [(x["cont"], x["base"], x["report"][-600:]) for x in v["instrument"]],
                                                      "per_seed": {s: {a: (y["solved"], y["qualified"], y["uses_library"], y["cpu_total_all_s"])
                                                                       for a, y in ps.items()} for s, ps in v["per_seed"].items()}}
                                                  for c, v in q.items()}}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
