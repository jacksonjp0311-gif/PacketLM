"""G58 library-size scaling (docs/G58.md §4, registered before the run).

The state is padded with L unrelated capabilities (two-step programs over 40 padding relations,
each taught by three examples), then a fixed 10-task workload runs (each task: a 6-fact chain on its
own relation, an example call — compositional for t > 0 —, two `complete` calls, two question calls).
Arms, every one in-process `serve.Server` with --answers --bounded --lean --deepen=5:
  j0  the 8994490 engine itself (a clean checkout at 8994490, `--indexed --incremental`), run in a
      subprocess with that checkout first on sys.path -- the stop rule's reference
  j   this commit, --indexed --incremental (the 8994490 configuration; reported)
  r   this commit, --indexed --incremental --routed (G58)
Padding and its acquisitions are outside the timed window; every arm is snapshotted (uncharged)
after padding. Charged: process CPU of each workload call, per task. Each (seed, L, arm) result is
written to disk when it finishes.
Guards: at every (seed, L) the j and r reply streams equal j0's, and the final state bytes of j and r
equal j0's.
Run: python3 benchmarks/g58_libscale.py [--out g58_libscale] [--seeds 261,...] [--sizes 0,64,256,1024]
"""
from __future__ import annotations
import hashlib
import json
import os
import random
import subprocess
import sys
import tempfile
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF_ROOT = Path(os.environ.get("G58_REF_ROOT", "/workspace/PacketLM"))  # the 8994490 checkout
REF_HEAD = "8994490"
FLAGS = ["--answers", "--bounded", "--lean", "--deepen=5", "--indexed", "--incremental"]
ARMS = {"j0": [], "j": [], "r": ["--routed"]}
SEEDS = [261, 262, 263, 264, 265, 266, 267]
SIZES = [0, 64, 256, 1024]
TASKS = 10
BASE_L = 64
HARNESS = ["benchmarks/g58_libscale.py", "benchmarks/g58_registered.sh"]
LOCK = Path("/workspace/REGISTERED_RUN.lock")


def lib_padding(rng, L):
    """L unrelated capabilities: two-step programs over 40 padding relations, taught by examples."""
    facts, caps = [], []
    for c in range(L):
        r1, r2 = f"pr{rng.randrange(40)}", f"pr{rng.randrange(40)}"
        ex = []
        for k in range(3):
            a, b, o = f"pc{c}_{k}", f"pc{c}_{k}m", f"pc{c}_{k}o"
            facts += [f"fact {a} {r1} {b}", f"fact {b} {r2} {o}"]
            ex.append(f"example pcap{c}: {a} -> {o}")
        caps.append(ex)
    return facts, caps

def workload(rng, tasks):
    calls = []
    for t in range(tasks):
        rel = f"w{t}"
        ents = [f"t{t}e{k}" for k in range(7)]
        calls.append((t, [f"fact {ents[k]} {rel} {ents[k + 1]}" for k in range(6)]))
        if t == 0:
            calls.append((t, [f"example wc{t}: {ents[k]} -> {ents[k + 1]}" for k in range(3)]))
        else:  # compositional: this task's relation then the previous task's capability's relation? (two-step over w{t})
            calls.append((t, [f"example wc{t}: {ents[k]} -> {ents[k + 2]}" for k in range(3)]))
        calls.append((t, [f"complete {ents[0]}"]))
        u = rng.randrange(t + 1)
        calls.append((t, [f"complete t{u}e{rng.randrange(3)}"]))
        for _ in range(2):
            qs = []
            for _ in range(6):
                u = rng.randrange(t + 1)
                qs.append(f"what is t{u}e{rng.randrange(5)} wc{u}")
            calls.append((t, qs))
    return calls


