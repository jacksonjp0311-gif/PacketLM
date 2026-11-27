"""OPS-1: acquiring bounded, predicate-terminated iteration on unfamiliar graphs.
Protocol and thresholds: docs/OPS1.md (committed before this ran).
Run: python3 benchmarks/ops1.py [--seeds 41,42,43]
"""

from __future__ import annotations
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from packetlm import reference  # noqa: E402
from packetlm.g45_test import Names, Teacher, source_hash  # noqa: E402

OUT = ROOT / "artifacts/ops1"
ARMS = {"O": ["--operators", "--deepen=3"], "X": ["--deepen=3"], "S": ["--operators", "--deepen=3"]}


def graph(rng, nm):
    U, K, D = nm(), nm(), nm()
    top, target, low = nm(), nm(), nm()
    triples, nodes, info = [], [], {}
    targets = []
    for _ in range(3):
        root = nm()
        triples.append((root, K, top))
        nodes.append(root)
        for _ in range(3):
            tg = nm()
            triples += [(tg, U, root), (tg, K, target)]
            targets.append(tg)
            nodes.append(tg)
            for depth in (1, 2, 3, 4):
                parent = tg
                for d in range(1, depth + 1):
                    node = nm()
                    triples.append((node, U, parent))
                    if d < depth and rng.random() < 0.5:
                        triples.append((node, K, low))
                    info[node] = {"depth": d, "leaf": d == depth, "target": tg}
                    nodes.append(node)
                    parent = node
    for n, x in info.items():
        if x["leaf"]:
            triples.append((n, D, rng.choice(nodes)))
    return {"U": U, "K": K, "D": D, "types": [top, target, low], "triples": triples, "info": info,
            "targets": targets, "hidden": [f"until:{U}:{K}:{target}"]}


def truth(triples, hidden, s):
    out = reference.run(reference.index(triples), hidden, s)
    return next(iter(out)) if len(out) == 1 else None


def classify(reply, s, name, t):
    got = reply.split()[2] if reply.startswith(f"{s} {name} ") else None
    prov = "[provisional]" in reply
    return {"s": s, "truth": t, "got": got, "provisional": prov, "reply": reply,
            "wrong_qualified": got is not None and got != t and not prov}


def run_arm(seed, arm):
    rng = random.Random(seed)
    nm = Names(rng)
    arng = random.Random(seed * 31 + ord(arm))
    state = OUT / f"{arm}_{seed}.json"
    for p in OUT.glob(f"{arm}_{seed}.json*"):
        p.unlink()
    log = []
    T = Teacher(state, ARMS[arm], log)
    out = []
    for gi in range(3):
        G = graph(rng, nm)
        name = nm()
        info, tri = G["info"], list(G["triples"])
        pool1 = [n for n, x in info.items() if x["leaf"] and x["depth"] == 1]
        pool2 = [n for n, x in info.items() if x["leaf"] and x["depth"] == 2]
        ex = [rng.choice(pool1), rng.choice(pool2)]
        ex.append(rng.choice([n for n in pool1 + pool2 if n not in ex]))
        sealed = [n for n, x in info.items() if (x["leaf"] and x["depth"] >= 3) or not x["leaf"]]
        # transfer subtree: depths 5 and 6 under one target, taught after acquisition
        tg = rng.choice(G["targets"])
        extra, tnodes = [], []
        for depth in (5, 6):
            parent = tg
            for _ in range(depth):
                node = nm()
                extra.append((node, G["U"], parent))
                tnodes.append(node)
                parent = node
        sealed_all = set(sealed) | set(tnodes)
        vals = [truth(tri, G["hidden"], s) for s in ex]
        if arm == "S":
            vals = [arng.choice([t for t in G["targets"] if t != v]) for v in vals]
        lines = [f"fact {s} {r} {o}" for s, r, o in tri] + [f"example {name}: {s} -> {v}" for s, v in zip(ex, vals)]
        status = T(*lines)[-1].split()[0]
        asked, pending, n = [], None, 0
        while n < 4 and status != "qualified":
            rr = T(*([pending] if pending else []), f"investigate {name}")
            n += 1
            if pending and pending.startswith("example"):
                status = rr[0].split()[0]
            pending = None
            q = rr[-1]
            if status == "qualified" or not q.startswith("what is "):
                break
            subj = q.split()[2]
            asked.append(subj)
            tv = truth(tri, G["hidden"], subj)
            if subj in sealed_all or tv is None:
                pending = f"unanswered {name}: {subj}"
                continue
            if arm == "S":
                tv = arng.choice([t for t in G["targets"] if t != tv])
            pending = f"example {name}: {subj} -> {tv}"
        if pending:
            rr = T(pending)
            if pending.startswith("example"):
                status = rr[0].split()[0]
        st = json.loads(state.read_text())["state"]
        cap = st["capabilities"].get(name)
        ver = cap["versions"][cap["current"] - 1] if cap and cap.get("current") else None
        items = [(s, truth(tri, G["hidden"], s)) for s in sealed]
        rows = [classify(r, s, name, t) for (s, t), r in zip(items, T(*[f"what is {s} {name}" for s, _ in items]))]
        T(*[f"fact {s} {r} {o}" for s, r, o in extra])
        tri2 = tri + extra
        titems = [(s, truth(tri2, G["hidden"], s)) for s in tnodes]
        trows = [classify(r, s, name, t) for (s, t), r in zip(titems, T(*[f"what is {s} {name}" for s, _ in titems]))]
        allrows = rows + trows
        answered = [r for r in allrows if r["got"] is not None]
        out.append({"graph": gi, "name": name, "hidden": G["hidden"], "status": ver["status"] if ver else status,
                    "seq": ver["seq"] if ver else None, "base": ver["base"] if ver else None,
                    "acquired": bool(ver) and ver["status"] in ("qualified", "provisional") and ver["base"] == G["hidden"],
                    "examples": [[s, v] for s, v in zip(ex, vals)], "asked": asked,
                    "blocking": st["hypotheses"].get(name, {}).get("blocking"),
                    "sealed_n": len(rows), "transfer_n": len(trows),
                    "answered": len(answered), "correct": sum(r["got"] == r["truth"] for r in answered),
                    "wrong_qualified": sum(r["wrong_qualified"] for r in allrows),
                    "provisional_answers": sum(r["provisional"] for r in answered),
                    "depths_eval": sorted({info[s]["depth"] for s in sealed} | {5, 6}), "rows": allrows})
    return {"seed": seed, "arm": arm, "graphs": out, "processes": len(log),
            "cpu_s": round(sum(e["cpu_s"] for e in log), 3), "interactions": sum(len(e["lines"]) for e in log)}


