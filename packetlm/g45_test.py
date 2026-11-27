"""G45 qualification: procedures taught through the interface, unfamiliar domains.

The harness plays the teacher. It holds each domain's hidden program and only
uses it to answer questions, the way a person would. Every engine call is a new
process (`python -m packetlm.engine STATE ...`). Protocol and thresholds:
docs/G45.md (committed before this ran). Not a mind.
"""

from __future__ import annotations
import hashlib
import json
import random
import string
import subprocess
import sys
import tempfile
import time
from itertools import permutations
from pathlib import Path
from . import reference

ROOT = Path(__file__).resolve().parent.parent
ORDERS = list(permutations(["s", "r", "o"]))
SHAPES = {1: "a+b", 2: "a+a", 3: "b+a", 4: "a+b (confounder d)", 5: "cap(D1)+e", 6: "b+c (sparse b)"}


def source_hash() -> str:
    h = hashlib.sha256()
    for p in sorted((ROOT / "packetlm").glob("*.py")):
        h.update(p.name.encode() + p.read_bytes())
    return h.hexdigest()


class Names:
    def __init__(self, rng):
        self.rng, self.used = rng, set()

    def __call__(self, k=6):
        while True:
            w = "".join(self.rng.choice(string.ascii_lowercase) for _ in range(k))
            if w not in self.used and w not in {"what", "is", "fact", "why", "show", "learn", "example"}:
                self.used.add(w)
                return w


def layers(nm, n=12, k=4):
    return [[nm() for _ in range(n)] for _ in range(k)]


def functional(rng, src, dst):
    d = list(dst)
    rng.shuffle(d)
    return list(zip(src, d))


def build(rng, nm, idx, d1=None):
    L = layers(nm)
    rel = {k: nm() for k in "abcd"}
    triples = []
    for r in "abcd":
        for k in range(3):
            triples += [(s, rel[r], o) for s, o in functional(rng, L[k], L[k + 1])]
    examples = L[0][:2]
    if idx == 4:  # d agrees with a on the example subjects
        amap = {s: o for s, r, o in triples if r == rel["a"]}
        triples = [(s, r, amap[s]) if r == rel["d"] and s in examples else (s, r, o) for s, r, o in triples]
    if idx == 6:  # missing b knowledge for three non-example subjects
        gone = set(L[0][2:5])
        triples = [t for t in triples if not (t[1] == rel["b"] and t[0] in gone)]
    target = {1: "ab", 2: "aa", 3: "ba", 4: "ab", 6: "bc"}.get(idx)
    dom = {"idx": idx, "shape": SHAPES[idx], "rel": rel, "layers": L, "name": nm(), "order": rng.choice(ORDERS)}
    if idx == 5:
        e = nm()
        ends = [nm() for _ in range(12)]
        d1_l2 = d1["layers"][2]
        triples = [(s, e, o) for s, o in functional(rng, d1_l2, ends)]
        dom.update({"rel": {"e": e}, "subjects": d1["layers"][0], "base": d1["base"] + [e], "triples": triples})
        dom["examples"] = d1["layers"][0][:2]
        return dom
    dom.update({"subjects": L[0], "base": [rel[c] for c in target], "triples": triples, "examples": examples})
    return dom


class Teacher:
    def __init__(self, state, flags=(), log=None):
        self.state, self.flags, self.log, self.calls, self.cpu = state, list(flags), log if log is not None else [], 0, 0.0

    def __call__(self, *lines):
        t = time.perf_counter()
        p = subprocess.run([sys.executable, "-m", "packetlm.engine", str(self.state), *self.flags, *lines],
                           cwd=ROOT, capture_output=True, text=True, timeout=600)
        self.calls += 1
        if p.returncode:
            raise RuntimeError(p.stderr[-800:])
        out = json.loads(p.stdout)
        self.cpu += out["cpu_s"]
        self.log.append({"lines": list(lines), "replies": out["replies"], "load": out["load"],
                         "stats": out["stats"], "cpu_s": out["cpu_s"], "cpu_total_s": out.get("cpu_total_s"),
                         "wall_s": round(time.perf_counter() - t, 3)})
        return out["replies"]


def sentence(order, s, word, o):
    return " ".join({"s": s, "r": word, "o": o}[k] for k in order)


def teach_domain(T, dom, truth, nm, shuffled=False, rng=None):
    a = dom["rel"].get("a")
    lines = []
    if a:
        x1, y1, x2, y2 = nm(), nm(), nm(), nm()
        lines.append(f"construct {a}: {sentence(dom['order'], x1, a, y1)} = {x1} {y1}; {sentence(dom['order'], x2, a, y2)} = {x2} {y2}")
    for s, r, o in dom["triples"]:
        lines.append(sentence(dom["order"], s, r, o) if r == a else f"fact {s} {r} {o}")
    ex = dom["examples"]
    vals = [truth(s) for s in ex]
    if shuffled:
        vals = vals[1:] + vals[:1]
    lines += [f"example {dom['name']}: {s} -> {v}" for s, v in zip(ex, vals)]
    replies = T(*lines)
    status = replies[-1].split()[0]
    asked = []
    for _ in range(6):
        if status == "qualified":
            break
        q = T(f"investigate {dom['name']}")[0]
        if not q.startswith("what is "):
            break
        subj = q.split()[2]
        asked.append(subj)
        ans = truth(rng.choice(dom["subjects"])) if shuffled else truth(subj)
        if ans is None:
            T(f"unanswered {dom['name']}: {subj}")
            continue
        status = T(f"example {dom['name']}: {subj} -> {ans}")[0].split()[0]
    return status, asked


