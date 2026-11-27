"""G59 part S: padding-growth exponent (docs/G59.md §4, registered before the run).

The G57 part S protocol (benchmarks/g57_scale.py: N unrelated padding facts over 20 relations plus
N // 500 one-step padding capabilities, then a fixed 10-task workload; padding outside the timed
window; every arm snapshotted, uncharged, after padding; charged = process CPU of each workload
call, per task) at N = 0, 1000, 16000, 32000, 64000. Arms, each an in-process `serve.Server` with
--answers --bounded --lean --indexed --incremental --routed:
  r0  the 33565b0 engine itself (a clean checkout, G58 registered), in a subprocess with that
      checkout first on sys.path -- the reference for the exactness guard and the material test
  r   this commit, same flags (the G58 configuration; reported)
  rg  r with the cyclic garbage collector off in the timed window (decomposition: GC vs recall)
  k   this commit, + --partitioned (G59; includes the snapshot gc.freeze of docs/G59.md §2d)
Guards: at every (seed, N) the r and k reply streams equal r0's, and the final state bytes of r and k
equal r0's; the workload is answered identically at every N; no snapshot in the timed window.
Each (seed, N, arm) result is written to disk when it finishes.
Run: python3 benchmarks/g59_scale.py [--out g59_scale] [--seeds 291,...] [--sizes 0,...]
"""
from __future__ import annotations
import hashlib
import json
import math
import os
import random
import subprocess
import sys
import tempfile
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF_ROOT = Path(os.environ.get("G59_REF_ROOT", "/workspace/PacketLM-33565b0"))
REF_HEAD = "33565b0"
FLAGS = ["--answers", "--bounded", "--lean", "--indexed", "--incremental", "--routed"]
ARMS = {"r0": [], "r": [], "rg": [], "k": ["--partitioned"]}
REGISTERED_ARMS = ["r0", "r", "k"]  # rg (GC decomposition) is optional, not in the registered run (time)
GC_OFF = {"rg"}  # rg: r with the cyclic collector off in the timed window (decomposition only, docs/G59.md §4)
SEEDS = [291, 292, 293, 294, 295, 296, 297]
SIZES = [0, 1000, 16000, 32000, 64000]
TASKS = 10
RATIO = 1.0  # registered (docs/G59.md §2e): the proportional policy's journal/snapshot ratio
BOUND = 0.2  # registered: bounded iff the upper 95% CI of alpha_k(16000 -> 64000) < 0.2
HARNESS = ["benchmarks/g59_scale.py", "benchmarks/g57_scale.py", "benchmarks/g59_registered.sh"]
LOCK = Path("/workspace/REGISTERED_RUN.lock")


def run_one(seed, n, arm, tasks):
    """One arm run in this process (the packetlm first on sys.path is the arm's engine)."""
    from packetlm import serve
    import g57_scale
    rng = random.Random(seed * 100003 + n)
    facts, caps = g57_scale.padding(rng, n)
    work = g57_scale.workload(random.Random(seed), tasks)
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
        snap_bytes = p.stat().st_size
        if arm in GC_OFF:
            import gc
            gc.collect()  # uncharged, like the padding
            gc.disable()
        work_calls = _work_calls(srv, p, flags, work)  # a forked copy counts function calls (uncharged)
        j0 = srv.cur.jfh.tell()
        per, stream, known = [0.0] * tasks, hashlib.sha256(), 0
        for t, lines in work:
            c0 = time.process_time()
            r = srv.call(p, flags, lines)["replies"]
            per[t] += time.process_time() - c0
            stream.update(json.dumps([lines, r]).encode())
            known += sum(1 for x in r if " wc" in x and "unknown" not in x and "ambiguous" not in x)
        if arm in GC_OFF:
            gc.enable()
        in_window = srv.cur.since < snaps0
        jbytes = srv.cur.jfh.tell() - j0
        journaled = srv.cur.since
        c0 = time.process_time()
        srv._snapshot(srv.cur)  # measured, not charged
        snap = time.process_time() - c0
        paths = dict(srv.cur.memo.counts) if srv.cur is not None and srv.cur.memo is not None else {}
        srv.close()
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
    return {"seed": seed, "n": n, "arm": arm, "pad_facts": len(facts), "pad_caps": len(caps), "pad_cpu_s": round(pad, 4),
            "task_cpu_s": [round(x, 6) for x in per], "mean_task_cpu_s": round(sum(per) / tasks, 6),
            "reply_stream_sha256": stream.hexdigest(), "state_sha256": sha, "known": known, "paths": paths,
            "snapshot_cpu_s": round(snap, 5), "snapshot_in_window": in_window, "journaled_calls": journaled,
            "amort_task_cpu_s": round(sum(per) / tasks + journaled / tasks / 64 * snap, 6),
            # G59 §4 (Med of verify-33565b0): maintenance charged. Fixed policy: one snapshot (which is also
            # the full validation, run once) per 64 journaled calls. Proportional policy (serve
            # PACKETLM_SNAPSHOT_RATIO = RATIO): one per max(64, RATIO x snapshot bytes / journal bytes per call)
            "journal_bytes": jbytes, "snapshot_bytes": snap_bytes, "work_calls": work_calls,
            "charged_fixed_cpu_s": round(sum(per) / tasks + journaled / tasks * snap / 64, 6),
            "charged_prop_cpu_s": round(sum(per) / tasks + journaled / tasks * snap
                                        / max(64, RATIO * snap_bytes / max(jbytes / max(journaled, 1), 1)), 6)}


