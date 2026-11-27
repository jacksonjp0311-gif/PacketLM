import os, sys, json, gzip
from multiprocessing import Pool
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "benchmarks"), str(ROOT)]
import g56, g60h
M = int(sys.argv[1]); OUT = Path(sys.argv[2]); jobs_spec = sys.argv[3]  # e.g. comp:401-407:CB,long:441-443:CB
TOOL = str(ROOT / "tools_69b5b26/shadow_serve.py")


class SServer(g56.Server):
    def __init__(self):
        import subprocess as sp
        self.p = sp.Popen([sys.executable, TOOL], cwd=ROOT, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE, text=True, bufsize=1)


def job(a):
    cur, seed, arm, out = a
    os.environ["SHADOW_LOG"] = str(OUT / f"{cur}_{seed}_{arm}.jsonl")
    Path(os.environ["SHADOW_LOG"]).unlink(missing_ok=True)
    g60h.HServer = SServer
    r = g60h.job(a)
    return (cur, seed, arm, r["reply_stream_sha256"], r["final_state_sha256"])


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for r_ in g56.BASEF:
        g56.BASEF[r_] = g56.BASEF[r_] + [f"--margin={M}"]
    jobs = []
    for spec in jobs_spec.split(","):
        c, rng, arms = spec.split(":")
        lo, hi = map(int, rng.split("-"))
        jobs += [(c, s, a + "h", str(OUT / "_runs")) for s in range(lo, hi + 1) for a in arms]
    with Pool(int(os.environ.get("W", "4"))) as p:
        res = p.map(job, jobs, chunksize=1)
    ev = ROOT / f"docs/evidence/g60h/gate_m{M}"
    regs = {}
    same = []
    for c, s, a, rs, fs in res:
        if c not in regs:
            regs[c] = json.load(gzip.open(ev / f"{c}_raw.json.gz"))
        R = regs[c][f"{s}:{a}"]
        same.append((c, s, a, rs == R["reply_stream_sha256"], fs == R["final_state_sha256"]))
    print(json.dumps(same))
    (OUT / "identity.json").write_text(json.dumps(same))
