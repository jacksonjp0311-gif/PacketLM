"""G58: adversarial differential test of `--routed` against the G57b engine (docs/G58.md §3).

Same protocol as packetlm/g57_diff.py (serve.Server in-process, replies and in-memory state text
compared after every call, final snapshots byte-compared), with the G57b engine
(--indexed --incremental) as the reference and --routed added. Work counters (`stats`) are not
compared: skipping re-evaluations is the point. Sessions add what the routing gates on: `complete`
statements (closed judgments; retracted by later facts), compositions of capabilities over each
other (dependency statuses), observations at unknown entities, suspensions and supersessions.
Run: python3 -m packetlm.g58_diff [N_SESSIONS] [SEED]
"""
from __future__ import annotations
import json
import random
import sys
import tempfile
from pathlib import Path

from . import engine, serve
from . import g57_diff

BASE = g57_diff.BASE + ["--indexed", "--incremental"]
NEW = BASE + ["--routed"]


def session(rng: random.Random):
    calls = g57_diff.session(rng)
    ents = sorted({w for c in calls for x in c for w in x.split()[1:4:2] if x.startswith("fact ")}) or ["e0"]
    names = sorted({x.split(":")[0].split()[-1] for c in calls for x in c if x.startswith("example ")}) or ["zz"]
    out = []
    for c in calls:
        out.append(c)
        x = rng.random()
        if x < 0.15:
            out.append([f"complete {rng.choice(ents)}"])
        elif x < 0.22:
            out.append([f"example {rng.choice(names)}: {rng.choice(ents + ['unk9'])} -> {rng.choice(ents)}"])
        elif x < 0.27:
            out.append([f"requalify {rng.choice(names)}"])
        elif x < 0.31:
            a, b = rng.choice(names), rng.choice(names)
            out.append([f"example k{a}{b}: {rng.choice(ents)} -> {rng.choice(ents)}"])
        elif x < 0.35:
            out.append([f"correct example {rng.choice(names)}: {rng.choice(ents)} -> {rng.choice(ents)}"])
    return out


CHAIN = g57_diff.CHAIN
ZZ = g57_diff.ZZ
SCENARIOS = [
    # a reviewed capability's dependency is suspended (no relation it reads changes)
    [["fact s1 k t1", "fact t1 m u1", "fact u1 m w1"], ["example nm: s1 -> u1"], ["example far: s1 -> w1"],
     ["example zz9: s1 -> s1"], ["example nm: s1 -> zz9"], ["example far: t1 -> w1"], ["what is s1 far"]],
    # a fact at a relation a reviewed capability reads contradicts its own example
    [CHAIN, ZZ, ["example yy: a -> b"], ["retract a p b", "fact a p c"], ["example yy: b -> c"], ["what is a zz"]],
    # closed judgment: `complete` at an observed subject, then a fact inside the closure retracts it
    [CHAIN, ZZ, ["complete a"], ["example zz: a -> !several"], ["fact a p x"], ["what is a zz"], ["complete a"],
     ["example zz: d -> e"]],
    # an observed subject unknown at the first review becomes known
    [CHAIN, ZZ, ["example zz: q9 -> r9"], ["fact q9 p r9"], ["example zz: d -> e"], ["what is q9 zz"]],
    # ... through a fact at a relation the capability does not read (no stamp it reads changes)
    [CHAIN, ZZ, ["example zz: q8 -> r8"], ["fact q8 w r7"], ["what is q8 zz"], ["fact q8 p r8"], ["what is q8 zz"]],
    # composition over a capability that is later superseded and re-taught
    [CHAIN + ["fact a q h", "fact b q g", "fact c q f", "fact h p i"], ZZ, ["example cz: a -> i"],
     ["example zz: a -> h", "example zz: b -> g", "example zz: c -> f"], ["example cz: b -> h"], ["what is a cz"],
     ["requalify cz"], ["what is a cz"]],
    # `complete` at a subject whose closure covers an unrelated capability's observations; a removal
    # outside every closure; reach over told facts only (derived facts are not edges)
    [CHAIN + ["fact x1 q x2", "fact x2 q x3"], ZZ, ["example qq: x1 -> x2", "example qq: x2 -> x3"],
     ["derive zz a"], ["complete a", "complete x1"], ["retract x2 q x3"], ["example qq: x1 -> x2"], ["what is x1 qq"]],
    # a corrected example (observations replaced, not added), then a dependent composition
    [CHAIN, ZZ, ["example yy: a -> c", "example yy: b -> d"], ["correct example yy: a -> b"],
     ["example kyy: a -> d"], ["correct example zz: a -> d"], ["what is a yy"]],
    # a suspended capability re-acquired as a new version (a different program) after corrections
    [["fact a p b", "fact b p c", "fact a q x", "fact b q y", "fact c q z"], ["example yy: a -> b"],
     ["example yy: b -> c"], ["example yy: a -> x"], ["correct example yy: b -> y"], ["correct example yy: a -> x"],
     ["what is b yy"], ["example yy: c -> z"], ["fact c q c"], ["example yy: c -> c"]],
    # a corrected example at a new subject of a qualified capability (no status change)
    [CHAIN, ZZ, ["correct example zz: d -> e"], ["fact d p x"], ["what is d zz"]],
    # a composition over a capability (cap:zz@1+rel:q); a second value at an observed subject, then
    # `complete` there (only the closed judgment changes); a corrected fact (not told: not an edge)
    [["fact a p b", "fact b p c", "fact c p d", "fact d p e", "fact e p f", "fact f p g", "fact d q x1", "fact e q x2", "fact f q x3"], ["example zz: a -> d", "example zz: b -> e", "example zz: c -> f"], ["example kz: a -> x1", "example kz: b -> x2"], ["what is c kz"], ["derive kz a"], ["fact a p y"], ["complete a"]] + [["example zz: a -> d"], ["correct d q x9"], ["complete d"], ["what is a kz"]],
    # only the closed judgment changes: a second value two steps on, then `complete` at the subject
    [["fact a p b", "fact b p c", "fact c p d", "fact d p e", "fact e p f", "fact f p g"], ["example zz: a -> d", "example zz: b -> e", "example zz: c -> f"], ["fact c p d2"], ["what is a zz"], ["complete a"], ["what is a zz"]],
]


