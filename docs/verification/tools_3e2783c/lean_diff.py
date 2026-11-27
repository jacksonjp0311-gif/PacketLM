"""Verifier's differential test for --lean (3e2783c), through the real CLI (one process per batch).
Random sessions (facts, examples incl. !none/!several, complete, retract, correct, investigate,
requalify, what-is on capabilities AND on told relations, which exercises geometric recall) are
split into random process batches and run three ways on fresh state files:
  ref    every process without --lean
  lean   every process with --lean
  mixed  each process picks --lean or not at random (cross-compatibility of the files)
Compared: every reply, the final state (canonical JSON), and the backup file's state.
LEAN_NORM=1 compares states with every list sorted (separates order-only differences).
Usage: lean_diff.py N SEED [extra engine flags...]   e.g. --bounded, --programs"""
import random, sys, json, tempfile, os, subprocess
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))

def session(rng):
    n = rng.randint(4, 9)
    ents = [f"e{i}" for i in range(n)]
    rels = ["ra", "rb", "rc"][: rng.randint(2, 3)]
    tri = set()
    for r in rels:
        for x in ents:
            for _ in range(rng.choice([0, 1, 1, 2])):
                tri.add((x, r, rng.choice(ents)))
    caps = {f"k{i}": [rng.choice(rels) for _ in range(rng.randint(1, 3))] for i in range(rng.randint(1, 3))}
    def path(seq, x):
        cur = {x}
        for r in seq:
            cur = {o for s, rr, o in tri if s in cur and rr == r}
        return cur
    lines = [f"fact {s} {r} {o}" for s, r, o in sorted(tri)]
    for _ in range(rng.randint(10, 30)):
        c = rng.choice(sorted(caps)); k = rng.random()
        if k < 0.3:
            x = rng.choice(ents); t = path(caps[c], x)
            lines.append(f"example {c}: {x} -> " + (next(iter(t)) if len(t) == 1 else ("!none" if not t else "!several")))
        elif k < 0.45:
            lines.append(f"complete {rng.choice(ents)}")
        elif k < 0.55:
            t = (rng.choice(ents), rng.choice(rels), rng.choice(ents)); tri.add(t)
            lines.append(f"fact {t[0]} {t[1]} {t[2]}")
        elif k < 0.6 and tri:
            t = rng.choice(sorted(tri)); tri.discard(t)
            lines.append(f"retract {t[0]} {t[1]} {t[2]}")
        elif k < 0.64 and tri:
            t = rng.choice(sorted(tri)); o2 = rng.choice(ents)
            tri = {x for x in tri if not (x[0] == t[0] and x[1] == t[1])} | {(t[0], t[1], o2)}
            lines.append(f"correct {t[0]} {t[1]} {o2}")
        elif k < 0.7:
            lines.append(f"investigate {c}")
        elif k < 0.73:
            lines.append(f"requalify {c}")
        elif k < 0.86:
            lines.append(f"what is {rng.choice(ents)} {rng.choice(rels)}")
        else:
            lines.append(f"what is {rng.choice(ents)} {c}")
    lines += [f"what is {x} {r}" for x in ents for r in rels[:1]] + [f"what is {x} {c}" for c in sorted(caps) for x in ents]
    cuts = sorted(rng.sample(range(1, len(lines)), min(len(lines) - 1, rng.randint(2, 8))))
    batches = [lines[a:b] for a, b in zip([0] + cuts, cuts + [len(lines)])]
    return batches

def run(batches, lean_of, extra):
    d = tempfile.mkdtemp(); st = os.path.join(d, "s.json")
    rep = []
    for i, b in enumerate(batches):
        fl = extra + (["--lean"] if lean_of(i) else [])
        p = subprocess.run([sys.executable, "-m", "packetlm.engine", st, *fl, *b], cwd=ROOT, capture_output=True, text=True)
        if p.returncode:
            return {"error": p.stderr[-300:]}, None, None
        rep += json.loads(p.stdout)["replies"]
    canon = lambda f: json.dumps(json.loads(open(f).read())["state"], sort_keys=True) if os.path.exists(f) else None
    if os.environ.get("LEAN_NORM"):  # order-insensitive: every list sorted by its JSON text
        def norm(x):
            if isinstance(x, dict): return {k: norm(v) for k, v in x.items()}
            if isinstance(x, list): return sorted((norm(v) for v in x), key=lambda v: json.dumps(v, sort_keys=True))
            return x
        canon = lambda f: json.dumps(norm(json.loads(open(f).read())["state"]), sort_keys=True) if os.path.exists(f) else None
    return rep, canon(st), canon(st + ".bak")

if __name__ == "__main__":
    N, seed, extra = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3:]
    rng = random.Random(seed)
    diff, lines, procs = [], 0, 0
    for i in range(N):
        b = session(rng); lines += sum(map(len, b)); procs += 3 * len(b)
        mix = [rng.random() < 0.5 for _ in b]
        ref = run(b, lambda j: False, extra)
        for name, f in (("lean", lambda j: True), ("mixed", lambda j: mix[j])):
            got = run(b, f, extra)
            if got != ref:
                k = next((j for j, (x, y) in enumerate(zip(ref[0], got[0])) if x != y), None) if isinstance(got[0], list) else None
                diff.append({"session": i, "variant": name, "first_reply_diff": k,
                             "ref": ref[0][k] if k is not None else None, "got": got[0][k] if k is not None else str(got[0])[:200],
                             "state_equal": ref[1] == got[1], "backup_equal": ref[2] == got[2]})
    print(json.dumps({"seed": seed, "flags": extra, "sessions": N, "lines": lines, "processes": procs,
                      "differing": len(diff)}))
    for x in diff[:5]:
        print(json.dumps(x))