def run_one(seed, L, arm, tasks):
    """One arm run in this process (the packetlm on sys.path is the arm's engine)."""
    from packetlm import serve
    rng = random.Random(seed * 7919 + L)
    facts, caps = lib_padding(rng, L)
    work = workload(random.Random(seed), tasks)
    flags = FLAGS + ARMS[arm]
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "s.json"
        srv = serve.Server()
        t0 = time.process_time()
        for k in range(0, len(facts), 2000):
            srv.call(p, flags, facts[k:k + 2000])
        for ex in caps:
            srv.call(p, flags, ex)
        if srv.cur is None:
            srv.call(p, flags, [])
        srv._snapshot(srv.cur)
        pad = time.process_time() - t0
        snaps0 = srv.cur.since
        per, stream, known = [0.0] * tasks, hashlib.sha256(), 0
        for t, lines in work:
            c0 = time.process_time()
            r = srv.call(p, flags, lines)["replies"]
            per[t] += time.process_time() - c0
            stream.update(json.dumps([lines, r]).encode())
            known += sum(1 for x in r if " wc" in x and "unknown" not in x and "ambiguous" not in x)
        in_window = srv.cur.since < snaps0
        journaled = srv.cur.since
        c0 = time.process_time()
        srv._snapshot(srv.cur)  # measured, not charged
        snap = time.process_time() - c0
        paths = dict(srv.cur.memo.counts) if srv.cur is not None and srv.cur.memo is not None else {}
        srv.close()
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
    return {"seed": seed, "L": L, "arm": arm, "pad_caps": len(caps), "pad_cpu_s": round(pad, 4),
            "task_cpu_s": [round(x, 5) for x in per], "mean_task_cpu_s": round(sum(per) / tasks, 6),
            "reply_stream_sha256": stream.hexdigest(), "state_sha256": sha, "known": known, "paths": paths,
            "snapshot_cpu_s": round(snap, 5), "snapshot_in_window": in_window, "journaled_calls": journaled,
            "amort_task_cpu_s": round(sum(per) / tasks + journaled / tasks / 64 * snap, 6)}


def job(args):
    seed, L, arm, tasks, out = args
    if arm == "j0":  # the 8994490 engine, in its own process with its checkout first on sys.path
        code = ("import sys, json; sys.path[:0] = [%r]; sys.path.insert(1, %r); import g58_libscale as h; "
                "print(json.dumps(h.run_one(%d, %d, 'j0', %d)))" % (str(REF_ROOT), str(ROOT / "benchmarks"), seed, L, tasks))
        p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd="/tmp")
        if p.returncode:
            raise RuntimeError(p.stderr[-800:])
        res = json.loads(p.stdout.strip().splitlines()[-1])
    else:
        res = run_one(seed, L, arm, tasks)
    (Path(out) / f"s{seed}_L{L}_{arm}.json").write_text(json.dumps(res))  # incremental
    return res


def boot(vals, reps=5000, seed=0):
    rng = random.Random(seed)
    m = sorted(sum(rng.choice(vals) for _ in vals) / len(vals) for _ in range(reps))
    return round(sum(vals) / len(vals), 4), [round(m[int(0.025 * reps)], 4), round(m[int(0.975 * reps) - 1], 4)]


