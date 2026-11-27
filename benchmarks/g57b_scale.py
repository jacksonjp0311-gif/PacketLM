"""G57b part S: the G57 part S protocol (benchmarks/g57_scale.py: padding, workload, charging,
bootstrap unchanged) on fresh seeds, with a third arm. Registered in docs/G57b.md.
Arms: Xs (reference), Xi (--indexed, the G57 engine), Xj (--indexed --incremental, G57b).
Guards: at every (seed, N) the Xj and Xi reply streams equal the Xs stream, and the final state
file bytes of Xj equal those of Xi. Each (seed, N, arm) result is written to disk when it finishes.
verify-35bda6b: Low 1 — rule F's baseline is N = 1000 (every padding relation present; N = 0 lacks
them), and R against N = 0 is also reported; Low 3 — every arm is snapshotted (uncharged) after
padding, the 50 workload calls stay below the 64-call interval so no arm snapshots in the timed
window, and a final snapshot's CPU is measured and reported separately (`snapshot_cpu_s`); Low 2 —
the receipt records HEAD, the clean-tree status, source and engine hashes, and the lock file.
Run: python3 benchmarks/g57b_scale.py [--out g57b_scale] [--seeds 231,...] [--sizes 0,...] [--tasks 10]
"""
from __future__ import annotations
import hashlib
import json
import os
import subprocess
import random
import sys
import tempfile
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))
from packetlm import serve  # noqa: E402
from g57_scale import padding, workload, boot, FLAGS  # noqa: E402
import g48  # noqa: E402

LOCK = Path("/workspace/REGISTERED_RUN.lock")