def run(n=60, seed=0, ref_flags=None, new_flags=None, audit=True) -> dict:
    """With `audit` (default), every routed shortcut is also recomputed the unrouted way at each use
    (engine.G58_AUDIT); any difference fails the run even when no reply or state byte differs."""
    old = dict(engine.G58_AUDIT)
    engine.G58_AUDIT.update(on=audit, log=[])
    try:
        r = _run(n, seed, ref_flags, new_flags)
        log = engine.G58_AUDIT["log"]
        r["audit_violations"] = len(log)
        r["audit_first"] = log[:5]
        r["ok"] = r["ok"] and not log
        return r
    finally:
        engine.G58_AUDIT.clear()
        engine.G58_AUDIT.update(old)


def _run(n, seed, ref_flags, new_flags) -> dict:
    rng = random.Random(seed)
    stats = {"sessions": 0, "calls": 0, "replies": 0, "review_skipped": 0, "mismatch": None}
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        for k in range(len(SCENARIOS) + n):
            calls = SCENARIOS[k] if k < len(SCENARIOS) else session(rng)
            ref, new = serve.Server(snapshot_every=5), serve.Server(snapshot_every=5, check_readonly=True)
            pr, pn = tmp / f"r{k}.json", tmp / f"n{k}.json"
            for c in calls:
                a = ref.call(pr, ref_flags or BASE, c)
                b = new.call(pn, new_flags or NEW, c)
                stats["calls"] += 1
                stats["replies"] += len(c)
                if a["replies"] != b["replies"] or json.dumps(ref.cur.state) != json.dumps(new.cur.state):
                    stats["mismatch"] = {"session": k, "lines": c, "ref": a["replies"], "new": b["replies"]}
                    return {**stats, "ok": False}
            if new.cur is not None and new.cur.memo is not None:
                stats["review_skipped"] += new.cur.memo.counts.get("g58_review_skipped", 0)
                for key, v in new.cur.memo.counts.items():
                    stats.setdefault("paths", {})[key] = stats.get("paths", {}).get(key, 0) + v
            ref.close()
            new.close()
            if pr.read_bytes() != pn.read_bytes():
                stats["mismatch"] = {"session": k, "final_snapshot": "differs"}
                return {**stats, "ok": False}
            stats["sessions"] += 1
    return {**stats, "ok": True}


