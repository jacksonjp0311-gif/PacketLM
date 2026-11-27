"""G59 curricula (docs/G59.md §5), built from the G46 generators without changing them.

- `world_long(seed)`: the compositional curriculum (benchmarks/g46.py `world`) with its six-family
  phase pattern AAABBB repeated REPS times (24 families, 144 tasks); every family has fresh relations
  and entities, exactly as in `world` (the contradiction task stays at family 3, the A-phase
  corrections at every A family). Accumulated knowledge grows four times as long as in `comp`.
- `world_mixed(seed)`: the six compositional families of `world`, each followed by two unrelated
  families (benchmarks/g46u.py `world_unrelated`'s family form: a fresh 3-relation family with one
  task), all names from one generator so no token is shared by accident (48 tasks).
"""
from __future__ import annotations
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT))
import g46  # noqa: E402
import g46u  # noqa: E402
from packetlm.g45_test import Names  # noqa: E402

REPS = 4
UNREL_PER_COMP = 2


def _comp_family(rng, nm, phase, fi):
    """One family of g46.world (the same draws in the same order)."""
    spec = g46.SPEC[phase]
    rel = {c: nm() for c in spec["rels"]}
    L, triples = g46.graph(rng, nm, spec, spec["width"], rel, spec["missing"], spec["ambig"])
    pool, sealed = L[0][:spec["sealed_from"]], L[0][spec["sealed_from"]:]
    tasks = []
    for ti, shape in enumerate(spec["tasks"]):
        hidden = [rel[c] for c in shape]
        single = [s for s in pool + L[1] if g46.truth(triples, hidden, s)[0] == "val"]
        ex = single[:2]
        t = {"name": nm(), "shape": shape, "hidden": hidden, "examples": ex}
        if phase == "B" and fi == 3 and ti == 1 and len(ex) == 2:
            v0, v1 = g46.truth(triples, hidden, ex[0])[1], g46.truth(triples, hidden, ex[1])[1]
            wrong = v1 if v1 != v0 else next(o for o in L[-1] if o != v0)
            t["contradiction"] = wrong
        tasks.append(t)
    fam = {"phase": phase, "rel": rel, "layers": L, "triples": triples, "pool": pool, "sealed": sealed, "tasks": tasks}
    if phase == "A":
        s, r = L[1][3], rel["a"]
        old = {o for x, rr, o in triples if x == s and rr == r}
        fam["correction"] = (s, r, rng.choice([o for o in L[2] if o not in old]))
    TL, tt = g46.graph(rng, nm, spec, 6, rel, 0.0, False)
    fam["transfer"] = {"subjects": TL[0], "triples": tt}
    return fam


def _unrel_family(rng, nm):
    """One family of g46u.world_unrelated (same form and draws)."""
    S = g46u.SPEC_U
    rel = {c: nm() for c in S["rels"]}
    L, triples = g46.graph(rng, nm, S, S["width"], rel, 0.0, False)
    pool, sealed = L[0][:4], L[0][4:]
    shape = rng.choice(g46u.SHAPES)
    hidden = [rel[c] for c in shape]
    single = [s for s in pool + L[1] if g46.truth(triples, hidden, s)[0] == "val"]
    tasks = [{"name": nm(), "shape": shape, "hidden": hidden, "examples": single[:2]}]
    TL, tt = g46.graph(rng, nm, S, 6, rel, 0.0, False)
    return {"phase": "U", "rel": rel, "layers": L, "triples": triples, "pool": pool, "sealed": sealed,
            "tasks": tasks, "transfer": {"subjects": TL[0], "triples": tt}}


def world_long(seed):
    rng = random.Random(seed)
    nm = Names(rng)
    return [_comp_family(rng, nm, phase, fi) for fi, phase in enumerate("AAABBB" * REPS)]


def world_mixed(seed):
    rng = random.Random(seed)
    nm = Names(rng)
    fams = []
    for fi, phase in enumerate("AAABBB"):
        fams.append(_comp_family(rng, nm, phase, fi))
        for _ in range(UNREL_PER_COMP):
            fams.append(_unrel_family(rng, nm))
    return fams


if __name__ == "__main__":  # self-check: world_long's first six families are g46.world's
    for sd in (1, 2, 3):
        a, b = g46.world(sd), world_long(sd)[:6]
        assert repr(a) == repr(b), sd
        m = world_mixed(sd)
        toks = [set(x for f in [fam] for t in f["triples"] for x in t) for fam in m]
        assert all(not (toks[i] & toks[j]) for i in range(len(m)) for j in range(i))
    print("ok", len(world_long(1)), sum(len(f["tasks"]) for f in world_long(1)), sum(len(f["tasks"]) for f in world_mixed(1)))
