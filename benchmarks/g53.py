"""G53: bounded library cost (docs/G53.md, registered before the run).
Same design as G51 (G50 `complete` teacher, whole-process CPU with maintenance, instrument 70297af),
with the engine's exact cost bounds (--bounded) on every arm except the unbounded reference C.
Arms: C   persistent, library, unbounded (G51 engine path; reference for the mechanism)
      Cb  C with --bounded
      Bb  empty state per task, --bounded (reference learner)
      Pb  persistent, no library, --bounded (primitive-only)
      Fb  frozen after phase A, --bounded (compositional only)
Exactness guard: every reply of Cb equals C's, call by call (hash of the reply stream).
Run: python3 benchmarks/g53.py [--out g53] [--dev] [--comp-seeds ...] [--unrel-seeds ...]
"""
from __future__ import annotations
import hashlib
import json
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
from g51 import instrument, INSTRUMENT, PIN, BOOT  # noqa: E402

FLAGS = {"C": ["--answers"], "Cb": ["--answers", "--bounded"], "Bb": ["--answers", "--no-library", "--bounded"],
         "Pb": ["--answers", "--no-library", "--bounded"], "Fb": ["--answers", "--bounded"]}
# g46 keys arm behaviour on the arm letter: B = empty state per task, F = frozen in phase B
ROLE = {"C": "C", "Cb": "C", "Bb": "B", "Pb": "P", "Fb": "F"}
CURRICULA = {"comp": (g46.world, ["C", "Cb", "Bb", "Pb", "Fb"]), "unrel": (g46u.world_unrelated, ["C", "Cb", "Bb", "Pb"])}
COMP_SEEDS = [121, 122, 123, 124, 125, 126, 127]
UNREL_SEEDS = [131, 132, 133, 134, 135, 136, 137]
HARNESS = ["benchmarks/g53.py", "benchmarks/g51.py", "benchmarks/g46.py", "benchmarks/g46u.py",
           "benchmarks/la_export.py", "benchmarks/px.py"]


def job(args):
    cur, seed, arm, out = args
    role = ROLE[arm]
    g46.FLAGS[role] = FLAGS[arm]
    g46.RICH = {role}
    g46.COMPLETE = {role}
    g46.world = CURRICULA[cur][0]
    g46.OUT = Path(out) / cur / arm  # one directory per arm: roles share g46's file names
    d = g46.OUT / f"seed{seed}"
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    stream = hashlib.sha256()
    base = g46.Teacher

    class Rec(base):
        def __call__(self, *lines):
            r = super().__call__(*lines)
            stream.update(json.dumps([list(lines), r]).encode())
            return r
    g46.Teacher = Rec
    try:
        r = g46.run_arm((seed, role))
    finally:
        g46.Teacher = base
    r["arm"], r["role"], r["curriculum"], r["reply_stream_sha256"] = arm, role, cur, stream.hexdigest()
    return r