def parse(reply, s, name):
    t = reply.split()
    if reply.startswith(f"{s} {name} ") and len(t) >= 3:
        return t[2], "[provisional]" in reply
    return None, False


def evaluate(T, items):
    replies = T(*[f"what is {s} {n}" for s, n, _ in items]) if items else []
    out = []
    for (s, n, truth), r in zip(items, replies):
        v, prov = parse(r, s, n)
        out.append({"s": s, "name": n, "truth": truth, "got": v, "provisional": prov, "reply": r})
    return out


def score(rows):
    defined = [r for r in rows if r["truth"] is not None]
    answered = [r for r in defined if r["got"] is not None]
    wrong = [r for r in answered if r["got"] != r["truth"]]
    wrong_q = [r for r in wrong if not r["provisional"]]
    return {"defined": len(defined), "answered": len(answered), "wrong": len(wrong), "wrong_qualified": len(wrong_q),
            "provisional": sum(r["provisional"] for r in answered),
            "coverage": round(len(answered) / max(len(defined), 1), 3),
            "spurious_on_undefined": sum(1 for r in rows if r["truth"] is None and r["got"] is not None)}


def run_seed(seed, tmp, shuffled=False):
    rng = random.Random(seed)
    nm = Names(rng)
    state = tmp / f"g45_{seed}{'_shuf' if shuffled else ''}.json"
    T = Teacher(state)
    world, doms, report = [], [], []
    for idx in range(1, 7):
        dom = build(rng, nm, idx, doms[0] if doms else None)
        doms.append(dom)
        world += dom["triples"]
        idx_ref = reference.index(world)

        def truth(s, base=dom["base"], idx_ref=idx_ref):
            out = reference.run(idx_ref, base, s)
            return next(iter(out)) if len(out) == 1 else None
        status, asked = teach_domain(T, dom, truth, nm, shuffled, rng)
        st = json.loads(state.read_text())["state"]
        cap = st["capabilities"].get(dom["name"])
        ver = cap["versions"][cap["current"] - 1] if cap and cap["current"] else None
        held = [s for s in dom["subjects"] if s not in dom["examples"] and s not in asked]
        rows = evaluate(T, [(s, dom["name"], truth(s)) for s in held])
        report.append({"domain": idx, "shape": dom["shape"], "name": dom["name"], "status": ver["status"] if ver else status,
                       "seq": ver["seq"] if ver else None, "base": ver["base"] if ver else None, "hidden": dom["base"],
                       "match": bool(ver) and ver["base"] == dom["base"], "examples": len(dom["examples"]) + len(asked),
                       "questions": asked, "eval": score(rows), "rows": rows,
                       "evaluations": st["hypotheses"].get(dom["name"], {}).get("evaluated")})
    # transfer: new entities for D1's relations
    d1 = doms[0]
    a1, b1 = d1["rel"]["a"], d1["rel"]["b"]
    L = layers(nm, 12, 3)
    tr = [(s, a1, o) for s, o in functional(rng, L[0], L[1])] + [(s, b1, o) for s, o in functional(rng, L[1], L[2])]
    T(*[sentence(d1["order"], s, r, o) if r == a1 else f"fact {s} {r} {o}" for s, r, o in tr])
    tref = reference.index(tr)
    trows = evaluate(T, [(s, d1["name"], next(iter(reference.run(tref, d1["base"], s)))) for s in L[0]])
    # retention: one more fresh process re-asks everything
    items = [(r["s"], r["name"], r["truth"]) for d in report for r in d["rows"]] + [(r["s"], r["name"], r["truth"]) for r in trows]
    final = evaluate(T, items)
    before = [r["reply"] for d in report for r in d["rows"]] + [r["reply"] for r in trows]
    after = [r["reply"] for r in final]
    # S1 of cdb4828: told facts added inside a qualified capability's region re-run its scan, so a
    # later domain built on an earlier one's world can demote it to provisional (a real alternative
    # appeared). Retention then means: every value identical, and every changed reply is the same
    # value now marked provisional, of a capability whose current version was re-scanned to
    # provisional with blockers on current facts.
    st = json.loads(state.read_text())["state"]
    strip = lambda x: x.replace(" [provisional]", "")
    changed = [(it[1], b, a) for it, b, a in zip(items, before, after) if b != a]

    def demoted(name):
        cap = st["capabilities"][name]
        ver = cap["versions"][cap["current"] - 1]
        return ver["status"] == "provisional" and "qualified" in [h["status"] for h in ver["history"]] \
            and ver["history"][-1]["reason"] == "requalified" and int(ver["evidence"].get("blocking", 0)) > 0
    retention_ok = all(strip(b) == strip(a) and a.endswith("[provisional]") and demoted(n) for n, b, a in changed)
    return {"seed": seed, "shuffled": shuffled, "domains": report, "transfer": score(trows),
            "retention_identical": retention_ok, "retention_strict_identical": not changed,
            "retention_demoted": sorted({n for n, _, _ in changed}), "retention_items": len(final),
            "processes": T.calls, "engine_cpu_s": round(T.cpu, 3), "state_bytes": state.stat().st_size,
            "sessions": T.log}


