import sys, random, time, json, hashlib, tempfile, cProfile, pstats
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parent.parent), str(Path(__file__).resolve().parent)]
from packetlm import serve
FLAGS = ["--answers", "--bounded", "--lean", "--deepen=5", "--indexed", "--incremental"]

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

def job(seed, L, extra, tasks=10, prof=False):
    rng = random.Random(seed * 7919 + L)
    facts, caps = lib_padding(rng, L)
    work = workload(random.Random(seed), tasks)
    flags = FLAGS + extra
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
        per, stream = [0.0] * tasks, hashlib.sha256()
        pr = cProfile.Profile() if prof else None
        if pr: pr.enable()
        for t, lines in work:
            c0 = time.process_time()
            r = srv.call(p, flags, lines)["replies"]
            per[t] += time.process_time() - c0
            stream.update(json.dumps([lines, r]).encode())
        if pr:
            pr.disable(); st = pstats.Stats(pr); st.sort_stats("cumulative"); st.print_stats(25)
        srv.close()
        sh = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
    return {"L": L, "pad": round(pad, 2), "mean_ms": round(1000 * sum(per) / tasks, 2), "replies": stream.hexdigest()[:12], "state": sh,
            "last": r}

if __name__ == "__main__":
    extra = sys.argv[2].split(",") if len(sys.argv) > 2 and sys.argv[2] else []
    for L in [int(x) for x in sys.argv[1].split(",")]:
        print(json.dumps(job(991, L, extra, prof="--prof" in sys.argv)))