def main(argv):
    seeds = [41, 42, 43]
    if "--seeds" in argv:
        seeds = [int(x) for x in argv[argv.index("--seeds") + 1].split(",")]
    OUT.mkdir(parents=True, exist_ok=True)
    sha0 = source_hash()
    runs = {(s, a): run_arm(s, a) for s in seeds for a in ARMS}
    g = lambda a: [x for s in seeds for x in runs[(s, a)]["graphs"]]
    O, X, S = g("O"), g("X"), g("S")
    ans = sum(x["answered"] for x in O)
    tot = sum(x["sealed_n"] + x["transfer_n"] for x in O)
    m = {"O_acquired": sum(x["acquired"] for x in O), "graphs": len(O),
         "O_status": [x["status"] for x in O],
         "O_wrong_qualified": sum(x["wrong_qualified"] for x in O),
         "O_accuracy_answered": round(sum(x["correct"] for x in O) / max(ans, 1), 4),
         "O_coverage": round(ans / max(tot, 1), 4),
         "O_provisional_answers": sum(x["provisional_answers"] for x in O),
         "X_wrong_qualified": sum(x["wrong_qualified"] for x in X), "X_acquired": sum(x["acquired"] for x in X),
         "X_status": [x["status"] for x in X], "X_answered": sum(x["answered"] for x in X),
         "S_matches": sum(x["acquired"] for x in S), "S_wrong_qualified": sum(x["wrong_qualified"] for x in S),
         "S_status": [x["status"] for x in S],
         "cpu_s": {a: round(sum(runs[(s, a)]["cpu_s"] for s in seeds), 3) for a in ARMS},
         "processes": {a: sum(runs[(s, a)]["processes"] for s in seeds) for a in ARMS}}
    th = {"1_acquired_ge_8": m["O_acquired"] >= 8, "2_no_wrong_qualified": m["O_wrong_qualified"] == 0,
          "3_accuracy_coverage": m["O_accuracy_answered"] >= 0.95 and m["O_coverage"] >= 0.9,
          "4_control_off": m["X_wrong_qualified"] == 0 and m["X_acquired"] == 0,
          "5_shuffled_le_1": m["S_matches"] <= 1, "source_unchanged": sha0 == source_hash()}
    rep = {"metrics": m, "thresholds": th, "all_pass": all(th.values()), "source_sha256": sha0}
    (OUT / "ops1_receipt.json").write_text(json.dumps(rep, indent=1))
    (OUT / "ops1_raw.json").write_text(json.dumps({f"{k[0]}:{k[1]}": v for k, v in runs.items()}))
    print(json.dumps(rep, indent=1))
    return 0 if rep["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
