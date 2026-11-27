"""G46-U: the G46 learner on an unrelated curriculum (docs/G46U.md).
Every task gets a fresh family of relations and entities, so nothing learned earlier
can be reused. Same teacher, budgets, engine and cost accounting as G46.
Run: python3 benchmarks/g46u.py [--seeds 11,22,33]
"""

from __future__ import annotations
import json
import random
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT))
import g46  # noqa: E402
from packetlm.g45_test import Names  # noqa: E402

SPEC_U = {"rels": "abc", "layers": 4, "width": 8, "missing": 0.0, "ambig": False, "sealed_from": 4}
SHAPES = ["ab", "ba", "abc", "cab", "bc", "ca", "aa", "cb"]
N_TASKS = 24
ARMS = ["C", "B", "P"]


def world_unrelated(seed):
    rng = random.Random(seed * 101 + 7)
    nm = Names(rng)
    fams = []
    for fi in range(N_TASKS):
        rel = {c: nm() for c in SPEC_U["rels"]}
        L, triples = g46.graph(rng, nm, SPEC_U, SPEC_U["width"], rel, 0.0, False)
        pool, sealed = L[0][:4], L[0][4:]
        shape = rng.choice(SHAPES)
        hidden = [rel[c] for c in shape]
        single = [s for s in pool + L[1] if g46.truth(triples, hidden, s)[0] == "val"]
        tasks = [{"name": nm(), "shape": shape, "hidden": hidden, "examples": single[:2]}]
        TL, tt = g46.graph(rng, nm, SPEC_U, 6, rel, 0.0, False)
        fams.append({"phase": "U", "rel": rel, "layers": L, "triples": triples, "pool": pool, "sealed": sealed,
                     "tasks": tasks, "transfer": {"subjects": TL[0], "triples": tt}})
    return fams


def main(argv):
    seeds = [11, 22, 33]
    if "--seeds" in argv:
        seeds = [int(x) for x in argv[argv.index("--seeds") + 1].split(",")]
    g46.world = world_unrelated
    g46.OUT = ROOT / "artifacts/g46u"
    g46.OUT.mkdir(parents=True, exist_ok=True)
    sha0 = g46.source_hash()
    with Pool(8) as pool:
        res = pool.map(g46.run_arm, [(s, a) for s in seeds for a in ARMS])
    runs = {(r["seed"], r["arm"]): r for r in res}
    rep = {"engine_sha256": sha0, "unchanged": sha0 == g46.source_hash(), "seeds": {}}
    for s in seeds:
        C, B, P = (runs[(s, a)] for a in ARMS)
        rep["seeds"][s] = {
            "acquired": {a: sum(t["acquired"] for t in runs[(s, a)]["tasks"]) for a in ARMS},
            "sealed_correct": {a: sum(t["correct"] for t in runs[(s, a)]["tasks"]) for a in ARMS},
            "library_uses_C": sum(t["uses_library"] for t in C["tasks"]),
            "task_cpu_s": {a: round(sum(t["cost"]["cpu_s"] for t in runs[(s, a)]["tasks"]), 3) for a in ARMS},
            "A_vs_empty": g46.amort(C, B)[-1], "A_reuse_vs_primitive": g46.amort(C, P)[-1]}
    (g46.OUT / "g46u_receipt.json").write_text(json.dumps(rep, indent=1))
    (g46.OUT / "g46u_raw.json").write_text(json.dumps({f"{k[0]}:{k[1]}": v for k, v in runs.items()}))
    print(json.dumps(rep, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
