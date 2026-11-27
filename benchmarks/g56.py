"""G56: the long-lived engine protocol (docs/G56.md, registered before the run).
Same design as G54 (G50 `complete` teacher, whole-process CPU with maintenance, instrument 70297af),
same engine flags (--answers --bounded --lean; B and P add --no-library). Every arm runs twice on the
same seeds:
  Xl  the per-process protocol (one `python -m packetlm.engine` process per call; G54's accounting)
  Xs  the long-lived protocol (packetlm/serve.py: one server process per arm run, state in memory,
      journal + snapshots; B still opens a new, empty state path for every task)
for X in C (persistent, library), B (empty state per task, no library), P (persistent, no library),
F (frozen after phase A; compositional only). Control rule (03:59 decision): every arm gets the same
protocol; contrasts are taken within a protocol.
Exactness guard: every Xs reply stream equals its Xl twin's, call by call (sha256 of the stream).
Run: python3 benchmarks/g56.py [--out g56] [--dev] [--comp-seeds ...] [--unrel-seeds ...]
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
from g51 import instrument, INSTRUMENT, PIN  # noqa: E402

BASEF = {"C": ["--answers", "--bounded", "--lean"], "B": ["--answers", "--no-library", "--bounded", "--lean"],
         "P": ["--answers", "--no-library", "--bounded", "--lean"], "F": ["--answers", "--bounded", "--lean"]}
CURRICULA = {"comp": (g46.world, ["C", "B", "P", "F"]), "unrel": (g46u.world_unrelated, ["C", "B", "P"])}
# amendment 1 (docs/G56.md): 161-167 / 171-177 were consumed by the aborted first start
COMP_SEEDS = [181, 182, 183, 184, 185, 186, 187]
UNREL_SEEDS = [191, 192, 193, 194, 195, 196, 197]
HARNESS = ["benchmarks/g56.py", "benchmarks/g46.py", "benchmarks/g46u.py", "benchmarks/g51.py",
           "benchmarks/la_export.py", "benchmarks/px.py"]


class Server:
    """One long-lived engine process (python -m packetlm.serve) for one arm run."""

    def __init__(self):
        self.p = subprocess.Popen([sys.executable, "-m", "packetlm.serve"], cwd=ROOT, stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

    def req(self, **r):
        self.p.stdin.write(json.dumps(r) + "\n")
        self.p.stdin.flush()
        line = self.p.stdout.readline()
        if not line:
            raise RuntimeError("server died: " + self.p.stderr.read()[-800:])
        out = json.loads(line)
        if "error" in out:
            raise RuntimeError(out["error"])
        return out

    def stop(self):
        out = self.req(op="close")
        self.p.stdin.close()
        self.p.wait(timeout=60)
        return out


SRV = {}  # the current arm run's server, if any (one per worker process at a time)


class ServeTeacher(g46.Teacher):
    def __call__(self, *lines):
        t = time.perf_counter()
        out = SRV["s"].req(op="call", state=str(self.state), flags=self.flags, lines=list(lines))
        self.calls += 1
        self.cpu += out["cpu_s"]
        self.log.append({"lines": list(lines), "replies": out["replies"], "load": out["load"],
                         "stats": out["stats"], "cpu_s": out["cpu_s"], "cpu_total_s": out["cpu_total_s"],
                         "wall_s": round(time.perf_counter() - t, 3)})
        return out["replies"]


_file_load_state = g46.load_state


def _serve_load_state(state_path):
    """Measurement only (uncharged): the server's open state, else the snapshot on disk."""
    got = SRV["s"].req(op="inspect", state=str(state_path))
    SRV["inspect_cpu_s"] = SRV.get("inspect_cpu_s", 0.0) + got["inspect_cpu_s"]
    if got["inspected"]:
        p = Path(str(state_path) + ".inspect")
        return json.loads(p.read_text())["state"], p.stat().st_size
    return _file_load_state(state_path)


