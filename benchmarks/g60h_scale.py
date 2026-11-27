"""G60H part S: padding-growth exponent of the HDC engine (docs/G60H.md §4, registered before the run).

The G59 part S protocol (benchmarks/g59_scale.py, g57_scale padding and workload: N unrelated padding
facts over 20 relations plus N // 500 one-step padding capabilities, then a fixed 10-task workload;
padding and one snapshot outside the timed window, uncharged; charged = process CPU of each workload
call, per task) at N = 0, 1000, 16000, 32000, 64000, with the HDC long-lived server in process
(packetlm/hdc/serve.py). Arms: hC (learner flags), hP (--no-library). Work = Python+C function calls of
the workload, counted in a forked copy (uncharged); engine work counters (row_ops, evaluations,
cleanup checks) reported too. Guard: the workload is answered identically at every N.
Run: python3 benchmarks/g60h_scale.py [--out g60h_scale] [--seeds ...] [--sizes ...]
"""
from __future__ import annotations
import hashlib
import json
import os
import random
import sys
import tempfile
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT))
import g57_scale  # noqa: E402
from g59_scale import boot, alpha  # noqa: E402

FLAGS = {"hC": ["--answers", "--bounded", "--lean"], "hP": ["--answers", "--bounded", "--lean", "--no-library"]}
SEEDS = [451, 452, 453, 454, 455, 456, 457]  # fresh (docs/G60H.md §4); dev seeds 98x
SIZES = [0, 1000, 16000, 32000, 64000]
TASKS = 10
RATIO = 1.0
BOUND = 0.2
LOCK = Path("/workspace/REGISTERED_RUN.lock")


def run_one(seed, n, arm, tasks=TASKS):
    from packetlm.hdc import serve
    rng = random.Random(seed * 100003 + n)
    facts, caps = g57_scale.padding(rng, n)
    work = g57_scale.workload(random.Random(seed), tasks)
    flags = FLAGS[arm]
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
        srv._snapshot()
        pad = time.process_time() - t0
        snap_bytes = p.stat().st_size
        work_calls = _work_calls(srv, p, flags, work)
        j0 = srv.cur["jfh"].tell()
        per, stream, known = [0.0] * tasks, hashlib.sha256(), 0
        eng_work = {"row_ops": 0, "evaluations": 0, "executions": 0, "cleanup_checks": 0}
        for t, lines in work:
            c0 = time.process_time()
            out = srv.call(p, flags, lines)
            per[t] += time.process_time() - c0
            r = out["replies"]
            for k_ in eng_work:
                eng_work[k_] += out["stats"].get(k_, 0)
            stream.update(json.dumps([lines, r]).encode())
            known += sum(1 for x in r if " wc" in x and "unknown" not in x and "ambiguous" not in x)
        in_window = srv.cur["since"] < len(work)
        jbytes = srv.cur["jfh"].tell() - j0
        journaled = srv.cur["since"]
        c0 = time.process_time()
        srv._snapshot()
        snap = time.process_time() - c0
        counters = dict(srv.cur["eng"].counters)
        n_ent = len(srv.cur["eng"].ent.code)
        n_keys = len(srv.cur["eng"].facts)
        srv.close()
    return {"seed": seed, "n": n, "arm": arm, "pad_facts": len(facts), "pad_caps": len(caps), "pad_cpu_s": round(pad, 4),
            "task_cpu_s": [round(x, 6) for x in per], "mean_task_cpu_s": round(sum(per) / tasks, 6),
            "reply_stream_sha256": stream.hexdigest(), "known": known, "engine_work": eng_work,
            "snapshot_cpu_s": round(snap, 5), "snapshot_in_window": in_window, "journaled_calls": journaled,
            "journal_bytes": jbytes, "snapshot_bytes": snap_bytes, "work_calls": work_calls,
            "entities": n_ent, "fact_keys": n_keys, "hdc_counters": counters,
            "charged_fixed_cpu_s": round(sum(per) / tasks + journaled / tasks * snap / 64, 6),
            "charged_prop_cpu_s": round(sum(per) / tasks + journaled / tasks * snap
                                        / max(64, RATIO * snap_bytes / max(jbytes / max(journaled, 1), 1)), 6)}


def _work_calls(srv, p, flags, work):
    r, w = os.pipe()
    pid = os.fork()
    if pid == 0:
        try:
            os.close(r)
            srv.cur["jfh"] = open(str(p) + ".workjournal", "ab")
            srv.every = 10 ** 9  # the copy never snapshots
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
    seed, n, arm, out = args
    r = run_one(seed, n, arm)
    d = Path(out) / "scale"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{arm}_{seed}_{n}.json").write_text(json.dumps(r))
    return r