def _work_calls(srv, p, flags, work):
    """Work in operations: the number of Python and C function calls the workload makes, counted in a
    forked copy of this process (the copy journals to a scratch file and exits without writing the
    state), so the timed run is unaffected. Deterministic for a given state and workload."""
    r, w = os.pipe()
    pid = os.fork()
    if pid == 0:
        try:
            os.close(r)
            srv.cur.jfh = open(str(p) + ".workjournal", "ab")
            n = [0]

            def prof(frame, event, arg):
                if event in ("call", "c_call"):
                    n[0] += 1
            sys.setprofile(prof)
            for _, lines in work:
                srv.call(p, flags, lines)
            sys.setprofile(None)
            os.write(w, str(n[0]).encode())
        finally:
            os._exit(0)
    os.close(w)
    got = b""
    while True:
        b = os.read(r, 64)
        if not b:
            break
        got += b
    os.close(r)
    os.waitpid(pid, 0)
    return int(got) if got else None


def job(args):
    seed, n, arm, tasks, out = args
    if arm == "r0":  # the 33565b0 engine in its own process, its checkout first on sys.path
        code = ("import sys, json; sys.path[:0] = [%r, %r]; sys.path.insert(2, %r); import g59_scale as h; "
                "print(json.dumps(h.run_one(%d, %d, 'r0', %d)))"
                % (str(REF_ROOT), str(REF_ROOT / "benchmarks"), str(ROOT / "benchmarks"), seed, n, tasks))
        p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd="/tmp")
        if p.returncode:
            raise RuntimeError(p.stderr[-800:])
        res = json.loads(p.stdout.strip().splitlines()[-1])
    else:
        res = run_one(seed, n, arm, tasks)
    (Path(out) / f"s{seed}_n{n}_{arm}.json").write_text(json.dumps(res))  # incremental
    return res


def boot(vals, reps=5000, seed=0):
    rng = random.Random(seed)
    m = sorted(sum(rng.choice(vals) for _ in vals) / len(vals) for _ in range(reps))
    return round(sum(vals) / len(vals), 4), [round(m[int(0.025 * reps)], 4), round(m[int(0.975 * reps) - 1], 4)]


