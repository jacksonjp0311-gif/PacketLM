"""Verifier's adversarial differential test of `--indexed` (35bda6b), independent of g57_diff.

Three in-process servers (packetlm.serve.Server) run the same session:
  REF  flags without --indexed (every re-ask executed by the reference code)
  IDX  flags + --indexed, check_readonly=True (a read-only call that moves the state fails)
  IDX2 flags + --indexed, check_readonly=False (the registered configuration)
After every call: replies equal, and json.dumps(state) (insertion order) byte-equal, across all
three. At the end: snapshot files byte-equal.
Sessions are built to make gated answers go stale: capabilities taught from a hidden chain program
so they qualify, a second capability composed on the first (cap: dependency), then rounds of
read-only re-ask calls (every entity, unknown entities, lexicon words, odd question forms) between
single adversarial mutations: an alternative path (new fact at a relation the program uses), a
fact at a new entity, retract / correct of a used fact, complete, a contradicting example
(suspension, re-acquisition, capability replacement), correct example, investigate, requalify,
define (lexicon) and redefine, express, a construction (library change), a question template,
re-teaching a capability on another relation, a new relation, and mixed question+mutation calls;
also memo drops (close / other path) between rounds.
Usage: indexed_diff.py N SEED [extra flags]"""
import json, os, random, shutil, sys, tempfile
from pathlib import Path
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, ROOT)
from packetlm.serve import Server  # noqa: E402

BASE = ["--answers", "--bounded", "--lean", "--deepen=3"]


def world(rng):
    ents = [f"e{i}" for i in range(rng.randint(6, 11))]
    rels = [f"r{i}" for i in range(rng.randint(2, 4))]
    tri = set()
    for r in rels:
        for x in ents:
            if rng.random() < 0.75:
                tri.add((x, r, rng.choice(ents)))
    return ents, rels, tri


def run_path(tri, seq, x):
    cur = {x}
    for r in seq:
        cur = {o for s, rr, o in tri if s in cur and rr == r}
    return cur


def examples(rng, tri, ents, name, seq, k):
    out = []
    for x in rng.sample(ents, len(ents)):
        v = run_path(tri, seq, x)
        if len(v) == 1:
            out.append(f"example {name}: {x} -> {next(iter(v))}")
        if len(out) >= k:
            break
    return out


def session(rng):
    ents, rels, tri = world(rng)
    names = rng.sample(["zz", "kk", "aa", "mm", "qq", "bb"], 3)
    seqs = {names[0]: [rng.choice(rels)], names[1]: None, names[2]: [rng.choice(rels), rng.choice(rels)]}
    seqs[names[1]] = seqs[names[0]] + [rng.choice(rels)]  # composable on names[0]
    calls = [[f"fact {s} {r} {o}" for s, r, o in sorted(tri)]]
    for n in names:
        ex = examples(rng, tri, ents, n, seqs[n], 3)
        if ex:
            calls.append(ex)
    words = []
    new_i = [0]

    def questions():
        qs = []
        for n in names + words:
            for x in rng.sample(ents, min(len(ents), rng.randint(3, len(ents)))) + ["zq", f"n{new_i[0]}"]:
                form = rng.choice(["what is {x} {n}", "What is {x} {n}?", "ask {x} {n}", "what is {x} {n}."])
                qs.append(form.format(x=x, n=n))
        for r in rels[:2]:
            qs.append(f"what is {rng.choice(ents)} {r}")
        rng.shuffle(qs)
        return qs[:rng.randint(4, 24)]

    for _ in range(rng.randint(8, 16)):
        calls.append(questions())
        if rng.random() < 0.5:
            calls.append(questions())  # repeated re-ask call: the gate's main use
        k = rng.random()
        n = rng.choice(names)
        seq = seqs[n]
        if k < 0.14:  # alternative path at a relation the program uses
            r = rng.choice(seq); s = rng.choice(ents); o = rng.choice(ents)
            tri.add((s, r, o)); m = [f"fact {s} {r} {o}"]
        elif k < 0.24:  # fact at a new entity (subject or object), on a used relation
            new_i[0] += 1; ne = f"n{new_i[0]}"; r = rng.choice(seq)
            t = (ne, r, rng.choice(ents)) if rng.random() < 0.5 else (rng.choice(ents), r, ne)
            tri.add(t); m = [f"fact {t[0]} {t[1]} {t[2]}"]
            if rng.random() < 0.5:
                ents.append(ne)
        elif k < 0.34 and tri:  # retract a used fact
            cand = [t for t in sorted(tri) if t[1] in seq] or sorted(tri)
            t = rng.choice(cand); tri.discard(t); m = [f"retract {t[0]} {t[1]} {t[2]}"]
        elif k < 0.42 and tri:  # correct a used fact
            cand = [t for t in sorted(tri) if t[1] in seq] or sorted(tri)
            t = rng.choice(cand); o2 = rng.choice(ents)
            tri = {x for x in tri if not (x[0] == t[0] and x[1] == t[1])} | {(t[0], t[1], o2)}
            m = [f"correct {t[0]} {t[1]} {o2}"]
        elif k < 0.48:
            m = [f"complete {' '.join(rng.sample(ents, rng.randint(1, 3)))}"]
        elif k < 0.56:  # contradicting example: suspension, re-acquisition, replacement
            x = rng.choice(ents); m = [f"example {n}: {x} -> {rng.choice(ents)}"]
        elif k < 0.60:
            x = rng.choice(ents); m = [f"correct example {n}: {x} -> {rng.choice(ents)}"]
        elif k < 0.64:
            m = [rng.choice([f"investigate {n}", f"requalify {n}"])]
        elif k < 0.70:  # lexicon: a new word for a capability or relation, or a redefinition
            w = rng.choice(["w1", "w2", "w3"])
            if w not in words:
                words.append(w)
            m = [f"define {w} as {rng.choice(names + rels)}"]
        elif k < 0.74:
            m = [f"express {n} as {rng.choice(['v1', 'v2'] + rels)}"]
        elif k < 0.78:  # library change: a construction for a meaning the answers speak
            a, b = rng.sample(ents, 2); c, d = rng.sample(ents, 2)
            mean = rng.choice(names + ["v1", "v2"])
            m = [f"construct {mean}: {a} {mean} {b} = {a} {b}; {c} {mean} {d} = {c} {d}"]
        elif k < 0.81:
            a, b = rng.sample(ents, 2)
            m = [f"question {n}: which {n} of {a} = {a}; which {n} of {b} = {b}"]
        elif k < 0.87:  # re-teach on another relation (capability replacement)
            seqs[n] = [rng.choice(rels)] + ([rng.choice(rels)] if rng.random() < 0.5 else [])
            m = examples(rng, tri, ents, n, seqs[n], 3) or [f"investigate {n}"]
        elif k < 0.91:  # a new relation, sometimes at entities the answers use
            r = f"r{len(rels)}"; rels.append(r)
            m = [f"fact {rng.choice(ents)} {r} {rng.choice(ents)}" for _ in range(rng.randint(1, 4))]
            for line in m:
                p = line.split(); tri.add((p[1], p[2], p[3]))
        elif k < 0.96:  # mixed call: questions and a mutation together
            r = rng.choice(seq); s = rng.choice(ents); o = rng.choice(ents); tri.add((s, r, o))
            q = questions()
            m = q[:2] + [f"fact {s} {r} {o}"] + q[2:]
        else:
            m = ["__drop__"]  # memo dropped: close the open state
        calls.append(m)
    calls.append(questions())
    return calls