def main(argv):
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    seeds = [int(x) for x in argv[argv.index("--seeds") + 1].split(",")] if "--seeds" in argv else SEEDS
    sizes = [int(x) for x in argv[argv.index("--sizes") + 1].split(",")] if "--sizes" in argv else SIZES
    arms = argv[argv.index("--arms") + 1].split(",") if "--arms" in argv else list(FLAGS)
    name = argv[argv.index("--out") + 1] if "--out" in argv else "g60h_scale"
    # G60H2 (docs/G60H2.md §6d): --config e = equal check (C) / base certificate meet-in-the-middle (P);
    # p = e on the plain engine. Default (no --config) is G60H's registered configuration, unchanged.
    cfg = argv[argv.index("--config") + 1] if "--config" in argv else None
    if cfg in ("e", "p"):
        FLAGS["hC"] = FLAGS["hC"] + ["--check=equal", "--certifier=mitm"] + (["--plain"] if cfg == "p" else [])
        FLAGS["hP"] = FLAGS["hP"] + ["--certifier=mitm"] + (["--plain"] if cfg == "p" else [])
    OUT = ROOT / "artifacts" / name
    OUT.mkdir(parents=True, exist_ok=True)
    lock0 = LOCK.read_text().strip() if LOCK.exists() else None
    load0 = os.getloadavg()
    jobs = [(s, n, a, str(OUT)) for n in sorted(sizes, reverse=True) for s in seeds for a in arms]
    # registered: 1 worker for the scaling timings (verifier L1 of 80cfb17: 4 workers inflated 64k)
    with Pool(int(os.environ.get("G60H_SCALE_WORKERS", "1"))) as pool:
        res = pool.map(job, jobs, chunksize=1)
    R = {(r["seed"], r["n"], r["arm"]): r for r in res}
    summ = {}
    for a in arms:
        S = {"mean_task_cpu_ms": {n: round(1000 * sum(R[(s, n, a)]["mean_task_cpu_s"] for s in seeds) / len(seeds), 4) for n in sizes},
             "snapshot_cpu_s": {n: round(sum(R[(s, n, a)]["snapshot_cpu_s"] for s in seeds) / len(seeds), 4) for n in sizes}}
        # local exponents per interval (verifier M2 of 80cfb17), not only 16k -> 64k
        for n1, n2 in [(1000, 16000), (16000, 32000), (16000, 64000), (32000, 64000)]:
            if n1 in sizes and n2 in sizes:
                for key, f in [("", "mean_task_cpu_s"), ("_charged_fixed", "charged_fixed_cpu_s"),
                               ("_charged_prop", "charged_prop_cpu_s"), ("_work", "work_calls"), ("_snapshot", "snapshot_cpu_s")]:
                    S[f"alpha{key}_{n1}_{n2}"] = alpha([R[(s, n2, a)][f] / R[(s, n1, a)][f] for s in seeds], n1, n2)
                S[f"alpha_rowops_{n1}_{n2}"] = alpha([max(R[(s, n2, a)]["engine_work"]["row_ops"], 1) / max(R[(s, n1, a)]["engine_work"]["row_ops"], 1) for s in seeds], n1, n2)
        for n in sizes:
            if 0 in sizes:
                S[f"R0_{n}"] = boot([R[(s, n, a)]["mean_task_cpu_s"] / R[(s, 0, a)]["mean_task_cpu_s"] for s in seeds])
        S["workload_identical_across_N"] = all(len({R[(s, n, a)]["reply_stream_sha256"] for n in sizes}) == 1 for s in seeds)
        S["no_snapshot_in_window"] = not any(R[(s, n, a)]["snapshot_in_window"] for s in seeds for n in sizes)
        S["decode_errors"] = sum(R[(s, n, a)]["hdc_counters"]["decode_errors"] for s in seeds for n in sizes)
        S["decodes"] = sum(R[(s, n, a)]["hdc_counters"]["decodes"] for s in seeds for n in sizes)
        summ[a] = S
    rep = {"started": started, "finished": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "seeds": seeds, "sizes": sizes,
           "summary": summ, "flags": FLAGS, "workers": int(os.environ.get("G60H_SCALE_WORKERS", "1")), "lock": {"start": lock0, "end": LOCK.read_text().strip() if LOCK.exists() else None},
           "loadavg": {"start": load0, "end": os.getloadavg()}}
    if "hC" in summ and 16000 in sizes and 64000 in sizes:
        rep["bounded_hC"] = summ["hC"]["alpha_16000_64000"][1][1] < BOUND
        rep["bounded_charged_hC"] = summ["hC"]["alpha_charged_prop_16000_64000"][1][1] < BOUND
    (OUT / f"{name}_receipt.json").write_text(json.dumps(rep, indent=1, default=str))
    print(json.dumps({k: v for k, v in rep.items() if k != "summary"}, default=str))
    for a, S in summ.items():
        print(a, json.dumps({k: v for k, v in S.items() if k.startswith(("alpha_16000_64000", "alpha_charged", "alpha_work_16000_64000", "mean_task", "workload", "no_snap", "decode", "alpha_rowops_16000_64000", "snapshot"))}, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
