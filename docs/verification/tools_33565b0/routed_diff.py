"""Verifier (verify-33565b0): adversarial differential of `--routed` (G58), adapted from the
verify-8994490 tool tools_8994490/incr_diff.py (header below kept for the shared parts).
Arms here: REF (unindexed), XJ64 (--indexed --incremental, K=64), XR (+--routed, read-only check,
K=arg), XR64 (+--routed, registered config). Capability churn (--churn), library padding of
unrelated capabilities (--lib L|mix), entity-set changes, optional G58_AUDIT (--audit). --arms
restricts arms (the 8994490 tree has no --routed); --dump writes per-call hashes of replies and
state and final snapshot/journal hashes of chosen arms for a cross-tree comparison.

Original header: Verifier's adversarial differential test of `--incremental` (G57b, 8994490). Independent of
packetlm/g57_diff.py and the builder's g57b checks.

Four in-process serve.Servers run the same session (long-lived protocol):
  REF   BASE                       (non-indexed; every re-ask executed by the reference code)
  XI    BASE + --indexed           (the G57 engine)
  XJ    BASE + --indexed --incremental, check_readonly=True, full_every=K (argument)
  XJ64  BASE + --indexed --incremental, registered config (K = 64, no read-only check)
After every call: replies equal and json.dumps(state) (insertion order) byte-equal across all four.
After every call, when XJ's persistent index is valid, it is compared against an independent
from-scratch rebuild of EVERY index structure (core + by_rel/by_s/by_o/by_sr/told_rel/small/codes/
codebits/decode), not only the ones ix_check covers (--deep, every call; sampled at big padding).
At the end: snapshot bytes REF = XI = XJ = XJ64 and journal bytes XI = XJ = XJ64.

Operations (adversarial for the index / change-scoped validation): fact add (new subject, new
object-only entity, used relation), re-tell of an existing fact (support append), told-after-derived
(`fact x cap:N y` / derive), retract (3- and 2-arg forms, also of absent facts), correct, complete,
removal of every fact of an object-only entity then re-tell (as object or as subject), mixed calls
(append + removal + append in one call), contradicting examples (suspension / re-acquisition /
replacement), correct example, investigate / requalify / revoke, cap: dependencies (names[1]
composed on names[0]), re-teaching on another relation (replacement / demotion), define / express /
construct / question, new relations, observe / unanswered, why / show / capabilities, memo drops
(close), crashes between calls (Server abandoned without close; journal replay) and torn journal
tails, with optional unrelated padding (benchmarks/g57_scale.padding) at session start.
Usage: incr_diff.py N SEED [--K 64] [--snap 64] [--pad 0|1000|16000|mix] [--deep] [--crash 0.08]
"""
import argparse, json, os, random, shutil, sys, tempfile
from collections import Counter
from pathlib import Path
ROOT = os.environ.get("PL_ROOT") or os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "benchmarks"))
from packetlm.serve import Server  # noqa: E402
from packetlm import engine as E  # noqa: E402
from g57_scale import padding  # noqa: E402
import hashlib  # noqa: E402

def lib_padding(rng, L):  # same construction as benchmarks/g58_libscale.lib_padding (copied: the j0 tree lacks it)
    facts, caps = [], []
    for c in range(L):
        r1, r2 = f"pr{rng.randrange(40)}", f"pr{rng.randrange(40)}"
        ex = []
        for k in range(3):
            a_, b_, o_ = f"pc{c}_{k}", f"pc{c}_{k}m", f"pc{c}_{k}o"
            facts += [f"fact {a_} {r1} {b_}", f"fact {b_} {r2} {o_}"]
            ex.append(f"example pcap{c}: {a_} -> {o_}")
        caps.append(ex)
    return facts, caps


