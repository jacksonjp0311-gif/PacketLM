"""G57b: the G57 long-lived protocol (benchmarks/g57.py; G50 `complete` teacher, whole-process CPU
with maintenance, instrument 70297af, flags --answers --bounded --lean; B and P add --no-library),
every arm under `python -m packetlm.serve`, on fresh seeds (docs/G57b.md, registered before the run):
  Xi  the G57 engine (--indexed)
  Xj  the G57b engine (--indexed --incremental: persistent fact index, exact recall candidate
      filter, sparse prediction tables, change-scoped validation with the registered full
      validation every 64 mutating calls and at every snapshot)
for X in C, B, P, F (F: compositional only). B starts every task from a new, empty state path.
Guards: every Xj reply stream equals its Xi twin's, and every Xj final state file is
byte-identical to its Xi twin's.
Each finished arm run is written to disk at once (<out>/<cur>/<arm>/seed<seed>/job.json, progress.jsonl).
Run: python3 benchmarks/g57b.py [--out g57b] [--dev] [--comp-seeds ...] [--unrel-seeds ...]
"""
from __future__ import annotations
import hashlib
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
import g48  # noqa: E402
import g56  # noqa: E402
from la_export import export  # noqa: E402
from px import g46_th  # noqa: E402
from g51 import instrument, INSTRUMENT, PIN  # noqa: E402

CURRICULA = g56.CURRICULA
COMP_SEEDS = [241, 242, 243, 244, 245, 246, 247]
UNREL_SEEDS = [251, 252, 253, 254, 255, 256, 257]
HARNESS = ["benchmarks/g57b.py", "benchmarks/g57.py", "benchmarks/g56.py", "benchmarks/g46.py", "benchmarks/g46u.py", "benchmarks/g51.py",
           "benchmarks/la_export.py", "benchmarks/px.py"]


PROTO = {"i": ["--indexed"], "j": ["--indexed", "--incremental"]}


