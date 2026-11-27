"""G57 part S (audit (c) of d6cbcf3): cost per task as a function of total accumulated state, with
the relevant state held fixed (docs/G57.md §3b, registered before the run).

For each seed and padding size N, a long-lived server (packetlm/serve.py, in-process) first loads
N unrelated facts over 20 padding relations plus N/500 padding capabilities taught from examples
(uncharged, reported as `pad_cpu_s`; for Xi it includes building the memo). Then the same
workload runs at every N: T tasks, each a fresh relation with a chain of 6 facts over fresh
entities (1 call), 3 examples (1 call), then 3 re-ask calls of 6 questions over this task's and
earlier tasks' capabilities (read-only calls, as the teacher's maintenance re-asks are). The
workload never mentions a padding entity or relation, so the relevant state is the same at every N.
Charged: process CPU of the workload calls (time.process_time), per task.
Arms: Xs (reference) and Xi (--indexed); flags --answers --bounded --lean.
Guard: at every (seed, N) the Xi replies equal the Xs replies, call by call.
Each (seed, N, arm) result is written to disk when it finishes.
Run: python3 benchmarks/g57_scale.py [--out g57_scale] [--seeds 221,...] [--sizes 0,1000,...] [--tasks 10]
"""
from __future__ import annotations
import hashlib
import json
import random
import sys
import tempfile
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from packetlm import serve  # noqa: E402

FLAGS = ["--answers", "--bounded", "--lean"]
SEEDS = [221, 222, 223, 224, 225, 226, 227]
SIZES = [0, 1000, 4000, 16000]
TASKS = 10


def padding(rng, n):
    facts = [f"fact pz{rng.randrange(n // 2 + 1)} pr{rng.randrange(20)} pz{rng.randrange(n // 2 + 1)}" for _ in range(n)]
    caps = []
    for c in range(n // 500):  # padding capabilities: one-step programs over padding relations
        r = f"pr{c % 20}"
        ex = []
        for k in range(3):
            s, o = f"pc{c}_{k}", f"pc{c}_{k}o"
            facts.append(f"fact {s} {r} {o}")
            ex.append(f"example pcap{c}: {s} -> {o}")
        caps.append(ex)
    return facts, caps


def workload(rng, tasks):
    calls = []
    for t in range(tasks):
        rel = f"w{t}"
        ents = [f"t{t}e{k}" for k in range(7)]
        calls.append((t, [f"fact {ents[k]} {rel} {ents[k + 1]}" for k in range(6)]))
        calls.append((t, [f"example wc{t}: {ents[k]} -> {ents[k + 1]}" for k in range(3)]))
        for _ in range(3):
            qs = []
            for _ in range(6):
                u = rng.randrange(t + 1)
                qs.append(f"what is t{u}e{rng.randrange(7)} wc{u}")
            calls.append((t, qs))
    return calls


def job(args):
    seed, n, arm, tasks, out = args
    rng = random.Random(seed * 100003 + n)
    facts, caps = padding(rng, n)
    work = workload(random.Random(seed), tasks)
    flags = FLAGS + (["--indexed"] if arm == "i" else [])
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "s.json"
        srv = serve.Server()
        t0 = time.process_time()
        for k in range(0, len(facts), 2000):
            srv.call(p, flags, facts[k:k + 2000])
        for ex in caps:
            srv.call(p, flags, ex)
        pad = time.process_time() - t0
        per, stream, replies = [0.0] * tasks, hashlib.sha256(), []
        for t, lines in work:
            c0 = time.process_time()
            r = srv.call(p, flags, lines)["replies"]
            per[t] += time.process_time() - c0
            stream.update(json.dumps([lines, r]).encode())
            replies.append(r)
        srv.close()
    res = {"seed": seed, "n": n, "arm": arm, "pad_facts": len(facts), "pad_caps": len(caps), "pad_cpu_s": round(pad, 4),
           "task_cpu_s": [round(x, 5) for x in per], "mean_task_cpu_s": round(sum(per) / tasks, 5),
           "reply_stream_sha256": stream.hexdigest(),
           "known": sum(1 for r in replies for x in r if " wc" in x and "unknown" not in x and "ambiguous" not in x)}
    o = Path(out) / f"s{seed}_n{n}_{arm}.json"
    o.write_text(json.dumps(res))  # incremental
    return res


def boot(vals, reps=5000, seed=0):
    rng = random.Random(seed)
    m = sorted(sum(rng.choice(vals) for _ in vals) / len(vals) for _ in range(reps))
    return round(sum(vals) / len(vals), 4), [round(m[int(0.025 * reps)], 4), round(m[int(0.975 * reps) - 1], 4)]


def main(argv):
    get = lambda f, d: [int(x) for x in argv[argv.index(f) + 1].split(",")] if f in argv else d  # noqa: E731
    seeds, sizes = get("--seeds", SEEDS), get("--sizes", SIZES)
    tasks = get("--tasks", [TASKS])[0]
    name = argv[argv.index("--out") + 1] if "--out" in argv else "g57_scale"
    out = ROOT / "artifacts" / name
    out.mkdir(parents=True, exist_ok=True)
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    jobs = [(s, n, a, tasks, str(out)) for n in sorted(sizes, reverse=True) for s in seeds for a in "si"]
    with Pool(8) as pool:
        res = list(pool.imap_unordered(job, jobs))
    R = {(r["seed"], r["n"], r["arm"]): r for r in res}
    rep = {"started": started, "finished": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "seeds": seeds, "sizes": sizes,
           "tasks": tasks, "runs": res}
    rep["guard_replies_i_equal_s"] = all(R[(s, n, "i")]["reply_stream_sha256"] == R[(s, n, "s")]["reply_stream_sha256"]
                                         for s in seeds for n in sizes)
    rep["guard_workload_answered"] = all(R[(s, n, a)]["known"] == R[(s, 0, a)]["known"] for s in seeds for n in sizes for a in "si")
    nmax = max(sizes)
    summ = {}
    for a in "si":
        summ[a] = {"mean_task_cpu_ms": {n: round(1000 * sum(R[(s, n, a)]["mean_task_cpu_s"] for s in seeds) / len(seeds), 3)
                                        for n in sizes},
                   "pad_cpu_s": {n: round(sum(R[(s, n, a)]["pad_cpu_s"] for s in seeds) / len(seeds), 3) for n in sizes}}
        for n in sizes:
            if n:
                ratios = [R[(s, n, a)]["mean_task_cpu_s"] / R[(s, 0, a)]["mean_task_cpu_s"] for s in seeds]
                summ[a][f"R_{n}"] = boot(ratios)
    rep["summary"] = summ
    rep["flat_Xi"] = summ["i"][f"R_{nmax}"][1][1] <= 1.25  # registered criterion (docs/G57.md §3b)
    (out / f"{name}_receipt.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k != "runs"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