def churn(rng, calls, L):
    """Capability churn and entity-set changes inserted between the session's calls."""
    ents = sorted({w for c in calls for x in c for w in x.split()[1:4:2] if x.startswith("fact ")}) or ["e0"]
    rels = sorted({x.split()[2] for c in calls for x in c if x.startswith("fact ") and len(x.split()) == 4}) or ["r0"]
    names = sorted({x.split(":")[0].split()[-1] for c in calls for x in c if x.startswith("example ")}) or ["zz"]
    pads = [f"pcap{c}" for c in range(L)]
    out, u = [], [0]
    for c in calls:
        out.append(c)
        if c and c[0].startswith("__"):
            continue
        x = rng.random()
        if x < 0.08:
            out.append([f"complete {rng.choice(ents)}"])
        elif x < 0.14:  # observation at an unknown entity, later made known through an unrelated relation
            u[0] += 1; q = f"uq{u[0]}"; n = rng.choice(names)
            out.append([f"example {n}: {q} -> {rng.choice(ents)}"])
            out.append([f"what is {q} {n}"])
            out.append([f"fact {q} rz{rng.randrange(3)} {rng.choice(ents)}", f"what is {q} {n}"])
            if rng.random() < 0.5:  # ... and unknown again (every fact of it retracted)
                out.append([f"retract {q} rz0", f"retract {q} rz1", f"retract {q} rz2", f"what is {q} {n}"])
        elif x < 0.19:  # composition over two capabilities (dependency closures)
            a, b = rng.choice(names), rng.choice(names)
            out.append([f"example k{a}{b}: {rng.choice(ents)} -> {rng.choice(ents)}"])
        elif x < 0.25:
            out.append([f"{rng.choice(['requalify', 'revoke', 'learn', 'investigate'])} {rng.choice(names + pads[:4] + ['k' + names[0] + names[-1]])}"])
        elif x < 0.29 and pads:  # touch an unrelated library capability (contradict / re-confirm / ask)
            c2 = rng.randrange(L); k = rng.randrange(3)
            out.append(rng.choice([[f"example pcap{c2}: pc{c2}_{k} -> pc{c2}_{k}m"], [f"example pcap{c2}: pc{c2}_{k} -> pc{c2}_{k}o"],
                                   [f"what is pc{c2}_{k} pcap{c2}", f"retract pc{c2}_{k}m"], [f"fact pc{c2}_{k} {rng.choice(rels)} {rng.choice(ents)}"]]))
        elif x < 0.33:  # a new relation shared with a library capability's first relation, and a composition on it
            r = f"pr{rng.randrange(40)}"; e1, e2, e3 = rng.sample(ents, 3) if len(ents) >= 3 else (ents[0],) * 3
            out.append([f"fact {e1} {r} {e2}", f"fact {e2} {rng.choice(rels)} {e3}", f"example nw{rng.randrange(3)}: {e1} -> {e3}"])
        elif x < 0.36:
            out.append([f"correct example {rng.choice(names)}: {rng.choice(ents)} -> {rng.choice(ents)}"])
        elif x < 0.38:
            out.append(["capabilities", f"show {rng.choice(names)}", f"why {rng.choice(ents)} {rng.choice(names)}"])
    return out


DUMP = {}


def h(x):
    return hashlib.sha256(x if isinstance(x, bytes) else x.encode()).hexdigest()[:16]

BASE = ["--answers", "--bounded", "--lean", "--deepen=3"]
PERIOD = Counter()
_orig_validate = Server._validate


def _counting_validate(self, o, eng):
    """Counts K-period full validations: the call would have been scoped but since_full reached K."""
    sc = o.memo.scope if eng.incremental else None
    if sc is not None and sc["ok"] and o.memo.ix_valid(eng.state) and o.since_full + 1 >= self.full_every:
        PERIOD[f"K{self.full_every}"] += 1
    return _orig_validate(self, o, eng)


Server._validate = _counting_validate


