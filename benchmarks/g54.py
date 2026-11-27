"""G54: exact per-call cost bounds (docs/G54.md, registered before the run).
Same design as G53 (G50 `complete` teacher, whole-process CPU with maintenance, instrument 70297af).
Arms: Cb  persistent, library, --bounded (G53 engine path; reference for the mechanism)
      Cl  Cb with --lean
      Bb  empty state per task, --bounded (G53 reference learner; for the floor analysis)
      Bl  Bb with --lean (reference learner for L1/L3: same engine path as Cl)
      Pl  persistent, no library, --bounded --lean (primitive-only)
      Fl  frozen after phase A, --bounded --lean (compositional only)
Exactness guards: every reply of Cl equals Cb's and every reply of Bl equals Bb's, call by call.
Floor: median whole-process CPU of FLOOR_N engine calls on an empty state (one question), per flag set.
Run: python3 benchmarks/g54.py [--out g54] [--dev] [--comp-seeds ...] [--unrel-seeds ...]
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

FLAGS = {"Cb": ["--answers", "--bounded"], "Cl": ["--answers", "--bounded", "--lean"],
         "Bb": ["--answers", "--no-library", "--bounded"], "Bl": ["--answers", "--no-library", "--bounded", "--lean"],
         "Pl": ["--answers", "--no-library", "--bounded", "--lean"], "Fl": ["--answers", "--bounded", "--lean"]}
# g46 keys arm behaviour on the arm letter: B = empty state per task, F = frozen in phase B
ROLE = {"Cb": "C", "Cl": "C", "Bb": "B", "Bl": "B", "Pl": "P", "Fl": "F"}
CURRICULA = {"comp": (g46.world, ["Cb", "Cl", "Bb", "Bl", "Pl", "Fl"]),
             "unrel": (g46u.world_unrelated, ["Cb", "Cl", "Bb", "Bl", "Pl"])}
COMP_SEEDS = [141, 142, 143, 144, 145, 146, 147]
UNREL_SEEDS = [151, 152, 153, 154, 155, 156, 157]
FLOOR_N = 40
HARNESS = ["benchmarks/g54.py", "benchmarks/g53.py", "benchmarks/g51.py", "benchmarks/g46.py", "benchmarks/g46u.py",
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


def floor_cpu(flags, d):
    """Fixed per-process cost: whole-process CPU of a call on an empty state with one question.
    Every arm pays it once per process; no per-call engine change can remove it."""
    d.mkdir(parents=True, exist_ok=True)
    xs = []
    for i in range(FLOOR_N):
        st = d / f"floor_{i}.json"
        for p in d.glob(f"floor_{i}.json*"):
            p.unlink()
        p = subprocess.run([sys.executable, "-m", "packetlm.engine", str(st), *flags, "--deepen=5", "what is x y"],
                           cwd=ROOT, capture_output=True, text=True, check=True)
        xs.append(json.loads(p.stdout)["cpu_total_s"])
    xs.sort()
    return {"n": FLOOR_N, "median_s": xs[len(xs) // 2], "min_s": xs[0], "max_s": xs[-1]}


def structure(per, procs, f0):
    """Descriptive split (docs/G54.md §3): processes x floor is the structural part of an arm's cost."""
    return {"processes": procs, "floor_s": round(procs * f0, 3), "above_floor_s": round(per - procs * f0, 3)}


