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

from . import serve
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
    # composition over a capability that is later superseded and re-taught
    [CHAIN + ["fact a q h", "fact b q g", "fact c q f", "fact h p i"], ZZ, ["example cz: a -> i"],
     ["example zz: a -> h", "example zz: b -> g", "example zz: c -> f"], ["example cz: b -> h"], ["what is a cz"],
     ["requalify cz"], ["what is a cz"]],
    # `complete` at a subject whose closure covers an unrelated capability's observations; a removal
    # outside every closure; reach over told facts only (derived facts are not edges)
    [CHAIN + ["fact x1 q x2", "fact x2 q x3"], ZZ, ["example qq: x1 -> x2", "example qq: x2 -> x3"],
     ["derive zz a"], ["complete a", "complete x1"], ["retract x2 q x3"], ["example qq: x1 -> x2"], ["what is x1 qq"]],
]


def run(n=60, seed=0, ref_flags=None, new_flags=None) -> dict:
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


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    print(json.dumps(run(n, seed), indent=1))