def deep_index_check(srv):
    """Independent full rebuild of every persistent-index structure; returns a list of mismatches."""
    o = srv.cur
    if o is None or o.memo is None or not o.memo.ix_valid(o.state):
        return None
    ix, facts = o.memo.ix, o.state["facts"]
    bad = []
    names, pos, triples = [], {}, []
    for f in facts:
        for t in (f["s"], f["o"]):
            if t not in pos:
                pos[t] = len(names); names.append(t)
        triples.append((f["s"], f["r"], f["o"]))
    if ix["names"] != names: bad.append("names")
    if ix["pos"] != pos: bad.append("pos")
    if ix["triples"] != triples: bad.append("triples")
    out = {}
    for s, r, _ in triples:
        out.setdefault(s, set()).add(r)
    if ix["out"] != out: bad.append("out")
    ref = {}
    for s, r, ob in triples:
        ref.setdefault(r, {}).setdefault(s, set()).add(ob)
    if ix["ref"] != ref: bad.append("ref")
    if list(ix["byid"]) != [f["id"] for f in facts] or any(ix["byid"][f["id"]] is not f for f in facts): bad.append("byid")
    by_rel, by_s, by_o, by_sr = {}, {}, {}, {}
    for f in facts:
        t = (f["s"], f["r"], f["o"])
        by_rel.setdefault(t[1], []).append(t); by_s.setdefault(t[0], []).append(t)
        by_o.setdefault(t[2], []).append(t); by_sr.setdefault((t[0], t[1]), []).append(f)
    if ix["by_rel"] != by_rel: bad.append("by_rel")
    if ix["by_s"] != by_s: bad.append("by_s")
    if ix["by_o"] != by_o: bad.append("by_o")
    if {k: [id(x) for x in v] for k, v in ix["by_sr"].items()} != {k: [id(x) for x in v] for k, v in by_sr.items()}: bad.append("by_sr")
    told = Counter(f["r"] for f in facts if not f["r"].startswith("cap:") and any(sp["kind"] == "told" for sp in f["supports"]))
    if +ix["told_rel"] != told: bad.append("told_rel")
    codes = {c for t in triples for c in ((0, t[0]), (1, t[1]), (2, t[2]))}
    if ix["codes"] != codes: bad.append("codes")
    cb = {}
    for c in codes:
        for b in E._geom().bits(E.bits_for(c[1], c[0])):
            cb.setdefault(b, set()).add(c)
    if {b: set(v) for b, v in ix["codebits"].items()} != cb or any(len(v) != len(set(v)) for v in ix["codebits"].values()): bad.append("codebits")
    small = [t for t in triples if E.Memo.packet(t).bit_count() < E.SMALL_PACKET]
    if sorted(ix["small"]) != sorted(small) or len(ix["small"]) != len(small): bad.append("small")
    dec = {E.pack(E.bits_for(t, 2)).bits: t for t in names}
    if ix["decode"] is not None and ix["decode"] != dec: bad.append("decode")
    # sparse rows cached in prow must equal rows recomputed from the facts of that relation
    return bad


def harvest(srvs, counts):
    for k in [x for x in ("XJ64", "XR", "XR64") if x in srvs]:
        o = srvs[k].cur
        if o is not None and o.memo is not None and not getattr(o.memo, "_harvested", False):
            counts.update({f"{k}.{x}": v for x, v in o.memo.counts.items()})
            counts[f"{k}.ix_checks"] += o.memo.ix_checks
            o.memo._harvested = True


def world(rng):
    ents = [f"e{i}" for i in range(rng.randint(6, 11))]
    rels = [f"r{i}" for i in range(rng.randint(2, 4))]
    tri = set()
    for r in rels:
        for x in ents:
            if rng.random() < 0.7:
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