def main():
    N, seed, extra = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3:]
    rng = random.Random(seed)
    tot = {"sessions": N, "calls": 0, "readonly_calls": 0, "gated": 0, "reply_diffs": 0, "state_diffs": 0,
           "final_bytes_diffs": 0, "errors": 0}
    bad = []
    for i in range(N):
        calls = session(rng)
        d = Path(tempfile.mkdtemp())
        srvs = {"REF": (Server(8, check_readonly=False), BASE + extra),
                "IDX": (Server(8, check_readonly=True), BASE + extra + ["--indexed"]),
                "IDX2": (Server(8, check_readonly=False), BASE + extra + ["--indexed"])}
        stop = False
        for j, c in enumerate(calls):
            if c == ["__drop__"]:
                for s, _ in srvs.values():
                    s.close()
                continue
            outs = {}
            for k, (s, fl) in srvs.items():
                try:
                    outs[k] = s.call(d / k / "s.json", fl, c)
                except Exception as exc:  # noqa: BLE001
                    outs[k] = {"error": f"{type(exc).__name__}: {exc}"}
            tot["calls"] += 1
            if any("error" in o for o in outs.values()):
                errs = {k: o.get("error") for k, o in outs.items()}
                if len(set(map(str, errs.values()))) > 1 or "read-only" in str(errs):
                    tot["errors"] += 1; bad.append({"session": i, "call": j, "lines": c[:4], "errors": errs})
                stop = True; break
            tot["readonly_calls"] += bool(outs["IDX"].get("readonly"))
            tot["gated"] += outs["IDX2"]["stats"].get("gated", 0)
            if outs["IDX"].get("readonly"):
                tot["readonly_known_replies"] = tot.get("readonly_known_replies", 0) + sum(
                    not r.startswith(("unknown", "ambiguous")) for r in outs["IDX"]["replies"])
                tot["readonly_ambiguous_replies"] = tot.get("readonly_ambiguous_replies", 0) + sum(
                    r.startswith("ambiguous") for r in outs["IDX"]["replies"])
            if not (outs["REF"]["replies"] == outs["IDX"]["replies"] == outs["IDX2"]["replies"]):
                tot["reply_diffs"] += 1
                k = next(x for x in range(len(c)) if len({outs[a]["replies"][x] for a in outs}) > 1)
                bad.append({"session": i, "call": j, "line": c[k], "replies": {a: outs[a]["replies"][k] for a in outs}})
                stop = True; break
            st = {k: json.dumps(s.cur.state) for k, (s, _) in srvs.items()}
            if len(set(st.values())) > 1:
                tot["state_diffs"] += 1; bad.append({"session": i, "call": j, "lines": c[:4], "state_diff": True})
                stop = True; break
        if not stop:
            for s, _ in srvs.values():
                s.close()
            raws = {k: (d / k / "s.json").read_bytes() for k in srvs}
            if len(set(raws.values())) > 1:
                tot["final_bytes_diffs"] += 1; bad.append({"session": i, "final_bytes_diff": True})
        shutil.rmtree(d)
    print(json.dumps({"seed": seed, "flags": BASE + extra, **tot}))
    for x in bad[:8]:
        print(json.dumps(x)[:1500])


if __name__ == "__main__":
    main()
