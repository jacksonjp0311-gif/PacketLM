"""Verifier's differential test for --bounded (050bebd): random base-engine sessions of facts,
examples (values, !none, !several), complete, retract, correct, what-is, investigate and requalify,
on several capabilities that can use each other (library). The same session is run on an
unbounded and a bounded engine; every reply and, after every line, every capability's
(current version, status, seq) must be equal. Sessions are split across fresh processes
(save + re-open) at random points. Flags: [--qualified-library] [--operators]."""
import random, sys, json, tempfile, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
from packetlm.engine import Engine

def world(rng):
    n = rng.randint(4, 9)
    ents = [f"e{i}" for i in range(n)]
    rels = ["ra", "rb", "rc"][: rng.randint(2, 3)]
    tri = set()
    for r in rels:
        for x in ents:
            for _ in range(rng.choice([0, 1, 1, 2])):
                tri.add((x, r, rng.choice(ents)))
    return ents, rels, sorted(tri)

def path(tri, seq, x):
    cur = {x}
    for r in seq:
        cur = {o for s, rr, o in tri if s in cur and rr == r}
    return cur

def session(rng, extra):
    ents, rels, tri = world(rng)
    tri = set(tri)
    caps = {f"k{i}": [rng.choice(rels) for _ in range(rng.randint(1, 3))] for i in range(rng.randint(1, 3))}
    lines = [f"fact {s} {r} {o}" for s, r, o in sorted(tri)]
    for _ in range(rng.randint(8, 30)):
        c = rng.choice(sorted(caps))
        k = rng.random()
        if k < 0.35:
            x = rng.choice(ents)
            t = path(tri, caps[c], x)
            v = next(iter(t)) if len(t) == 1 else ("!none" if not t else "!several")
            lines.append(f"example {c}: {x} -> {v}")
        elif k < 0.55:
            seen = [l.split(":")[1].split("->")[0].strip() for l in lines if l.startswith("example ")]
            lines.append(f"complete {rng.choice(seen) if seen and rng.random() < 0.7 else rng.choice(ents)}")
        elif k < 0.65:
            t = (rng.choice(ents), rng.choice(rels), rng.choice(ents)); tri.add(t)
            lines.append(f"fact {t[0]} {t[1]} {t[2]}")
        elif k < 0.70 and tri:
            t = rng.choice(sorted(tri)); tri.discard(t)
            lines.append(f"retract {t[0]} {t[1]} {t[2]}")
        elif k < 0.74 and tri:
            t = rng.choice(sorted(tri)); o2 = rng.choice(ents)
            tri = {x for x in tri if not (x[0] == t[0] and x[1] == t[1])} | {(t[0], t[1], o2)}
            lines.append(f"correct {t[0]} {t[1]} {o2}")
        elif k < 0.80:
            lines.append(f"investigate {c}")
        elif k < 0.84:
            lines.append(f"requalify {c}")
        else:
            lines.append(f"what is {rng.choice(ents)} {c}")
    lines += [f"what is {x} {c}" for c in sorted(caps) for x in ents]
    splits = {i for i in range(len(lines)) if rng.random() < 0.15}
    out = {}
    for b in (False, True):
        fd, p = tempfile.mkstemp(suffix=".json"); os.close(fd); os.unlink(p)
        kw = dict(answers=True, bounded=b, **extra)
        eng = Engine(p, **kw)
        rep, sts, skipped = [], [], 0
        for i, ln in enumerate(lines):
            if i in splits:
                skipped += eng.stats.get("fc_skipped", 0)
                eng.save(); eng = Engine.open(p, **kw)
            rep.append(eng.turn(ln))
            sts.append(json.dumps({n: (c_["current"], (eng.version(n) or {}).get("status"), (eng.version(n) or {}).get("seq"))
                                   for n, c_ in sorted(eng.state["capabilities"].items())}))
        eng.save()
        out[b] = (rep, sts, {"fc_skipped": skipped + eng.stats.get("fc_skipped", 0)})
        os.unlink(p)
    diff = [i for i in range(len(lines)) if out[False][0][i] != out[True][0][i] or out[False][1][i] != out[True][1][i]]
    return {"lines": len(lines), "diff": diff[:1], "line": lines[diff[0]] if diff else None,
            "a": out[False][0][diff[0]] if diff else None, "b": out[True][0][diff[0]] if diff else None,
            "fc_skipped": out[True][2].get("fc_skipped", 0), "qualified_seen": any('"qualified"' in s for s in out[True][1])}

if __name__ == "__main__":
    N, seed = int(sys.argv[1]), int(sys.argv[2])
    extra = {"qualified_library": "--qualified-library" in sys.argv, "operators": "--operators" in sys.argv}
    rng = random.Random(seed)
    rows = [session(rng, extra) for _ in range(N)]
    print(json.dumps({"seed": seed, "flags": extra, "sessions": N, "lines": sum(r["lines"] for r in rows),
                      "sessions_with_qualified": sum(r["qualified_seen"] for r in rows),
                      "fc_skipped_total": sum(r["fc_skipped"] for r in rows),
                      "sessions_with_skip": sum(r["fc_skipped"] > 0 for r in rows),
                      "sessions_differing": sum(bool(r["diff"]) for r in rows)}))
    for r in [r for r in rows if r["diff"]][:5]:
        print(json.dumps(r))