def session(rng, crash_p, rounds=(10, 22)):
    ents, rels, tri = world(rng)
    names = rng.sample(["zz", "kk", "aa", "mm", "qq", "bb"], 3)
    seqs = {names[0]: [rng.choice(rels)], names[2]: [rng.choice(rels), rng.choice(rels)]}
    seqs[names[1]] = seqs[names[0]] + [rng.choice(rels)]
    calls = [[f"fact {s} {r} {o}" for s, r, o in sorted(tri)]]
    for n in names:
        ex = examples(rng, tri, ents, n, seqs[n], 3)
        if ex:
            calls.append(ex)
    words, newi, objonly = [], [0], []

    def newent(p="n"):
        newi[0] += 1
        return f"{p}{newi[0]}"

    def questions():
        qs = []
        for n in names + words + rels[:2]:
            pool = rng.sample(ents, min(len(ents), rng.randint(2, len(ents)))) + ["zq"] + objonly[-2:]
            for x in pool:
                form = rng.choice(["what is {x} {n}", "What is {x} {n}?", "ask {x} {n}"])
                qs.append(form.format(x=x, n=n))
        rng.shuffle(qs)
        qs = qs[:rng.randint(3, 20)]
        if rng.random() < 0.1:
            qs.append(rng.choice([f"why {rng.choice(ents)} {rng.choice(names)}", f"show {rng.choice(names)}", "capabilities"]))
        return qs

    for _ in range(rng.randint(*rounds)):
        calls.append(questions())
        if rng.random() < 0.4:
            calls.append(questions())
        k = rng.random(); n = rng.choice(names); seq = seqs[n]
        if k < 0.09:  # fact on a used relation
            r = rng.choice(seq); t = (rng.choice(ents), r, rng.choice(ents)); tri.add(t); m = [f"fact {t[0]} {t[1]} {t[2]}"]
        elif k < 0.15:  # object-only new entity
            ne = newent("o"); t = (rng.choice(ents), rng.choice(seq), ne); tri.add(t); objonly.append(ne)
            m = [f"fact {t[0]} {t[1]} {t[2]}"]
        elif k < 0.21 and objonly:  # remove every fact of an object-only entity, then (maybe same call) re-tell it
            ne = rng.choice(objonly)
            ts = [t for t in sorted(tri) if ne in (t[0], t[2])]
            m = [f"retract {t[0]} {t[1]} {t[2]}" for t in ts]
            for t in ts:
                tri.discard(t)
            if rng.random() < 0.6:
                t = (ne, rng.choice(rels), rng.choice(ents)) if rng.random() < 0.5 else (rng.choice(ents), rng.choice(rels), ne)
                tri.add(t); m.append(f"fact {t[0]} {t[1]} {t[2]}")
            if rng.random() < 0.5:
                m = [f"what is {ne} {n}"] + m + [f"what is {ne} {n}", f"what is {rng.choice(ents)} {n}"]
        elif k < 0.26 and tri:  # re-tell an existing fact (support append) / told-after-derived
            t = rng.choice(sorted(tri)); m = [f"fact {t[0]} {t[1]} {t[2]}"]
            if rng.random() < 0.5:
                x = rng.choice(ents); m = [f"derive {n} {x}"] + [f"fact {x} cap:{n} {y}" for y in sorted(run_path(tri, seq, x))][:1]
        elif k < 0.33 and tri:  # retract used fact (3-arg) / 2-arg / absent
            u = rng.random()
            if u < 0.6:
                t = rng.choice([t for t in sorted(tri) if t[1] in seq] or sorted(tri)); tri.discard(t); m = [f"retract {t[0]} {t[1]} {t[2]}"]
            elif u < 0.85:
                s, r = rng.choice(ents), rng.choice(rels); tri = {x for x in tri if not (x[0] == s and x[1] == r)}; m = [f"retract {s} {r}"]
            else:
                m = [f"retract zq {rng.choice(rels)} {rng.choice(ents)}"]
        elif k < 0.39 and tri:
            t = rng.choice([t for t in sorted(tri) if t[1] in seq] or sorted(tri)); o2 = rng.choice(ents + [t[2]])
            tri = {x for x in tri if not (x[0] == t[0] and x[1] == t[1])} | {(t[0], t[1], o2)}; m = [f"correct {t[0]} {t[1]} {o2}"]
        elif k < 0.44:
            m = [f"complete {' '.join(rng.sample(ents, rng.randint(1, 3)))}"]
        elif k < 0.51:
            m = [f"example {n}: {rng.choice(ents)} -> {rng.choice(ents)}"]
        elif k < 0.54:
            m = [f"correct example {n}: {rng.choice(ents)} -> {rng.choice(ents)}"]
        elif k < 0.58:
            m = [rng.choice([f"investigate {n}", f"requalify {n}", f"revoke {n}", f"learn {n}"])]
        elif k < 0.62:
            w = rng.choice(["w1", "w2"]); words.append(w) if w not in words else None
            m = [f"define {w} as {rng.choice(names + rels)}"]
        elif k < 0.64:
            m = [f"express {n} as {rng.choice(['v1'] + rels)}"]
        elif k < 0.66:
            a, b = rng.sample(ents, 2); c, d = rng.sample(ents, 2); mean = rng.choice(names + ["v1"])
            m = [f"construct {mean}: {a} {mean} {b} = {a} {b}; {c} {mean} {d} = {c} {d}"]
        elif k < 0.68:
            a, b = rng.sample(ents, 2); m = [f"question {n}: which {n} of {a} = {a}; which {n} of {b} = {b}"]
        elif k < 0.74:  # re-teach (replacement / demotion); also changes names[1]'s dependency
            seqs[n] = [rng.choice(rels)] + ([rng.choice(rels)] if rng.random() < 0.5 else [])
            m = examples(rng, tri, ents, n, seqs[n], 3) or [f"investigate {n}"]
        elif k < 0.78:
            r = f"r{len(rels)}"; rels.append(r)
            m = [f"fact {rng.choice(ents)} {r} {rng.choice(ents)}" for _ in range(rng.randint(1, 4))]
            for line in m:
                p = line.split(); tri.add((p[1], p[2], p[3]))
        elif k < 0.85 and tri:  # mixed: append, removal, append (+ questions) in one call
            t1 = (rng.choice(ents), rng.choice(seq), newent()); t2 = rng.choice(sorted(tri)); t3 = (t1[2], rng.choice(rels), rng.choice(ents))
            tri.add(t1); tri.discard(t2); tri.add(t3)
            m = [f"fact {t1[0]} {t1[1]} {t1[2]}", f"what is {t1[0]} {n}", f"retract {t2[0]} {t2[1]} {t2[2]}",
                 f"fact {t3[0]} {t3[1]} {t3[2]}", f"what is {t1[2]} {n}"]
        elif k < 0.855:  # a brand-new subject (alone, or after a removal in the same call)
            ne = newent("s"); t = (ne, rng.choice(seq), rng.choice(ents)); tri.add(t); ents.append(ne)
            m = [f"fact {t[0]} {t[1]} {t[2]}"]
            if tri and rng.random() < 0.4:
                t2 = rng.choice(sorted(tri - {t})); tri.discard(t2); m = [f"retract {t2[0]} {t2[1]} {t2[2]}"] + m
        elif k < 0.865:  # PX negative statements (!none / !several), also outside the domain
            m = [f"example {n}: {rng.choice(ents + ['zq'])} -> {rng.choice(['!none', '!several'])}"]
        elif k < 0.88:
            m = [f"observe {rng.choice(ents)} {n} {rng.choice(ents)}"] + ([f"unanswered {n}: {rng.choice(ents)}"] if rng.random() < 0.5 else [])
        elif k < 0.93:
            r = rng.choice(seq); t = (rng.choice(ents), r, rng.choice(ents)); tri.add(t)
            q = questions(); m = q[:2] + [f"fact {t[0]} {t[1]} {t[2]}"] + q[2:]
        else:
            m = ["__drop__"]
        calls.append(m)
        if rng.random() < crash_p:
            calls.append([rng.choice(["__crash__", "__torn__"])])
    calls.append(questions())
    return calls