def provenance():
    git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()  # noqa: E731
    return {"head": git("rev-parse", "HEAD"), "git_status_porcelain": git("status", "--porcelain"),
            "source_sha256": g48.source_hash(), "engine_sha256": g48.engine_hash(),
            "harness_sha256": hashlib.sha256(b"".join((ROOT / f).read_bytes() for f in HARNESS)).hexdigest(),
            "lock": LOCK.read_text().strip() if LOCK.exists() else None, "loadavg": os.getloadavg(),
            "at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}

SEEDS = [231, 232, 233, 234, 235, 236, 237]
SIZES = [0, 1000, 4000, 16000]
TASKS = 10
ARMS = {"s": [], "i": ["--indexed"], "j": ["--indexed", "--incremental"]}
BASE_N = 1000
MATERIAL = 91.9 / 2  # registered: Xj's R_16000 upper CI bound must be <= half of G57 Xi's R_16000 (91.9)
# registered (finalization, before any G57b registered run): the same halving test against the N = 1000
# baseline. G57 Xi's comparable value, computed from the published G57 part S files
# (docs/evidence/g57/scale, seeds 221-227, same boot): R1k_16000 = 17.8296 [17.3312, 18.4131].
G57_R1K_16000 = 17.8296
MATERIAL_1K = G57_R1K_16000 / 2
HARNESS = ["benchmarks/g57b_scale.py", "benchmarks/g57_scale.py", "benchmarks/g57b_registered.sh"]


def job(args):
    seed, n, arm, tasks, out = args
    rng = random.Random(seed * 100003 + n)
    facts, caps = padding(rng, n)
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
        if srv.cur is None:  # N = 0: open the path outside the timed window too
            srv.call(p, flags, [])
        srv._snapshot(srv.cur)  # Low 3: every arm starts the timed window just after a snapshot
        pad = time.process_time() - t0
        snaps0 = srv.cur.since
        per, stream, replies = [0.0] * tasks, hashlib.sha256(), []
        for t, lines in work:
            c0 = time.process_time()
            r = srv.call(p, flags, lines)["replies"]
            per[t] += time.process_time() - c0
            stream.update(json.dumps([lines, r]).encode())
            replies.append(r)
        in_window_snapshot = srv.cur.since < snaps0 or srv.cur.since == 0
        journaled = srv.cur.since
        c0 = time.process_time()
        srv._snapshot(srv.cur)  # measured, not charged to the tasks
        snap = time.process_time() - c0
        paths = dict(srv.cur.memo.counts) if srv.cur is not None and srv.cur.memo is not None else {}
        srv.close()
        state_sha = hashlib.sha256(p.read_bytes()).hexdigest()
    res = {"seed": seed, "n": n, "arm": arm, "pad_facts": len(facts), "pad_caps": len(caps), "pad_cpu_s": round(pad, 4),
           "task_cpu_s": [round(x, 5) for x in per], "mean_task_cpu_s": round(sum(per) / tasks, 5),
           "reply_stream_sha256": stream.hexdigest(), "state_sha256": state_sha, "paths": paths,
           "snapshot_cpu_s": round(snap, 5), "snapshot_in_window": in_window_snapshot, "journaled_calls": journaled,
           # amortized: each journaled call carries 1/64 of a snapshot (a full validation for Xj)
           "amort_task_cpu_s": round(sum(per) / tasks + journaled / tasks / serve.SNAPSHOT_EVERY * snap, 5),
           "known": sum(1 for r in replies for x in r if " wc" in x and "unknown" not in x and "ambiguous" not in x)}
    (Path(out) / f"s{seed}_n{n}_{arm}.json").write_text(json.dumps(res))  # incremental
    return res


def main(argv):
    get = lambda f, d: [int(x) for x in argv[argv.index(f) + 1].split(",")] if f in argv else d  # noqa: E731
    seeds, sizes = get("--seeds", SEEDS), get("--sizes", SIZES)
    tasks = get("--tasks", [TASKS])[0]
    name = argv[argv.index("--out") + 1] if "--out" in argv else "g57b_scale"
    out = ROOT / "artifacts" / name
    out.mkdir(parents=True, exist_ok=True)
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    prov0 = provenance()
    jobs = [(s, n, a, tasks, str(out)) for n in sorted(sizes, reverse=True) for s in seeds for a in ARMS]
    with Pool(8) as pool:
        res = list(pool.imap_unordered(job, jobs))
    R = {(r["seed"], r["n"], r["arm"]): r for r in res}
    rep = {"started": started, "finished": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "seeds": seeds, "sizes": sizes,
           "tasks": tasks, "provenance_start": prov0, "provenance_end": provenance(), "runs": res}
    rep["source_unchanged"] = prov0["source_sha256"] == rep["provenance_end"]["source_sha256"]
    rep["guard_replies_equal_s"] = all(R[(s, n, a)]["reply_stream_sha256"] == R[(s, n, "s")]["reply_stream_sha256"]
                                       for s in seeds for n in sizes for a in "ij")
    rep["guard_state_j_equals_i"] = all(R[(s, n, "j")]["state_sha256"] == R[(s, n, "i")]["state_sha256"] for s in seeds for n in sizes)
    rep["guard_workload_answered"] = all(R[(s, n, a)]["known"] == R[(s, 0, a)]["known"] for s in seeds for n in sizes for a in ARMS)
    rep["guard_no_snapshot_in_window"] = not any(r["snapshot_in_window"] for r in res)
    nmax = max(sizes)
    summ = {}
    for a in ARMS:
        summ[a] = {"mean_task_cpu_ms": {n: round(1000 * sum(R[(s, n, a)]["mean_task_cpu_s"] for s in seeds) / len(seeds), 3)
                                        for n in sizes},
                   "pad_cpu_s": {n: round(sum(R[(s, n, a)]["pad_cpu_s"] for s in seeds) / len(seeds), 3) for n in sizes}}
        summ[a]["snapshot_cpu_ms"] = {n: round(1000 * sum(R[(s, n, a)]["snapshot_cpu_s"] for s in seeds) / len(seeds), 3)
                                      for n in sizes}
        for n in sizes:
            if n:  # against N = 0 (G57's form)
                summ[a][f"R_{n}"] = boot([R[(s, n, a)]["mean_task_cpu_s"] / R[(s, 0, a)]["mean_task_cpu_s"] for s in seeds])
            if n > BASE_N:  # amortized snapshot/full-validation cost included (reported)
                summ[a][f"R1k_amort_{n}"] = boot([R[(s, n, a)]["amort_task_cpu_s"] / R[(s, BASE_N, a)]["amort_task_cpu_s"] for s in seeds])
            if n > BASE_N:  # registered rule F baseline (Low 1)
                summ[a][f"R1k_{n}"] = boot([R[(s, n, a)]["mean_task_cpu_s"] / R[(s, BASE_N, a)]["mean_task_cpu_s"] for s in seeds])
    rep["summary"] = summ
    rep["material_Xj_vs_N0"] = summ["j"][f"R_{nmax}"][1][1] <= MATERIAL  # registered (docs/G57b.md)
    rep["material_Xj_vs_N1000"] = summ["j"][f"R1k_{nmax}"][1][1] <= MATERIAL_1K  # registered (docs/G57b.md)
    rep["material_Xj"] = rep["material_Xj_vs_N0"] and rep["material_Xj_vs_N1000"]  # both, else stop and report
    rep["flat_Xj"] = summ["j"][f"R1k_{nmax}"][1][1] <= 1.25  # rule F on Xj, baseline N = 1000 (Low 1)
    rep["flat_Xj_vs_N0"] = summ["j"][f"R_{nmax}"][1][1] <= 1.25  # reported, G57's form
    (out / f"{name}_receipt.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k != "runs"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
