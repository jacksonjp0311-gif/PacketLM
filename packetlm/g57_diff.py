"""G57: adversarial differential test of `--indexed` against the always-re-ask, non-indexed engine.

Both engines run the same random session under the long-lived protocol (serve.Server, in-process).
After every call the replies must be equal and the in-memory states byte-identical (json text in
insertion order); at the end the snapshot files must be byte-identical. Read-only calls are checked
to leave the state unchanged (PACKETLM_CHECK_READONLY semantics via `check_readonly=True`).

Sessions are adversarial for the gate: capabilities taught out of alphabetical order and composed
from each other, facts added and removed at relations a cached answer uses, corrections that retire
examples and change statuses, `express`/`define` changes, new and unknown entities, and many
repeated re-ask calls between the changes.
Run: python3 -m packetlm.g57_diff [N_SESSIONS] [SEED]
"""
from __future__ import annotations
import json
import random
import sys
import tempfile
from pathlib import Path

from . import serve

BASE = ["--answers", "--bounded", "--lean", "--deepen=3"]


def session(rng: random.Random):
    ents = [f"e{i}" for i in range(rng.randint(6, 12))]
    rels = [f"r{i}" for i in range(rng.randint(2, 4))]
    names = rng.sample(["zz", "yy", "mm", "aa", "kk", "bb", "qq"], k=rng.randint(2, 4))
    facts = set()
    for _ in range(rng.randint(8, 20)):
        facts.add((rng.choice(ents), rng.choice(rels), rng.choice(ents)))
    calls = [[f"fact {s} {r} {o}" for s, r, o in sorted(facts)]]

    def truth(prog, s):
        front = {s}
        for r in prog:
            front = {o for x in front for (a, b, o) in facts if a == x and b == r}
        return front

    progs = {}
    for n in names:
        prog = [rng.choice(rels) for _ in range(rng.randint(1, 2))]
        progs[n] = prog
        ex = []
        for s in rng.sample(ents, k=min(len(ents), 4)):
            t = truth(prog, s)
            if len(t) == 1:
                ex.append(f"example {n}: {s} -> {next(iter(t))}")
        if ex:
            calls.append(ex[:3])

    def questions():
        k = rng.randint(3, 10)
        return [f"what is {rng.choice(ents + ['unk' + str(rng.randint(0, 3))])} "
                f"{rng.choice(names + rels + ['ww'])}" for _ in range(k)]
    for _ in range(rng.randint(10, 22)):
        x = rng.random()
        if x < 0.45:
            calls.append(questions())  # read-only re-ask calls
        elif x < 0.55:
            s, r, o = rng.choice(ents), rng.choice(rels), rng.choice(ents)
            facts.add((s, r, o))
            calls.append([f"fact {s} {r} {o}"] + (questions() if rng.random() < 0.5 else []))
        elif x < 0.63 and facts:
            s, r, o = rng.choice(sorted(facts))
            facts.discard((s, r, o))
            calls.append([f"retract {s} {r} {o}"])
        elif x < 0.70 and facts:
            s, r, o = rng.choice(sorted(facts))
            o2 = rng.choice(ents)
            facts.difference_update({f for f in facts if f[0] == s and f[1] == r})
            facts.add((s, r, o2))
            calls.append([f"correct {s} {r} {o2}"])
        elif x < 0.75:
            calls.append([f"express {rng.choice(names)} as {rng.choice(['w1', 'w2', rng.choice(rels)])}"])
        elif x < 0.80:
            calls.append([f"define ww as {rng.choice(names + rels)}"])
        elif x < 0.86:
            n = rng.choice(names)
            calls.append([f"investigate {n}"])
        elif x < 0.92:
            n = rng.choice(names)
            s = rng.choice(ents)
            t = truth(progs[n], s)
            if len(t) == 1:
                calls.append([f"example {n}: {s} -> {next(iter(t))}"])
        else:
            a, b = rng.sample(names, 2)  # composition: a capability over another
            s = rng.choice(ents)
            t = truth(progs[a] + progs[b], s)
            if len(t) == 1:
                calls.append([f"example c{a}{b}: {s} -> {next(iter(t))}"])
    return calls