def session_append(rng, n_calls):
    """Append-only stream (no removals, so nothing forces a full validation): the K-period guard
    is the only full validation between snapshots. Facts at used relations, new subjects, new
    object-only entities, re-tells, examples (new capabilities and contradictions), questions."""
    ents, rels, tri = world(rng)
    names = rng.sample(["zz", "kk", "aa", "mm", "qq", "bb"], 3)
    seqs = {n: [rng.choice(rels)] for n in names}
    calls = [[f"fact {s} {r} {o}" for s, r, o in sorted(tri)]]
    for n in names:
        ex = examples(rng, tri, ents, n, seqs[n], 3)
        if ex:
            calls.append(ex)
    i = 0
    while len(calls) < n_calls:
        i += 1
        k = rng.random(); n = rng.choice(names)
        if k < 0.35:
            calls.append([f"what is {rng.choice(ents)} {rng.choice(names + rels)}" for _ in range(rng.randint(2, 8))])
        elif k < 0.6:
            t = (rng.choice(ents), rng.choice(seqs[n]), rng.choice(ents)); tri.add(t); calls.append([f"fact {t[0]} {t[1]} {t[2]}"])
        elif k < 0.72:
            ne = f"s{i}"; t = (ne, rng.choice(rels), rng.choice(ents)); tri.add(t); ents.append(ne); calls.append([f"fact {t[0]} {t[1]} {t[2]}"])
        elif k < 0.8:
            t = (rng.choice(ents), rng.choice(rels), f"o{i}"); tri.add(t); calls.append([f"fact {t[0]} {t[1]} {t[2]}", f"what is {t[2]} {n}"])
        elif k < 0.86 and tri:
            t = rng.choice(sorted(tri)); calls.append([f"fact {t[0]} {t[1]} {t[2]}"])
        elif k < 0.93:
            calls.append([f"example {n}: {rng.choice(ents)} -> {rng.choice(ents + ['!none'])}"])
        else:
            r = f"r{len(rels)}"; rels.append(r); t = (rng.choice(ents), r, rng.choice(ents)); tri.add(t)
            calls.append([f"fact {t[0]} {t[1]} {t[2]}", f"what is {t[0]} {r}"])
    return calls