def job(args):
    cur, seed, arm, out = args
    role, proto = arm[0], arm[1]
    g46.FLAGS[role] = BASEF[role]
    g46.RICH = {role}
    g46.COMPLETE = {role}
    g46.world = CURRICULA[cur][0]
    g46.OUT = Path(out) / cur / arm  # one directory per arm: roles share g46's file names
    d = g46.OUT / f"seed{seed}"
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    stream = hashlib.sha256()
    base = ServeTeacher if proto == "s" else g46.Teacher

    class Rec(base):
        def __call__(self, *lines):
            r = super().__call__(*lines)
            stream.update(json.dumps([list(lines), r]).encode())
            return r
    orig = g46.Teacher
    g46.Teacher = Rec
    if proto == "s":
        SRV.clear()
        SRV["s"] = Server()
        g46.load_state = _serve_load_state
    try:
        r = g46.run_arm((seed, role))
        if proto == "s":
            closed = SRV["s"].stop()
            r["close_cpu_total_s"] = closed["cpu_total_s"]
            r["inspect_cpu_s"] = round(SRV.get("inspect_cpu_s", 0.0), 4)
            # the closing snapshot is charged to the run (and to the last task's maintenance bucket
            # via the last call), so whole-run CPU equals the server's whole CPU minus inspections
            r["cpu_total_all_s"] = round(r["cpu_total_all_s"] + closed["cpu_total_s"], 4)
            last_fam = [f for f in r["families"] if "cost" in f]
            if last_fam:
                last_fam[-1]["cost"]["cpu_total_s"] = round(last_fam[-1]["cost"]["cpu_total_s"] + closed["cpu_total_s"], 4)
            else:
                r["tasks"][-1]["cost"]["cpu_total_s"] = round(r["tasks"][-1]["cost"]["cpu_total_s"] + closed["cpu_total_s"], 4)
    finally:
        g46.Teacher = orig
        g46.load_state = _file_load_state
        if proto == "s" and SRV.get("s") and SRV["s"].p.poll() is None:
            SRV["s"].p.kill()
    r["arm"], r["role"], r["proto"], r["curriculum"], r["reply_stream_sha256"] = arm, role, proto, cur, stream.hexdigest()
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
    name = "g56_dev" if "--dev" in argv else (argv[argv.index("--out") + 1] if "--out" in argv else "g56")
    OUT = ROOT / "artifacts" / name
    OUT.mkdir(parents=True, exist_ok=True)
    sha0 = g48.source_hash()
    load0 = __import__("os").getloadavg()
    arms = {c: [r + p for r in roles for p in "ls"] for c, (_, roles) in CURRICULA.items()}
    jobs = [(c, s, a, str(OUT)) for c in CURRICULA for s in seeds[c] for a in arms[c]]
    jobs.sort(key=lambda j: j[2][0] not in ("B", "F"))  # long jobs first
    with Pool(8) as pool:
        res = pool.map(job, jobs)
    runs = {(r["curriculum"], r["seed"], r["arm"]): r for r in res}
    rep = {"started": started, "finished": None, "head": head, "git_status_porcelain": dirty, "harness_sha256": harness,
           "instrument": {"path": str(INSTRUMENT), "head": pin, "pinned": pin == PIN, "unmodified": idirty == ""},
           "seeds": seeds, "source_sha256": sha0, "engine_sha256": g48.engine_hash(), "curricula": {}}
    for c, (_, roles) in CURRICULA.items():
        raw = {f"{s}:{a}": {**runs[(c, s, a)], "arm": a} for s in seeds[c] for a in arms[c]}
        (OUT / f"{c}_raw.json").write_text(json.dumps(raw, default=str))
        csv = OUT / f"{c}_total.csv"
        export(raw, csv, None, "cpu_total_s")
        n = len(runs[(c, seeds[c][0], "Cs")]["tasks"])
        primary = [("Cs+maint", "Bs"), ("Cs+maint", "Ps+maint"), ("Cs+maint", "Cl+maint")]
        secondary = [("Cl+maint", "Bl"), ("Cl+maint", "Pl+maint"), ("Bs", "Bl"), ("Ps+maint", "Pl+maint"),
                     ("Cs", "Bs"), ("Cs", "Ps")]
        if "F" in roles:
            secondary += [("Cs+maint", "Fs+maint"), ("Cl+maint", "Fl+maint")]
        per = {}
        for s in seeds[c]:
            per[s] = {}
            for a in arms[c]:
                rr = runs[(c, s, a)]
                t = rr["tasks"]
                m, th = g46_th(rr) if a[0] != "B" else (None, None)
                per[s][a] = {"tasks": len(t), "solved": sum(x["correct"] == x["n_sealed"] for x in t),
                             "qualified": sum(x["status"] == "qualified" for x in t),
                             "uses_library": sum(x["uses_library"] for x in t),
                             "wrong_qualified_sealed": sum(r["wrong_qualified"] for x in t for r in x["rows"]),
                             "cpu_total_all_s": rr.get("cpu_total_all_s"), "g46_thresholds": th,
                             "reply_stream_sha256": rr["reply_stream_sha256"], "calls": rr["processes"],
                             "maint_calls": sum(f.get("cost", {}).get("processes", 0) for f in rr["families"]),
                             "maint_cpu_s": round(sum(f.get("cost", {}).get("cpu_total_s", 0) for f in rr["families"]), 4),
                             "inspect_cpu_s": rr.get("inspect_cpu_s"), "close_cpu_total_s": rr.get("close_cpu_total_s")}
        tot = {a: round(sum(per[s][a]["cpu_total_all_s"] for s in seeds[c]), 3) for a in arms[c]}
        exact = {r: all(per[s][r + "s"]["reply_stream_sha256"] == per[s][r + "l"]["reply_stream_sha256"] for s in seeds[c])
                 for r in roles}
        rep["curricula"][c] = {"n": n, "per_seed": per, "cpu_total": tot,
                               "primary": [instrument(csv, a, b, n) for a, b in primary],
                               "secondary": [instrument(csv, a, b, n) for a, b in secondary],
                               "exact_s_equals_l": exact,
                               "median_seed_ratio_Cs_Cl": sorted(per[s]["Cs"]["cpu_total_all_s"] / per[s]["Cl"]["cpu_total_all_s"]
                                                                 for s in seeds[c])[len(seeds[c]) // 2]}
    q = rep["curricula"]
    rep["guards"] = {"exact_replies_s_equal_l": all(all(v["exact_s_equals_l"].values()) for v in q.values()),
                     "no_wrong_qualified_C": all(v[a]["wrong_qualified_sealed"] == 0 for c in q.values()
                                                 for v in c["per_seed"].values() for a in ("Cl", "Cs")),
                     "instrument_pinned_unmodified": rep["instrument"]["pinned"] and rep["instrument"]["unmodified"],
                     "all_reports_ran": all(x["rc"] == 0 for c in q.values() for x in c["primary"] + c["secondary"]),
                     "source_unchanged": sha0 == g48.source_hash()}
    rep["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    rep["loadavg"] = {"start": load0, "end": __import__("os").getloadavg()}
    (OUT / f"{name}_receipt.json").write_text(json.dumps(rep, indent=1, default=str))
    print(json.dumps({"guards": rep["guards"], **{c: {"primary": [(x["cont"], x["base"], x["report"].splitlines()[0] if x["report"] else x["err"])
                                                                   for x in v["primary"]],
                                                       "secondary": [(x["cont"], x["base"], x["report"].splitlines()[0] if x["report"] else x["err"])
                                                                     for x in v["secondary"]],
                                                       "cpu": v["cpu_total"], "exact": v["exact_s_equals_l"]}
                                                  for c, v in q.items()}}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