STATUSES = ("qualified", "provisional", "superseded", "suspended", "revoked")


def contract_fuzz(n=120, seed=0, reps=8) -> dict:
    """The routing contract, apart from what the curricula reach (docs/G58.md §2d): with the audit
    on, after every call each routed shortcut is exercised on every capability version (any status)
    -- `_expand_fast`, `_routing`, `_closure_cached`, `_reach` at every entity -- and arbitrary status
    transitions (`_set_status`, any status to any status), corrected examples and observations are
    applied directly, each followed by `review`; the audit checks that every capability `review`
    did not visit has the fingerprint of its last evaluation. Any audit difference fails."""
    rng = random.Random(seed)
    old = dict(engine.G58_AUDIT)
    engine.G58_AUDIT.update(on=True, log=[])
    stats = {"sessions": 0, "calls": 0, "reviews": 0, "transitions": 0, "probes": 0, "refused": 0}
    try:
        with tempfile.TemporaryDirectory() as d:
            plan = [sc for sc in SCENARIOS for _ in range(reps)] + [None] * n
            for k, calls in enumerate(plan):
                calls = calls or session(rng)
                srv = serve.Server(snapshot_every=1000)
                p = Path(d) / f"f{k}.json"
                for c in calls:
                    try:
                        srv.call(p, NEW, c)
                    except Exception as exc:  # noqa: BLE001 -- a refused state after a direct transition
                        stats["refused"] += 1
                        stats.setdefault("refusals", []).append(f"call {type(exc).__name__}: {exc}"[:120])
                        break
                    stats["calls"] += 1
                    if srv.cur is None or srv.cur.memo is None:
                        break
                    e = srv._engine(srv.cur)  # the open state and its memo, between calls
                    caps = e.state["capabilities"]
                    vers = [(nm, ver) for nm, cap in caps.items() for ver in cap["versions"]]
                    for nm, ver in vers:
                        e._expand_fast(list(ver["seq"]))
                        e._closure_cached(nm, ver)
                    if vers:
                        e._routing([f"cap:{nm}@{ver['v']}" for nm, ver in vers] + ["rel:p"])
                    for nm in sorted(caps):
                        e.primitives(nm)
                    e._sx()
                    for x in sorted(e._idx()["pos"]):
                        e._reach(x)
                    stats["probes"] += 1
                    try:  # direct operations on states no curriculum reaches; the engine may refuse
                        r = rng.random()
                        if vers and r < 0.5:
                            held = [(nm, ver) for nm, ver in vers  # versions some closure holds (dependencies)
                                    if any((nm, ver["v"]) in e._closure_cached(m, w) for m, w in vers)]
                            nm, ver = rng.choice(held if held and rng.random() < 0.6 else vers)
                            e._set_status(nm, ver["v"], rng.choice(STATUSES), "contract fuzz")
                            stats["transitions"] += 1
                        elif caps and r < 0.8:
                            nm = rng.choice(sorted(caps))
                            ents = sorted(e._idx()["pos"]) or ["e0"]
                            if r < 0.6:
                                e.correct_example(nm, rng.choice(ents), rng.choice(ents))
                            elif r < 0.7:
                                e.observe(nm, rng.choice(ents), rng.choice(ents))
                            else:
                                e.acquire(nm)  # a re-scan without an observation change (requalify)
                        elif r < 0.9 and e.state["facts"]:
                            f = rng.choice(e.state["facts"])
                            if not f["r"].startswith("cap:"):
                                e.correct(f["s"], f["r"], f"c{rng.randrange(5)}")  # a corrected fact: not told
                        e.review()
                    except Exception as exc:  # noqa: BLE001
                        stats["refused"] += 1
                        stats.setdefault("refusals", []).append(f"{type(exc).__name__}: {exc}"[:120])
                        break
                    stats["reviews"] += 1
                srv.cur = None
                stats["sessions"] += 1
        log = engine.G58_AUDIT["log"]
        return {**stats, "audit_violations": len(log), "audit_first": log[:5], "ok": not log}
    finally:
        engine.G58_AUDIT.clear()
        engine.G58_AUDIT.update(old)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    print(json.dumps(run(n, seed), indent=1))