def provenance():
    git = lambda root, *a: subprocess.run(["git", *a], cwd=root, capture_output=True, text=True).stdout.strip()  # noqa: E731
    sys.path.insert(0, str(ROOT / "benchmarks"))
    import g48
    return {"head": git(ROOT, "rev-parse", "HEAD"), "git_status_porcelain": git(ROOT, "status", "--porcelain"),
            "source_sha256": g48.source_hash(), "engine_sha256": g48.engine_hash(),
            "harness_sha256": hashlib.sha256(b"".join((ROOT / f).read_bytes() for f in HARNESS)).hexdigest(),
            "ref_root": str(REF_ROOT), "ref_head": git(REF_ROOT, "rev-parse", "HEAD"),
            "ref_clean": git(REF_ROOT, "status", "--porcelain") == "",
            "lock": LOCK.read_text().strip() if LOCK.exists() else None, "loadavg": os.getloadavg(),
            "at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}


def main(argv):
    get = lambda f, d: [int(x) for x in argv[argv.index(f) + 1].split(",")] if f in argv else d  # noqa: E731
    seeds, sizes = get("--seeds", SEEDS), get("--sizes", SIZES)
    tasks = get("--tasks", [TASKS])[0]
    name = argv[argv.index("--out") + 1] if "--out" in argv else "g58_libscale"
    out = ROOT / "artifacts" / name
    out.mkdir(parents=True, exist_ok=True)
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    prov0 = provenance()
    jobs = [(s, n, a, tasks, str(out)) for n in sorted(sizes, reverse=True) for s in seeds for a in ARMS]
    res = []
    with Pool(8) as pool:
        for r in pool.imap_unordered(job, jobs):
            res.append(r)
            with open(out / "progress.jsonl", "a") as fh:
                fh.write(json.dumps({k: r[k] for k in ("seed", "L", "arm", "mean_task_cpu_s", "state_sha256")}) + "\n")
    R = {(r["seed"], r["L"], r["arm"]): r for r in res}
    rep = {"started": started, "finished": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "seeds": seeds, "sizes": sizes,
           "tasks": tasks, "provenance_start": prov0, "provenance_end": provenance(), "runs": res}
    rep["source_unchanged"] = prov0["source_sha256"] == rep["provenance_end"]["source_sha256"]
    rep["guard_ref_is_8994490"] = prov0["ref_head"].startswith(REF_HEAD) and prov0["ref_clean"]
    rep["guard_replies_equal_j0"] = all(R[(s, n, a)]["reply_stream_sha256"] == R[(s, n, "j0")]["reply_stream_sha256"]
                                        for s in seeds for n in sizes for a in ("j", "r"))
    rep["guard_state_equal_j0"] = all(R[(s, n, a)]["state_sha256"] == R[(s, n, "j0")]["state_sha256"]
                                      for s in seeds for n in sizes for a in ("j", "r"))
    rep["guard_workload_answered"] = all(R[(s, n, a)]["known"] == R[(s, 0, a)]["known"] for s in seeds for n in sizes for a in ARMS)
    rep["guard_no_snapshot_in_window"] = not any(r["snapshot_in_window"] for r in res)
    lmax = max(sizes)
    summ = {}
    for a in ARMS:
        summ[a] = {"mean_task_cpu_ms": {n: round(1000 * sum(R[(s, n, a)]["mean_task_cpu_s"] for s in seeds) / len(seeds), 3) for n in sizes},
                   "pad_cpu_s": {n: round(sum(R[(s, n, a)]["pad_cpu_s"] for s in seeds) / len(seeds), 3) for n in sizes},
                   "snapshot_cpu_ms": {n: round(1000 * sum(R[(s, n, a)]["snapshot_cpu_s"] for s in seeds) / len(seeds), 3) for n in sizes}}
        for n in sizes:
            if n:
                summ[a][f"R0_{n}"] = boot([R[(s, n, a)]["mean_task_cpu_s"] / R[(s, 0, a)]["mean_task_cpu_s"] for s in seeds])
            if n > BASE_L:
                summ[a][f"R{BASE_L}_{n}"] = boot([R[(s, n, a)]["mean_task_cpu_s"] / R[(s, BASE_L, a)]["mean_task_cpu_s"] for s in seeds])
                summ[a][f"R{BASE_L}_amort_{n}"] = boot([R[(s, n, a)]["amort_task_cpu_s"] / R[(s, BASE_L, a)]["amort_task_cpu_s"] for s in seeds])
    rep["summary"] = summ
    # registered (docs/G58.md §4): material iff Xr's growth ratio is at most half of the 8994490 engine's,
    # against both baselines (upper 95% CI of Xr <= half of j0's point estimate); else stop and report
    rep["material_vs_L64"] = summ["r"][f"R{BASE_L}_{lmax}"][1][1] <= summ["j0"][f"R{BASE_L}_{lmax}"][0] / 2
    rep["material_vs_L0"] = summ["r"][f"R0_{lmax}"][1][1] <= summ["j0"][f"R0_{lmax}"][0] / 2
    rep["material"] = rep["material_vs_L64"] and rep["material_vs_L0"]
    rep["flat_r"] = summ["r"][f"R{BASE_L}_{lmax}"][1][1] <= 1.25  # registered flatness threshold
    rep["flat_r_vs_L0"] = summ["r"][f"R0_{lmax}"][1][1] <= 1.25  # reported
    (out / f"{name}_receipt.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k != "runs"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
