"""Dev only: run a g56 arm in-process (packetlm.serve.Server), record every call; or replay a record."""
import sys, json, time, hashlib, tempfile, pickle, cProfile, pstats
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "benchmarks")]
import g56
from packetlm import serve

class InProc:
    log = []
    class _P:
        def poll(self): return 0
        def kill(self): pass
    def __init__(self):
        self.s = serve.Server()
        self.p = InProc._P()
    def req(self, **r):
        if r["op"] == "call":
            InProc.log.append((r["state"], r["flags"], r["lines"]))
        out = self.s.handle(r)
        return json.loads(json.dumps(out, default=str))
    def stop(self):
        return self.req(op="close")

def record(cur, seed, role, extra, dest):
    g56.Server = InProc
    g56.BASEF[role] = g56.BASEF[role] + extra
    d = tempfile.mkdtemp()
    InProc.log = []
    t = time.process_time()
    r = g56.job((cur, seed, role + "s", d))
    cpu = time.process_time() - t
    st = Path(d) / cur / (role + "s") / f"seed{seed}" / f"{role}.json"
    base = str(Path(d))
    pickle.dump({"base": base, "log": InProc.log}, open(dest, "wb"))
    print(json.dumps({"cpu": round(cpu, 3), "calls": len(InProc.log), "state": hashlib.sha256(st.read_bytes()).hexdigest()[:16]}))

def replay(src, extra, prof=None):
    rec = pickle.load(open(src, "rb"))
    d = tempfile.mkdtemp()
    s = serve.Server()
    reps = hashlib.sha256()
    pr = cProfile.Profile() if prof else None
    t = time.process_time()
    if pr: pr.enable()
    finals = {}
    for state, flags, lines in rec["log"]:
        p = state.replace(rec["base"], d)
        out = s.call(p, flags + extra, lines)
        reps.update(json.dumps(out["replies"]).encode())
        finals[p] = 1
    s.close()
    if pr: pr.disable()
    cpu = time.process_time() - t
    h = hashlib.sha256()
    for p in sorted(finals):
        h.update(Path(p).read_bytes())
    res = {"cpu": round(cpu, 3), "replies": reps.hexdigest()[:16], "states": h.hexdigest()[:16], "stats": {}}
    if pr:
        st = pstats.Stats(pr); st.sort_stats("cumulative"); st.print_stats(prof)
    print(json.dumps(res))

if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "record":
        record(a[1], int(a[2]), a[3], a[5].split(",") if len(a) > 5 and a[5] else [], a[4])
    else:
        replay(a[1], a[2].split(",") if len(a) > 2 and a[2] else [], int(a[3]) if len(a) > 3 else None)