def norm_journal(b):
    """Journal bytes with "--routed" removed from every record's flags (the only allowed difference)."""
    out = []
    for line in b.split(b"\n"):
        if not line.strip():
            out.append(line); continue
        try:
            r = json.loads(line)
        except Exception:  # noqa: BLE001 -- a torn tail is kept verbatim
            out.append(line); continue
        if isinstance(r, dict) and isinstance(r.get("flags"), list):
            r["flags"] = [f for f in r["flags"] if f != "--routed"]
        out.append(json.dumps(r, sort_keys=True).encode())
    return b"\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("N", type=int); ap.add_argument("seed", type=int)
    ap.add_argument("--K", type=int, default=64); ap.add_argument("--snap", type=int, default=64)
    ap.add_argument("--pad", default="0"); ap.add_argument("--deep", action="store_true")
    ap.add_argument("--crash", type=float, default=0.08); ap.add_argument("--extra", default=""); ap.add_argument("--rounds", default="10,22"); ap.add_argument("--nodrop", action="store_true"); ap.add_argument("--appendonly", type=int, default=0)
    ap.add_argument("--lib", default="0"); ap.add_argument("--churn", action="store_true"); ap.add_argument("--audit", action="store_true")
    ap.add_argument("--arms", default="REF,XJ64,XR,XR64"); ap.add_argument("--dump", default="")
    a = ap.parse_args()
    arms = a.arms.split(",")
    if a.audit:
        E.G58_AUDIT.update(on=True, log=[])
    extra = a.extra.split() if a.extra else []
    rng = random.Random(a.seed)
    tot = Counter(sessions=a.N); bad = []; counts = Counter(); dump = []
    for i in range(a.N):
        pad_n = rng.choice([0, 0, 1000]) if a.pad == "mix" else int(a.pad)
        lib_n = rng.choice([0, 4, 16, 64]) if a.lib == "mix" else int(a.lib)
        prng = random.Random(a.seed * 7919 + i)
        pf, pc = padding(prng, pad_n) if pad_n else ([], [])
        lf, lc = lib_padding(random.Random(a.seed * 104729 + i), lib_n) if lib_n else ([], [])
        calls = session(rng, a.crash, tuple(int(x) for x in a.rounds.split(","))) if not a.appendonly else session_append(rng, a.appendonly)
        if a.churn:
            calls = churn(random.Random(a.seed * 31 + i), calls, lib_n)
        if a.nodrop:
            calls = [c for c in calls if c != ["__drop__"]]
        pre = [pf[k:k + 2000] for k in range(0, len(pf), 2000)] + pc + [lf[k:k + 2000] for k in range(0, len(lf), 2000)] + lc
        d = Path(tempfile.mkdtemp(dir="/tmp"))
        spec = {"REF": dict(fl=BASE + extra, ro=False, K=None),
                "XJ64": dict(fl=BASE + extra + ["--indexed", "--incremental"], ro=False, K=64),
                "XR": dict(fl=BASE + extra + ["--indexed", "--incremental", "--routed"], ro=True, K=a.K),
                "XR64": dict(fl=BASE + extra + ["--indexed", "--incremental", "--routed"], ro=False, K=64)}
        spec = {k: v for k, v in spec.items() if k in arms}
        mk = lambda k: Server(a.snap, check_readonly=spec[k]["ro"], full_every=spec[k]["K"])  # noqa: E731
        srvs = {k: mk(k) for k in spec}
        stop = False
        seq_calls = [("pad", c) for c in pre] + [("s", c) for c in calls]
        sd = {"session": i, "calls": []}
        for j, (kind, c) in enumerate(seq_calls):
            if c == ["__drop__"]:
                harvest(srvs, counts)
                for s in srvs.values():
                    s.close()
                tot["drops"] += 1; continue
            if c in (["__crash__"], ["__torn__"]):
                harvest(srvs, counts)
                for k in list(srvs):
                    o = srvs[k].cur
                    if o is not None and o.jfh:
                        o.jfh.close()
                        if c == ["__torn__"]:
                            with open(o.jpath, "ab") as fh:
                                fh.write(b'{"flags": ["--answ')
                    srvs[k] = mk(k)
                tot["crashes" if c == ["__crash__"] else "torn"] += 1; continue
            outs = {}
            for k, s in srvs.items():
                try:
                    outs[k] = s.call(d / k / "s.json", spec[k]["fl"], c)
                except Exception as exc:  # noqa: BLE001
                    outs[k] = {"error": f"{type(exc).__name__}: {exc}"}
            tot["calls"] += 1
            if any("error" in o for o in outs.values()):
                errs = {k: o.get("error") for k, o in outs.items()}
                tot["errors"] += 1; bad.append({"session": i, "call": j, "lines": c[:6], "errors": errs}); stop = True; break
            if "XR" in outs:
                tot["readonly_calls"] += bool(outs["XR"].get("readonly"))
            ks = list(outs)
            if len({json.dumps(outs[q]["replies"]) for q in ks}) > 1:
                tot["reply_diffs"] += 1
                kk = next(x for x in range(len(c)) if len({outs[q]["replies"][x] for q in outs}) > 1)
                bad.append({"session": i, "call": j, "line": c[kk], "replies": {q: outs[q]["replies"][kk] for q in outs}}); stop = True; break
            st = {k: json.dumps(s.cur.state) for k, s in srvs.items()}
            if len(set(st.values())) > 1:
                tot["state_diffs"] += 1; bad.append({"session": i, "call": j, "lines": c[:6], "state_diff": [k for k in st if st[k] != st[ks[0]]]}); stop = True; break
            if a.dump:
                sd["calls"].append(h(json.dumps(outs[ks[-1]]["replies"])) + h(st[ks[-1]]))
            if a.deep and (pad_n < 16000 or j % 7 == 0 or kind == "s" and j == len(seq_calls) - 1):
                for k in [x for x in ("XJ64", "XR", "XR64") if x in srvs]:
                    r = deep_index_check(srvs[k])
                    if r is None:
                        tot["deep_skipped_invalid"] += 1
                    else:
                        tot["deep_checks"] += 1
                        if r:
                            tot["deep_diffs"] += 1; bad.append({"session": i, "call": j, "server": k, "deep": r}); stop = True
                if stop:
                    break
            if a.audit and E.G58_AUDIT["log"]:
                tot["audit_violations"] += len(E.G58_AUDIT["log"]); bad.append({"session": i, "call": j, "audit": E.G58_AUDIT["log"][:3]})
                E.G58_AUDIT["log"].clear(); stop = True; break
        harvest(srvs, counts)
        if not stop:
            for s in srvs.values():
                s.close()
            raws = {k: (d / k / "s.json").read_bytes() for k in srvs}
            if len(set(raws.values())) > 1:
                tot["final_bytes_diffs"] += 1; bad.append({"session": i, "final_bytes_diff": True})
            js = {k: norm_journal((d / k / "s.json.journal").read_bytes()) for k in srvs if k != "REF"}
            if len(set(js.values())) > 1:
                tot["journal_diffs"] += 1; bad.append({"session": i, "journal_diff": True})
            if a.dump:
                k = list(srvs)[-1]
                sd["final"] = h(raws[k]); sd["journal"] = h(norm_journal((d / k / "s.json.journal").read_bytes()))
        else:
            sd["stopped"] = True
        dump.append(sd)
        shutil.rmtree(d)
    if a.dump:
        Path(a.dump).write_text(json.dumps(dump))
    print(json.dumps({"seed": a.seed, "K": a.K, "snap": a.snap, "pad": a.pad, "lib": a.lib, "churn": a.churn, "audit": a.audit,
                      "arms": arms, "flags": BASE + extra, **tot, "path_counts": dict(counts), "period_full_validations": dict(PERIOD)}))
    for x in bad[:10]:
        print(json.dumps(x)[:2000])


if __name__ == "__main__":
    main()