def job(args):
    cur, seed, arm, out = args
    role, proto = arm[0], arm[1]
    flags = g56.BASEF[role] + PROTO[proto]
    saved = dict(g56.BASEF)
    g56.BASEF[role] = flags
    # g56.job writes under <root>/<cur>/<role>s; each protocol runs under its own side root and is
    # moved to <out>/<cur>/<role><proto>, so the two protocols never share a directory
    root = Path(out) / f"_{proto}"
    try:
        r = g56.job((cur, seed, role + "s", str(root)))  # the serve protocol, with this arm's flags
    finally:
        g56.BASEF.clear()
        g56.BASEF.update(saved)
    src = root / cur / (role + "s") / f"seed{seed}"
    dst = Path(out) / cur / arm / f"seed{seed}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    src.rename(dst)
    d = dst
    st = d / f"{role}.json"
    r["arm"], r["proto"] = arm, proto
    r["final_state_sha256"] = hashlib.sha256(st.read_bytes()).hexdigest() if st.exists() else None
    (d / "job.json").write_text(json.dumps(r, default=str))  # incremental: on disk as soon as the arm run ends
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
    name = "g57b_dev" if "--dev" in argv else (argv[argv.index("--out") + 1] if "--out" in argv else "g57b")
    OUT = ROOT / "artifacts" / name
    OUT.mkdir(parents=True, exist_ok=True)
    sha0 = g48.source_hash()
    LOCK = Path("/workspace/REGISTERED_RUN.lock")  # Low 2 of verify-35bda6b: the lock as seen by the run
    lock0 = LOCK.read_text().strip() if LOCK.exists() else None
    load0 = os.getloadavg()
    arms = {c: [r + p for r in roles for p in "ij"] for c, (_, roles) in CURRICULA.items()}
    jobs = [(c, s, a, str(OUT)) for c in CURRICULA for s in seeds[c] for a in arms[c]]
    jobs.sort(key=lambda j: j[2][0] not in ("B", "F"))  # long jobs first
    res = []
    with Pool(8) as pool:
        for r in pool.imap_unordered(job, jobs):
            res.append(r)
            with open(OUT / "progress.jsonl", "a") as fh:  # each arm run's summary as it finishes
                fh.write(json.dumps({"curriculum": r["curriculum"], "seed": r["seed"], "arm": r["arm"],
                                     "cpu_total_all_s": r.get("cpu_total_all_s"),
                                     "reply_stream_sha256": r["reply_stream_sha256"],
                                     "final_state_sha256": r["final_state_sha256"],
                                     "at": time.strftime("%H:%M:%S")}) + "\n")
    runs = {(r["curriculum"], r["seed"], r["arm"]): r for r in res}
    rep = {"started": started, "finished": None, "head": head, "git_status_porcelain": dirty, "harness_sha256": harness,
           "instrument": {"path": str(INSTRUMENT), "head": pin, "pinned": pin == PIN, "unmodified": idirty == ""},
           "seeds": seeds, "source_sha256": sha0, "engine_sha256": g48.engine_hash(), "curricula": {}}
    for c, (_, roles) in CURRICULA.items():
        raw = {f"{s}:{a}": {**runs[(c, s, a)], "arm": a} for s in seeds[c] for a in arms[c]}
        (OUT / f"{c}_raw.json").write_text(json.dumps(raw, default=str))
        csv = OUT / f"{c}_total.csv"
        export(raw, csv, None, "cpu_total_s")
        n = len(runs[(c, seeds[c][0], "Ci")]["tasks"])
        # registered (docs/G57b.md): L1 (comp) / L3 (unrel) = C+maint against B, per protocol
        primary = [("Cj+maint", "Bj"), ("Cj+maint", "Ci+maint")]
        secondary = [("Ci+maint", "Bi"), ("Bj", "Bi"), ("Pj+maint", "Pi+maint"), ("Cj+maint", "Pj+maint"), ("Cj", "Bj")]
        if "F" in roles:
            secondary += [("Fj+maint", "Fi+maint"), ("Cj+maint", "Fj+maint")]
        per = {}
        for s in seeds[c]:
            per[s] = {}
            for a in arms[c]:
                rr = runs[(c, s, a)]
                t = rr["tasks"]
                m, th = g46_th(rr) if a[0] != "B" else (None, None)
                per[s][a] = {"tasks": len(t), "solved": sum(x["correct"] == x["n_sealed"] for x in t),
                             "qualified": sum(x["status"] == "qualified" for x in t),
                             # audit (b): every qualification status; "None" = no version within the
                             # bound (censored: the task ended without a decision)
                             "status": {k: sum(str(x["status"]) == k for x in t) for k in sorted({str(x["status"]) for x in t})},
                             "censored": sum(x["status"] is None for x in t),
                             "uses_library": sum(x["uses_library"] for x in t),
                             "wrong_qualified_sealed": sum(r["wrong_qualified"] for x in t for r in x["rows"]),
                             "cpu_total_all_s": rr.get("cpu_total_all_s"), "g46_thresholds": th,
                             "reply_stream_sha256": rr["reply_stream_sha256"], "final_state_sha256": rr["final_state_sha256"],
                             "calls": rr["processes"],
                             "maint_calls": sum(f.get("cost", {}).get("processes", 0) for f in rr["families"]),
                             "maint_cpu_s": round(sum(f.get("cost", {}).get("cpu_total_s", 0) for f in rr["families"]), 4),
                             "inspect_cpu_s": rr.get("inspect_cpu_s"), "close_cpu_total_s": rr.get("close_cpu_total_s")}
        tot = {a: round(sum(per[s][a]["cpu_total_all_s"] for s in seeds[c]), 3) for a in arms[c]}
        exact = {r: all(per[s][r + "j"]["reply_stream_sha256"] == per[s][r + "i"]["reply_stream_sha256"]
                        and per[s][r + "j"]["final_state_sha256"] == per[s][r + "i"]["final_state_sha256"]
                        for s in seeds[c]) for r in roles}
        outcomes = {a: {k: sum(per[s][a][k] for s in seeds[c]) for k in ("tasks", "solved", "qualified", "censored",
                                                                          "uses_library", "wrong_qualified_sealed")}
                    for a in arms[c]}
        maint = {a: round(sum(per[s][a]["maint_cpu_s"] for s in seeds[c]), 3) for a in arms[c] if a[0] != "B"}
        rep["curricula"][c] = {"n": n, "per_seed": per, "cpu_total": tot, "maint_cpu": maint, "outcomes": outcomes,
                               "primary": [instrument(csv, a, b, n) for a, b in primary],
                               "secondary": [instrument(csv, a, b, n) for a, b in secondary],
                               "exact_j_equals_i": exact}
    q = rep["curricula"]
    rep["guards"] = {"exact_replies_and_state_j_equal_i": all(all(v["exact_j_equals_i"].values()) for v in q.values()),
                     "no_wrong_qualified_C": all(v[a]["wrong_qualified_sealed"] == 0 for c in q.values()
                                                 for v in c["per_seed"].values() for a in ("Ci", "Cj")),
                     "instrument_pinned_unmodified": rep["instrument"]["pinned"] and rep["instrument"]["unmodified"],
                     "all_reports_ran": all(x["rc"] == 0 for c in q.values() for x in c["primary"] + c["secondary"]),
                     "source_unchanged": sha0 == g48.source_hash()}
    rep["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    rep["lock"] = {"start": lock0, "end": LOCK.read_text().strip() if LOCK.exists() else None}
    rep["loadavg"] = {"start": load0, "end": os.getloadavg()}
    (OUT / f"{name}_receipt.json").write_text(json.dumps(rep, indent=1, default=str))
    print(json.dumps({"guards": rep["guards"], **{c: {"primary": [(x["cont"], x["base"], x["report"].splitlines()[0] if x["report"] else x["err"])
                                                                   for x in v["primary"]],
                                                       "secondary": [(x["cont"], x["base"], x["report"].splitlines()[0] if x["report"] else x["err"])
                                                                     for x in v["secondary"]],
                                                       "cpu": v["cpu_total"], "maint": v["maint_cpu"],
                                                       "outcomes": v["outcomes"],
                                                       "exact": v["exact_j_equals_i"]}
                                                  for c, v in q.items()}}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