def main(argv):
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()  # noqa: E731
    head, dirty = git("rev-parse", "HEAD"), git("status", "--porcelain")
    harness = hashlib.sha256(b"".join((ROOT / f).read_bytes() for f in HARNESS)).hexdigest()
    pin = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=INSTRUMENT, capture_output=True, text=True).stdout.strip()
    idirty = subprocess.run(["git", "status", "--porcelain"], cwd=INSTRUMENT, capture_output=True, text=True).stdout.strip()
    get = lambda f, d: [int(x) for x in argv[argv.index(f) + 1].split(",")] if f in argv else d  # noqa: E731
    seeds = {"comp": get("--comp-seeds", COMP_SEEDS), "unrel": get("--unrel-seeds", UNREL_SEEDS)}
    name = "g53_dev" if "--dev" in argv else (argv[argv.index("--out") + 1] if "--out" in argv else "g53")
    OUT = ROOT / "artifacts" / name
    OUT.mkdir(parents=True, exist_ok=True)
    sha0 = g48.source_hash()
    jobs = [(c, s, a, str(OUT)) for c, (_, arms) in CURRICULA.items() for s in seeds[c] for a in arms]
    jobs.sort(key=lambda j: j[2] in ("Bb", "Fb"))  # long jobs first
    with Pool(8) as pool:
        res = pool.map(job, jobs)
    runs = {(r["curriculum"], r["seed"], r["arm"]): r for r in res}
    rep = {"started": started, "head": head, "git_status_porcelain": dirty, "harness_sha256": harness,
           "instrument": {"path": str(INSTRUMENT), "head": pin, "pinned": pin == PIN, "unmodified": idirty == ""},
           "seeds": seeds, "source_sha256": sha0, "engine_sha256": g48.engine_hash(), "curricula": {}}
    for c, (_, arms) in CURRICULA.items():
        raw = {f"{s}:{a}": {**runs[(c, s, a)], "arm": a} for s in seeds[c] for a in arms}
        (OUT / f"{c}_raw.json").write_text(json.dumps(raw, default=str))
        csv = OUT / f"{c}_total.csv"
        export(raw, csv, None, "cpu_total_s")
        n = len(runs[(c, seeds[c][0], "C")]["tasks"])
        contrasts = [("Cb+maint", "Bb"), ("Cb+maint", "Pb+maint"), ("Cb+maint", "C+maint"), ("Cb", "Pb")]
        if "Fb" in arms:
            contrasts.append(("Cb+maint", "Fb+maint"))
        per = {}
        for s in seeds[c]:
            per[s] = {}
            for a in arms:
                rr = runs[(c, s, a)]
                t = rr["tasks"]
                m, th = g46_th(rr) if ROLE[a] != "B" else (None, None)
                per[s][a] = {"tasks": len(t), "solved": sum(x["correct"] == x["n_sealed"] for x in t),
                             "qualified": sum(x["status"] == "qualified" for x in t),
                             "uses_library": sum(x["uses_library"] for x in t),
                             "wrong_qualified_sealed": sum(r["wrong_qualified"] for x in t for r in x["rows"]),
                             "cpu_total_all_s": rr.get("cpu_total_all_s"), "g46_thresholds": th,
                             "reply_stream_sha256": rr["reply_stream_sha256"]}
        rep["curricula"][c] = {"n": n, "per_seed": per, "instrument": [instrument(csv, a, b, n) for a, b in contrasts],
                               "exact_Cb_equals_C": all(per[s]["Cb"]["reply_stream_sha256"] == per[s]["C"]["reply_stream_sha256"]
                                                        for s in seeds[c])}
    q = rep["curricula"]
    rep["guards"] = {"exact_Cb_replies_equal_C": all(v["exact_Cb_equals_C"] for v in q.values()),
                     "no_wrong_qualified_C_Cb": all(v[a]["wrong_qualified_sealed"] == 0 for c in q.values()
                                                    for v in c["per_seed"].values() for a in ("C", "Cb")),
                     "instrument_pinned_unmodified": rep["instrument"]["pinned"] and rep["instrument"]["unmodified"],
                     "all_reports_ran": all(x["rc"] == 0 for c in q.values() for x in c["instrument"]),
                     "source_unchanged": sha0 == g48.source_hash()}
    (OUT / f"{name}_receipt.json").write_text(json.dumps(rep, indent=1, default=str))
    print(json.dumps({"guards": rep["guards"], **{c: {"reports": [(x["cont"], x["base"], x["report"].splitlines()[0] if x["report"] else x["err"])
                                                                   for x in v["instrument"]],
                                                       "cpu": {a: round(sum(ps[a]["cpu_total_all_s"] for ps in v["per_seed"].values()), 1)
                                                               for a in CURRICULA[c][1]},
                                                       "exact": v["exact_Cb_equals_C"]}
                                                  for c, v in q.items()}}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
