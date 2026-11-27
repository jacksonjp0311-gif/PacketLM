"""G60H2 decoy curriculum (L4 of verify-69b5b26; docs/G60H2.md §4).

Six families on G46 phase-A graphs (relations abcd, 5 layers of 10, functional, no missing facts). Each
family teaches `ab` and `bc` first, then a decoy task: the hidden program is a base program of length 4
with no library structure (`dcda`), and the two example subjects are chosen and the graph minimally edited
so that the library composition ab+bc (`abbc`, two library steps) gives the same values on the examples.
So the library prior points to a wrong-but-consistent program: in C's own language the decoy is found at
depth 2 and the target only at depth 4 (beyond the +1 margin); in the base language both have length 4.
The edit only re-points relation a at the two layer-3 entities reached by `dcd` from the examples
(abbc never uses a at layer 3), so `ab`, `bc` and `abbc` keep their values. Correction / contradiction
steps are not used (phase "D"); transfer is generated as in G46.
"""
from __future__ import annotations
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT))
import g46  # noqa: E402
from packetlm.g45_test import Names  # noqa: E402

SPEC = dict(g46.SPEC["A"], tasks=["ab", "bc", "dcda"])
DECOY, TARGET = "abbc", "dcda"


def _img(triples, rel, shape, s):
    return g46.truth(triples, [rel[c] for c in shape], s)


def decoy_family(rng, nm):
    while True:
        rel = {c: nm() for c in SPEC["rels"]}
        L, triples = g46.graph(rng, nm, SPEC, SPEC["width"], rel, SPEC["missing"], SPEC["ambig"])
        pool, sealed = L[0][:SPEC["sealed_from"]], L[0][SPEC["sealed_from"]:]
        cand = []
        for s in pool:
            d, x = _img(triples, rel, DECOY, s), _img(triples, rel, TARGET[:3], s)
            if d[0] == "val" and x[0] == "val":
                cand.append((s, x[1], d[1]))
        pick = None
        for i in range(len(cand)):
            for j in range(i + 1, len(cand)):
                (s1, x1, d1), (s2, x2, d2) = cand[i], cand[j]
                if x1 != x2 or d1 == d2:
                    pick = (cand[i], cand[j])
                    break
            if pick:
                break
        if not pick:
            continue
        edit = {(x, rel["a"]): d for _, x, d in pick}
        triples = [t for t in triples if (t[0], t[1]) not in edit] + [(x, r, d) for (x, r), d in edit.items()]
        ex = [p[0] for p in pick]
        tasks = []
        for shape in SPEC["tasks"]:
            hidden = [rel[c] for c in shape]
            t = {"name": nm(), "shape": shape, "hidden": hidden,
                 "examples": ex if shape == TARGET else [s for s in pool + L[1] if g46.truth(triples, hidden, s)[0] == "val"][:2]}
            tasks.append(t)
        for s in ex:  # the decoy is consistent with the examples, and differs from the target somewhere
            assert _img(triples, rel, DECOY, s) == _img(triples, rel, TARGET, s)
        fam = {"phase": "D", "rel": rel, "layers": L, "triples": triples, "pool": pool, "sealed": sealed, "tasks": tasks,
               "decoy_differs_on_sealed": sum(_img(triples, rel, DECOY, s) != _img(triples, rel, TARGET, s) for s in sealed)}
        TL, tt = g46.graph(rng, nm, SPEC, 6, rel, 0.0, False)
        fam["transfer"] = {"subjects": TL[0], "triples": tt}
        return fam


def world_decoy(seed):
    rng = random.Random(seed)
    nm = Names(rng)
    return [decoy_family(rng, nm) for _ in range(6)]


if __name__ == "__main__":
    for sd in (1, 2, 3):
        w = world_decoy(sd)
        print(sd, [f["decoy_differs_on_sealed"] for f in w])