CHAIN = [f"fact {a} p {b}" for a, b in zip("abcdefgh", "bcdefghi")]
ZZ = ["example zz: a -> b", "example zz: b -> c", "example zz: c -> d"]
# Hand-built sessions, one per way a cached answer can go stale (docs/G57.md §3).
SCENARIOS = [
    # a capability's own record changes (suspension) with no change to the relations it reads
    [CHAIN, ZZ, ["what is h zz"], ["what is h zz"], ["example zz: g -> a"], ["what is h zz", "What is H zz?"]],
    # a fact the cached answer used is removed (no fact is added)
    [CHAIN, ZZ, ["what is h zz", "what is g zz"], ["retract h p i"], ["what is h zz", "what is g zz"]],
    # a change and a re-ask inside one mutating call
    [CHAIN, ZZ, ["what is h zz"], ["what is h zz", "example zz: g -> a", "what is h zz"]],
    # a dependent capability pinned to a dependency that is superseded, then suspended
    [["fact s1 k t1", "fact t1 m u1", "fact u1 m w1"], ["example nm: s1 -> u1"], ["example far: s1 -> w1"],
     ["what is s1 far", "what is t1 far"], ["fact s1 j t1", "fact s2 j t2", "fact t2 m u2"], ["example nm: s2 -> u2"],
     ["what is s1 far", "what is s2 nm"], ["example nm: s1 -> zz9"], ["what is s1 far", "what is s1 nm"]],
    # the lexicon word changes target
    [CHAIN, ZZ, ["define ww as zz"], ["what is c ww"], ["define ww as p"], ["what is c ww", "what is c ww"]],
    # qualified -> provisional through a dependency, with no change to any relation the answer reads:
    # across calls, then inside one mutating call
    [["fact s1 k t1", "fact t1 m u1", "fact u1 m w1", "fact s2 j t2", "fact t2 n u2"], ["example nm: s1 -> u1"],
     ["example far: s1 -> w1"], ["what is s1 far"], ["what is s1 far"], ["example nm: s2 -> u2"], ["what is s1 far"]],
    [["fact s1 k t1", "fact t1 m u1", "fact u1 m w1", "fact s2 j t2", "fact t2 n u2"], ["example nm: s1 -> u1"],
     ["example far: s1 -> w1"], ["what is s1 far"], ["what is s1 far", "example nm: s2 -> u2", "what is s1 far"],
     ["what is s1 far"]],
    # audit (a) of d6cbcf3: a new fact creates an alternative path (a second edge from a cached subject)
    [CHAIN, ZZ, ["what is h zz", "what is g zz"], ["fact h p a"], ["what is h zz", "what is g zz"],
     ["fact x1 p x2", "fact x2 p x3"], ["what is h zz", "what is x1 zz"]],
    # a new fact contradicts a recorded example (correction of a premise) and a retraction of the other
    [CHAIN, ZZ, ["what is e zz", "what is f zz"], ["correct a p z"], ["what is e zz", "what is f zz"],
     ["retract b p c"], ["what is e zz", "what is b zz"]],
    # capability replacement: zz re-taught on another relation (superseded, then a new version)
    [CHAIN + ["fact a q h", "fact b q g", "fact c q f", "fact d q e"], ZZ, ["what is d zz", "what is a zz"],
     ["example zz: a -> h", "example zz: b -> g", "example zz: c -> f"], ["what is d zz", "what is a zz"],
     ["investigate zz"], ["what is d zz", "what is a zz"]],
    # an entity unknown at the first ask becomes known; a fact appears at a cached recall
    [CHAIN, ZZ, ["what is q zz", "what is q p"], ["fact q p a"], ["what is q zz", "what is q p"]],
    # G57b: a negative statement at a known entity outside the candidate's domain (sparse tables)
    [CHAIN + ["fact x9 q y9", "fact a q b", "fact b q c"], ZZ, ["example zz: x9 -> !none"],
     ["what is a zz", "what is x9 zz", "what is d zz"], ["investigate zz"], ["what is e zz"]],
    # G57b: in one call, an entity loses all its facts and is told again (known to the reference's
    # entity set from its first use: growth must still re-check the region)
    # (o8 is only ever an object, so the retraction itself does not grow it)
    [CHAIN, ZZ, ["what is a zz"], ["fact w8 q o8"], ["fact w8 q v8", "retract w8 q o8", "fact o8 p a", "what is a zz"],
     ["what is o8 zz", "what is a zz"]],
]


def run(n=60, seed=0, mutate=None, ref_flags=None, new_flags=None, full_every=None) -> dict:
    """Returns counts; `ok` is True when every call agreed."""
    rng = random.Random(seed)
    stats = {"sessions": 0, "calls": 0, "readonly_calls": 0, "gated_answers": 0, "replies": 0,
             "mismatch": None}
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        for k in range(len(SCENARIOS) + n):
            calls = SCENARIOS[k] if k < len(SCENARIOS) else session(rng)
            ref = serve.Server(snapshot_every=5)
            ind = serve.Server(snapshot_every=5, check_readonly=True, full_every=full_every)
            pr, pi = tmp / f"r{k}.json", tmp / f"i{k}.json"
            for c in calls:
                a = ref.call(pr, ref_flags or BASE, c)
                b = ind.call(pi, new_flags or BASE + ["--indexed"], c)
                stats["calls"] += 1
                stats["replies"] += len(c)
                stats["readonly_calls"] += bool(b.get("readonly"))
                stats["gated_answers"] += b["stats"].get("gated", 0)
                # G57b mode (both engines indexed): the engines' work counters must match too
                same_stats = not (ref_flags and "--indexed" in ref_flags) or a["stats"] == b["stats"]
                if a["replies"] != b["replies"] or json.dumps(ref.cur.state) != json.dumps(ind.cur.state) or not same_stats:
                    stats["mismatch"] = {"session": k, "lines": c, "ref": a["replies"], "indexed": b["replies"],
                                         "stats_equal": same_stats}
                    return {**stats, "ok": False}
            if ind.cur is not None and ind.cur.memo is not None:
                for k, v in ind.cur.memo.counts.items():
                    stats.setdefault("paths", {})[k] = stats.get("paths", {}).get(k, 0) + v
            ref.close()
            ind.close()
            if pr.read_bytes() != pi.read_bytes():
                stats["mismatch"] = {"session": k, "final_snapshot": "differs"}
                return {**stats, "ok": False}
            stats["sessions"] += 1
    return {**stats, "ok": True}


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    if "--g57b" in sys.argv:  # G57b: --incremental against the G57 engine
        print(json.dumps(run(n, seed, ref_flags=BASE + ["--indexed"], new_flags=BASE + ["--indexed", "--incremental"],
                             full_every=int(sys.argv[sys.argv.index("--full-every") + 1]) if "--full-every" in sys.argv
                             else None), indent=1))
    else:
        print(json.dumps(run(n, seed), indent=1))