def alpha(ratios, n1, n2):
    """Exponent from per-seed growth ratios T(n2)/T(n1): ln(bootstrap mean ratio) / ln(n2/n1), CI
    transformed from the ratio's percentile CI (monotone)."""
    m, (lo, hi) = boot(ratios)
    f = math.log(n2 / n1)
    return round(math.log(m) / f, 4), [round(math.log(lo) / f, 4), round(math.log(hi) / f, 4)], {"ratio": [m, [lo, hi]]}


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
    arms = argv[argv.index("--arms") + 1].split(",") if "--arms" in argv else list(REGISTERED_ARMS)
    name = argv[argv.index("--out") + 1] if "--out" in argv else "g59_scale"
    out = ROOT / "artifacts" / name
    out.mkdir(parents=True, exist_ok=True)
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    prov0 = provenance()
    jobs = [(s, n, a, tasks, str(out)) for n in sorted(sizes, reverse=True) for s in seeds for a in arms]
    res = []
    with Pool(int(os.environ.get("G59_WORKERS", "4"))) as pool:
        for r in pool.imap_unordered(job, jobs):
            res.append(r)
            with open(out / "progress.jsonl", "a") as fh:
                fh.write(json.dumps({k: r[k] for k in ("seed", "n", "arm", "mean_task_cpu_s", "pad_cpu_s", "state_sha256")}
                                    | {"at": time.strftime("%H:%M:%S")}) + "\n")
    R = {(r["seed"], r["n"], r["arm"]): r for r in res}
    rep = {"started": started, "finished": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "seeds": seeds, "sizes": sizes,
           "tasks": tasks, "arms": arms, "provenance_start": prov0, "provenance_end": provenance(), "runs": res}
    rep["source_unchanged"] = prov0["source_sha256"] == rep["provenance_end"]["source_sha256"]
    ref = "r0" if "r0" in arms else "r" if "r" in arms else arms[0]
    rep["guard_ref_is_33565b0"] = prov0["ref_head"].startswith(REF_HEAD) and prov0["ref_clean"]
    rep["guard_replies_equal_ref"] = all(R[(s, n, a)]["reply_stream_sha256"] == R[(s, n, ref)]["reply_stream_sha256"]
                                         for s in seeds for n in sizes for a in arms)
    rep["guard_state_equal_ref"] = all(R[(s, n, a)]["state_sha256"] == R[(s, n, ref)]["state_sha256"]
                                       for s in seeds for n in sizes for a in arms)
    rep["guard_workload_answered"] = all(R[(s, n, a)]["known"] == R[(s, sizes[0], a)]["known"] for s in seeds for n in sizes for a in arms)
    rep["guard_no_snapshot_in_window"] = not any(r["snapshot_in_window"] for r in res)
    summ = {}
    for a in arms:
        S = summ[a] = {"mean_task_cpu_ms": {n: round(1000 * sum(R[(s, n, a)]["mean_task_cpu_s"] for s in seeds) / len(seeds), 3) for n in sizes},
                       "pad_cpu_s": {n: round(sum(R[(s, n, a)]["pad_cpu_s"] for s in seeds) / len(seeds), 3) for n in sizes},
                       "snapshot_cpu_ms": {n: round(1000 * sum(R[(s, n, a)]["snapshot_cpu_s"] for s in seeds) / len(seeds), 3) for n in sizes}}
        big = [n for n in sizes if n >= 16000]
        for i, n1 in enumerate(big):
            for n2 in big[i + 1:]:
                S[f"alpha_{n1}_{n2}"] = alpha([R[(s, n2, a)]["mean_task_cpu_s"] / R[(s, n1, a)]["mean_task_cpu_s"] for s in seeds], n1, n2)
                S[f"alpha_amort_{n1}_{n2}"] = alpha([R[(s, n2, a)]["amort_task_cpu_s"] / R[(s, n1, a)]["amort_task_cpu_s"] for s in seeds], n1, n2)
                S[f"alpha_snapshot_{n1}_{n2}"] = alpha([R[(s, n2, a)]["snapshot_cpu_s"] / R[(s, n1, a)]["snapshot_cpu_s"] for s in seeds], n1, n2)
                S[f"alpha_charged_fixed_{n1}_{n2}"] = alpha([R[(s, n2, a)]["charged_fixed_cpu_s"] / R[(s, n1, a)]["charged_fixed_cpu_s"] for s in seeds], n1, n2)
                S[f"alpha_charged_prop_{n1}_{n2}"] = alpha([R[(s, n2, a)]["charged_prop_cpu_s"] / R[(s, n1, a)]["charged_prop_cpu_s"] for s in seeds], n1, n2)
                if all(R[(s, n, a)]["work_calls"] for s in seeds for n in (n1, n2)):
                    S[f"alpha_work_{n1}_{n2}"] = alpha([R[(s, n2, a)]["work_calls"] / R[(s, n1, a)]["work_calls"] for s in seeds], n1, n2)
                S[f"alpha_pad_{n1}_{n2}"] = alpha([R[(s, n2, a)]["pad_cpu_s"] / R[(s, n1, a)]["pad_cpu_s"] for s in seeds], n1, n2)
                if 0 in sizes:  # excess over the N = 0 cost (I3's form; reported)
                    ex = [(R[(s, n2, a)]["mean_task_cpu_s"] - R[(s, 0, a)]["mean_task_cpu_s"])
                          / (R[(s, n1, a)]["mean_task_cpu_s"] - R[(s, 0, a)]["mean_task_cpu_s"]) for s in seeds]
                    S[f"alpha_excess_{n1}_{n2}"] = alpha(ex, n1, n2) if min(ex) > 0 else ("undefined", ex)
        for n in sizes:
            if n and 0 in sizes:
                S[f"R0_{n}"] = boot([R[(s, n, a)]["mean_task_cpu_s"] / R[(s, 0, a)]["mean_task_cpu_s"] for s in seeds])
            if n > 1000 and 1000 in sizes:
                S[f"R1k_{n}"] = boot([R[(s, n, a)]["mean_task_cpu_s"] / R[(s, 1000, a)]["mean_task_cpu_s"] for s in seeds])
    rep["summary"] = summ
    if "k" in arms and 16000 in sizes and 64000 in sizes:
        ak = summ["k"]["alpha_16000_64000"]
        rep["bounded_k"] = ak[1][1] < BOUND  # registered primary (docs/G59.md §4)
        rep["bounded_charged_k"] = summ["k"]["alpha_charged_prop_16000_64000"][1][1] < BOUND  # registered co-primary
        if "alpha_work_16000_64000" in summ["k"]:
            rep["bounded_work_k"] = summ["k"]["alpha_work_16000_64000"][1][1] < BOUND  # secondary
        rep["bounded_charged_fixed_k"] = summ["k"]["alpha_charged_fixed_16000_64000"][1][1] < BOUND  # secondary
        if ref in summ and ref != "k":
            # registered anti-circling stop rule: k's growth ratio 16k -> 64k (upper CI) at most half of r0's point
            rep["material_k_vs_ref"] = ak[2]["ratio"][1][1] <= summ[ref]["alpha_16000_64000"][2]["ratio"][0] / 2
            rep["snapshot_material_k_vs_ref"] = summ["k"]["snapshot_cpu_ms"][64000] <= summ[ref]["snapshot_cpu_ms"][64000] / 2
    (out / f"{name}_receipt.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k != "runs"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