def main(argv):
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()  # noqa: E731
    head, dirty = git("rev-parse", "HEAD"), git("status", "--porcelain")
    harness = hashlib.sha256(b"".join((ROOT / f).read_bytes() for f in HARNESS)).hexdigest()
    pin = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=INSTRUMENT, capture_output=True, text=True).stdout.strip()
    idirty = subprocess.run(["git", "status", "--porcelain"], cwd=INSTRUMENT, capture_output=True, text=True).stdout.strip()
    get = lambda f, d: [int(x) for x in argv[argv.index(f) + 1].split(",")] if f in argv else d  # noqa: E731
    seeds = {"comp": get("--comp-seeds", COMP_SEEDS), "unrel": get("--unrel-seeds", UNREL_SEEDS)}
    name = "g54_dev" if "--dev" in argv else (argv[argv.index("--out") + 1] if "--out" in argv else "g54")
    OUT = ROOT / "artifacts" / name
    OUT.mkdir(parents=True, exist_ok=True)
    sha0 = g48.source_hash()
    jobs = [(c, s, a, str(OUT)) for c, (_, arms) in CURRICULA.items() for s in seeds[c] for a in arms]
    jobs.sort(key=lambda j: j[2] in ("Bb", "Bl", "Fl"))  # long jobs first
    with Pool(8) as pool:
        res = pool.map(job, jobs)
    floor = {k: floor_cpu(FLAGS[k], OUT / "floor") for k in ("Bb", "Bl")}
    runs = {(r["curriculum"], r["seed"], r["arm"]): r for r in res}
    rep = {"started": started, "head": head, "git_status_porcelain": dirty, "harness_sha256": harness,
           "instrument": {"path": str(INSTRUMENT), "head": pin, "pinned": pin == PIN, "unmodified": idirty == ""},
           "seeds": seeds, "source_sha256": sha0, "engine_sha256": g48.engine_hash(), "curricula": {}}
    for c, (_, arms) in CURRICULA.items():
        raw = {f"{s}:{a}": {**runs[(c, s, a)], "arm": a} for s in seeds[c] for a in arms}
        (OUT / f"{c}_raw.json").write_text(json.dumps(raw, default=str))
        csv = OUT / f"{c}_total.csv"
        export(raw, csv, None, "cpu_total_s")
        n = len(runs[(c, seeds[c][0], "Cb")]["tasks"])
        contrasts = [("Cl+maint", "Bl"), ("Cl+maint", "Pl+maint"), ("Cl+maint", "Cb+maint"), ("Bl", "Bb"),
                     ("Cl", "Bl"), ("Cl", "Pl")]
        if "Fl" in arms:
            contrasts.append(("Cl+maint", "Fl+maint"))
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
                             "reply_stream_sha256": rr["reply_stream_sha256"], "processes": rr["processes"],
                             "maint_processes": sum(f.get("cost", {}).get("processes", 0) for f in rr["families"]),
                             "maint_cpu_s": round(sum(f.get("cost", {}).get("cpu_total_s", 0) for f in rr["families"]), 4)}
        f0 = floor["Bl"]["median_s"]
        tot = {a: sum(per[s][a]["cpu_total_all_s"] for s in seeds[c]) for a in arms}
        prc = {a: sum(per[s][a]["processes"] for s in seeds[c]) for a in arms}
        struct = {a: structure(tot[a], prc[a], f0) for a in arms}
        # what A(Cl+maint || Bl) would be if Cl's work above the floor were as small as Bl's (descriptive)
        best = 1 - (prc["Cl"] * f0 + struct["Bl"]["above_floor_s"]) / tot["Bl"]
        rep["curricula"][c] = {"n": n, "per_seed": per, "instrument": [instrument(csv, a, b, n) for a, b in contrasts],
                               "structure": {"floor_per_process_s": f0, "arms": struct,
                                             "A_if_Cl_above_floor_equalled_Bl": round(best, 4),
                                             "structural_share_of_gap": round((prc["Cl"] - prc["Bl"]) * f0 / (tot["Cl"] - tot["Bl"]), 4)
                                             if tot["Cl"] != tot["Bl"] else None},
                               "exact_Cl_equals_Cb": all(per[s]["Cl"]["reply_stream_sha256"] == per[s]["Cb"]["reply_stream_sha256"]
                                                         for s in seeds[c]),
                               "exact_Bl_equals_Bb": all(per[s]["Bl"]["reply_stream_sha256"] == per[s]["Bb"]["reply_stream_sha256"]
                                                         for s in seeds[c])}
    q = rep["curricula"]
    rep["floor"] = floor
    rep["guards"] = {"exact_Cl_replies_equal_Cb": all(v["exact_Cl_equals_Cb"] for v in q.values()),
                     "exact_Bl_replies_equal_Bb": all(v["exact_Bl_equals_Bb"] for v in q.values()),
                     "no_wrong_qualified_Cb_Cl": all(v[a]["wrong_qualified_sealed"] == 0 for c in q.values()
                                                     for v in c["per_seed"].values() for a in ("Cb", "Cl")),
                     "instrument_pinned_unmodified": rep["instrument"]["pinned"] and rep["instrument"]["unmodified"],
                     "all_reports_ran": all(x["rc"] == 0 for c in q.values() for x in c["instrument"]),
                     "source_unchanged": sha0 == g48.source_hash()}
    (OUT / f"{name}_receipt.json").write_text(json.dumps(rep, indent=1, default=str))
    print(json.dumps({"guards": rep["guards"], **{c: {"reports": [(x["cont"], x["base"], x["report"].splitlines()[0] if x["report"] else x["err"])
                                                                   for x in v["instrument"]],
                                                       "cpu": {a: round(sum(ps[a]["cpu_total_all_s"] for ps in v["per_seed"].values()), 1)
                                                               for a in CURRICULA[c][1]},
                                                       "structure": v["structure"],
                                                       "exact": [v["exact_Cl_equals_Cb"], v["exact_Bl_equals_Bb"]]}
                                                  for c, v in q.items()}, "floor": floor}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
