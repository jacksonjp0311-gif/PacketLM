"""G60H accuracy / capacity of the sparse block code operations (docs/G60H.md §3), uncharged, not timed.

For each (K, L) in a grid (a subprocess per config, codes.py reads K, L from the environment):
  bundle    OR-bundle of d random members of a codebook of M items; cleanup decode; spurious items
            (decoded non-members) and misses, per bundle (the entity-signature and capability-index path)
  sequence  composed hypervector of m position-permuted primitives (codebook of M); a decode error is
            any position not decoding to exactly its primitive (the capability path; the engine checks
            against the exact copy and counts such errors)
  keys      fact memory: M random (subject, relation) pairs, bound keys; collisions = distinct pairs
            with one key (would merge two facts; the registered engine does not detect them)
Expected rates: spurious per candidate ~ (d/L)^K; key collisions ~ M^2 / (2 L^K).
Run: python3 benchmarks/g60h_capacity.py [--out g60h_capacity]
"""
from __future__ import annotations
import json
import os
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRID = [(4, 16), (8, 16), (16, 16), (32, 16), (4, 64), (8, 64), (16, 64), (32, 64)]
D_SIZES = [1, 2, 4, 8, 16, 32]
M_SIZES = [1000, 20000]
M_SEQ = 1000
SEQ_LENS = [1, 2, 3, 4, 5, 8]
KEY_M = [10000, 100000]
TRIALS = 200


def one(K, L):
    sys.path.insert(0, str(ROOT))
    from packetlm.hdc import codes as C
    assert C.K == K and C.L == L
    rng = random.Random(K * 1000 + L)
    out = {"K": K, "L": L, "D": K * L, "bundle": [], "sequence": [], "keys": []}
    for M in M_SIZES:
        cb = C.Codebook()
        names = [f"i{M}_{i}" for i in range(M)]
        for nm in names:
            cb.add(nm)
        for d in D_SIZES:
            spur = miss = 0
            for _ in range(TRIALS):
                mem = rng.sample(names, d)
                S = 0
                for nm in mem:
                    S |= cb.hot[nm]
                got = set(cb.decode(S))
                spur += len(got - set(mem))
                miss += len(set(mem) - got)
            out["bundle"].append({"M": M, "d": d, "trials": TRIALS, "spurious_per_bundle": spur / TRIALS,
                                  "misses_per_bundle": miss / TRIALS, "code_collisions": cb.collisions,
                                  "expected_spurious_per_candidate": (d / L) ** K})
    cb = C.Codebook()
    names = [f"p{i}" for i in range(M_SEQ)]
    for nm in names:
        cb.add(nm)
    for m in SEQ_LENS:
        err = 0
        for _ in range(TRIALS):
            seq = [rng.choice(names) for _ in range(m)]
            H = 0
            for k, p in enumerate(seq):
                H |= C.onehot(C.rho(cb.code[p], k))
            dec = []
            for k in range(m):
                it = cb.decode(H, k)
                dec.append(it[0] if len(it) == 1 else None)
            err += dec != seq
        out["sequence"].append({"M": M_SEQ, "m": m, "trials": TRIALS, "decode_error_rate": err / TRIALS})
    for M in KEY_M:
        ent = C.Codebook()
        rel = C.Codebook()
        keys = {}
        coll = 0
        for i in range(M):
            s, r = f"s{rng.randrange(M)}", f"r{rng.randrange(20)}"
            k = C.bind(ent.add(s), C.rho(rel.add(r)))
            if k in keys and keys[k] != (s, r):
                coll += 1
            keys.setdefault(k, (s, r))
        out["keys"].append({"M": M, "collisions": coll, "expected": M * M / (2 * float(L) ** K)})
    return out


def main(argv):
    if "--one" in argv:
        K, L = (int(x) for x in argv[argv.index("--one") + 1].split(","))
        print(json.dumps(one(K, L)))
        return 0
    name = argv[argv.index("--out") + 1] if "--out" in argv else "g60h_capacity"
    OUT = ROOT / "artifacts" / name
    OUT.mkdir(parents=True, exist_ok=True)
    res = []
    for K, L in GRID:
        env = dict(os.environ, PACKETLM_HDC_K=str(K), PACKETLM_HDC_L=str(L))
        p = subprocess.run([sys.executable, __file__, "--one", f"{K},{L}"], env=env, capture_output=True, text=True)
        if p.returncode:
            raise SystemExit(p.stderr[-2000:])
        res.append(json.loads(p.stdout))
    (OUT / "capacity.json").write_text(json.dumps(res, indent=1))
    for r in res:
        b = {(x["M"], x["d"]): round(x["spurious_per_bundle"], 3) for x in r["bundle"]}
        print(f"K={r['K']:2d} L={r['L']:3d} D={r['D']:5d} spurious(M=20k,d=4/8/16/32)=",
              [b[(20000, d)] for d in (4, 8, 16, 32)], "misses=", max(x["misses_per_bundle"] for x in r["bundle"]),
              "seqerr(m=2/5/8)=", [x["decode_error_rate"] for x in r["sequence"] if x["m"] in (2, 5, 8)],
              "keycoll(1e5)=", r["keys"][-1]["collisions"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