def no_library_control(seed, tmp):
    rng = random.Random(seed)
    nm = Names(rng)
    T = Teacher(tmp / f"nolib_{seed}.json", ["--no-library"])
    d1 = build(rng, nm, 1)
    ref1 = reference.index(d1["triples"])
    teach_domain(T, d1, lambda s: next(iter(reference.run(ref1, d1["base"], s))), nm, rng=rng)
    for idx in range(2, 5):
        build(rng, nm, idx)  # keep the generator aligned with run_seed
    d5 = build(rng, nm, 5, d1)
    ref5 = reference.index(d1["triples"] + d5["triples"])
    status, _ = teach_domain(T, d5, lambda s: (lambda o: next(iter(o)) if len(o) == 1 else None)(reference.run(ref5, d5["base"], s)), nm, rng=rng)
    st = json.loads((tmp / f"nolib_{seed}.json").read_text())["state"]
    return {"seed": seed, "status": status, "acquired": d5["name"] in st["capabilities"],
            "evaluated": st["hypotheses"].get(d5["name"], {}).get("evaluated")}


def run() -> dict:
    h0 = source_hash()
    seeds = [101, 202, 303]
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        runs = [run_seed(s, tmp) for s in seeds]
        shuf = [run_seed(s, tmp, shuffled=True) for s in seeds]
        nolib = [no_library_control(s, tmp) for s in seeds]
    h1 = source_hash()
    per_seed = {}
    for r in runs:
        ds = r["domains"]
        per_seed[r["seed"]] = {
            "t1_matches_ge_5": sum(d["match"] for d in ds) >= 5,
            "t2_zero_wrong_qualified": all(d["eval"]["wrong_qualified"] == 0 for d in ds if d["status"] == "qualified"),
            "t3_coverage_ge_0_9": all(d["eval"]["coverage"] >= 0.9 for d in ds if d["match"]),
            "t4_transfer": r["transfer"]["wrong"] == 0 and r["transfer"]["coverage"] >= 0.9,
            "t5_retention": r["retention_identical"],
        }
    checks = {f"seed{s}.{k}": v for s, c in per_seed.items() for k, v in c.items()}
    checks["t6_source_unchanged"] = h0 == h1
    checks["t7a_shuffled_at_most_1"] = all(sum(d["match"] for d in r["domains"]) <= 1 for r in shuf)
    # strict reading of the registered wording "fails to acquire D5" (verification L2): no acquisition at any status
    checks["t7b_no_library_fails_d5"] = all(not c["acquired"] for c in nolib)
    failed = [k for k, v in checks.items() if not v]
    summary = [{"seed": r["seed"], "domains": [{k: d[k] for k in ("domain", "shape", "status", "match", "examples", "evaluations")}
                                              | {"eval": d["eval"]} for d in r["domains"]],
                "transfer": r["transfer"], "retention_items": r["retention_items"],
                "retention_strict_identical": r["retention_strict_identical"], "retention_demoted": r["retention_demoted"], "processes": r["processes"],
                "engine_cpu_s": r["engine_cpu_s"], "state_bytes": r["state_bytes"]} for r in runs]
    shuf_summary = [{"seed": r["seed"], "matches": sum(d["match"] for d in r["domains"]),
                     "statuses": [d["status"] for d in r["domains"]],
                     "wrong_qualified": sum(d["eval"]["wrong_qualified"] for d in r["domains"])} for r in shuf]
    receipt = {"checks": checks, "failed": failed, "count": len(checks), "source_sha256": h0,
               "summary": summary, "shuffled": shuf_summary, "no_library": nolib,
               "claim": "procedures acquired through the controlled-language interface; not open language; not a mind"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/g45_receipt.json").write_text(json.dumps(receipt, indent=2))
    Path("artifacts/g45_raw.json").write_text(json.dumps({"runs": runs, "shuffled": shuf}, indent=1))
    print(json.dumps({k: receipt[k] for k in ("checks", "failed", "count", "summary", "shuffled", "no_library")}, indent=1))
    if failed:
        raise SystemExit(1)
    return receipt


if __name__ == "__main__":
    run()
