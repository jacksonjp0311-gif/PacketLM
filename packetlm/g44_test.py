"""G44 test. One engine, checked as separate claims.

Sections memory..fresh_process are the original 39 checks (names kept;
semantics updated where the audit changed the policy, see docs/RESEARCH_LEDGER.md).
Section audit covers docs/G44_AUDIT.md. Not a mind.
"""

from __future__ import annotations
import copy
import json
import random
import subprocess
import sys
import tempfile
from itertools import product
from pathlib import Path
from .engine import Engine, StateError, judge, _checksum, SCHEMA, SCHEMA_V2
from .field import add as field_add, ask as field_ask, bind
from . import reference

ROOT = Path(__file__).resolve().parent.parent


def family(eng):
    for i in range(6):
        eng.tell(f"p{i}", "parent", f"p{i+1}", source="test")
    eng.tell("p0", "friend", "p2", source="test")
    eng.tell("p1", "friend", "p5", source="test")
    eng.tell("rex", "owns", "map", source="test")


def grand_engine(path):
    eng = Engine(path)
    family(eng)
    eng.observe("grand", "p0", "p2")
    eng.observe("grand", "p1", "p3")
    eng.acquire("grand")
    return eng


def memory_checks(tmp) -> dict:
    eng = Engine.open(tmp / "mem.json")
    eng.turn("construct owns: ada owns box = ada box; ned owns key = ned key")
    rec = eng.turn("rex owns map")
    told = copy.deepcopy(eng._find("rex", "owns", "map"))
    family(eng)
    eng.observe("grand", "p0", "p2")
    eng.observe("grand", "p1", "p3")
    eng.acquire("grand")
    d = eng.derive("grand", "p2")
    derived = copy.deepcopy(eng._find("p2", "cap:grand", "p4"))
    corr = eng.correct("p3", "parent", "p9")
    after = eng.answer("p2", "grand")
    eng.tell("sam", "owns", "key")
    eng.tell("sam", "owns", "cup")
    amb = eng.ask("sam", "owns")
    eng.correct("sam", "owns", "key")
    amb_fixed = eng.ask("sam", "owns")
    gone = eng.retract("rex", "owns", "map")
    return {
        "provenance_told": rec == "recorded rex owns map" and bool(told) and told[0]["supports"][0]["source"] == "sentence"
            and told[0]["supports"][0]["turn"] > 0,
        "derived_provenance": d.get("status") == "derived" and bool(derived)
            and derived[0]["supports"][0]["premises"] == ["p2 parent p3", "p3 parent p4"]
            and derived[0]["supports"][0]["program"] == "cap:grand@1",
        "correction_drops_derived": "p2 cap:grand p4" in corr["removed"] and after.get("value") == "p9"
            and eng.version("grand")["status"] == "qualified",
        "correction_logged": any(e["id"] == "p2 cap:grand p4" and e["reason"].startswith("correct") for e in eng.state["log"]),
        "ambiguity_abstains": amb == {"status": "ambiguous", "value": None, "candidates": ["cup", "key"]},
        "ambiguity_resolved_by_correction": amb_fixed == {"status": "known", "value": "key"},
        "retraction": gone["removed"] == ["rex owns map"] and eng.ask("rex", "owns")["status"] == "unknown"
            and any(e["reason"].startswith("retract") for e in eng.state["log"]),
    }


def construction_checks(tmp) -> dict:
    eng = Engine.open(tmp / "con.json")
    a = eng.turn("construct owns: ada owns box = ada box; ned owns key = ned key")
    b = eng.turn("construct vek: box vek ada = ada box; key vek ned = ned key")
    clash = eng.turn("construct holds: ada owns box = ada box; ned owns key = ned key")
    rec = eng.turn("map vek rex")
    q = eng.turn("question owns: what does ada own = ada; what does ned own = ned")
    asked = eng.turn("what does rex own")
    return {
        "induced_orders": a == "construction owns sro" and b == "construction vek ors",
        "osv_read": rec == "recorded rex vek map" and eng.ask("rex", "vek")["value"] == "map",
        "speak_roundtrip": eng.speak(("rex", "vek", "map")) == "map vek rex" and eng.read("map vek rex") == ("rex", "vek", "map"),
        "unknown_word_abstains": eng.turn("rex holds map") == "unparsed",
        "word_clash_rejected": clash == "construction rejected",
        "question_template_learned": q == "question owns what does <s> own" and asked == "unknown"
            and eng.turn("rex owns map") == "recorded rex owns map" and eng.turn("what does rex own") == "rex owns map",
        "question_unknown_form_unparsed": eng.turn("what does rex hold") == "unparsed",
    }


def acquisition_checks(tmp) -> dict:
    eng = Engine(tmp / "acq.json")
    family(eng)
    eng.observe("grand", "p0", "p2")
    first = eng.acquire("grand")
    eng.observe("grand", "p1", "p3")
    second = eng.acquire("grand")
    eng.observe("great", "p0", "p3")
    eng.observe("great", "p1", "p4")
    ctl = Engine(tmp / "ctl.json", copy.deepcopy(eng.state), use_library=False)
    control = ctl.acquire("great")
    with_lib = eng.acquire("great")
    deep = Engine(tmp / "deep.json", copy.deepcopy(ctl.state), use_library=False)
    deep_res = deep.acquire("great", max_len=3)
    ref = reference.index([(f["s"], f["r"], f["o"]) for f in eng.state["facts"] if not f["r"].startswith("cap:")])
    compared = nonempty = agree = 0
    for name in eng.state["capabilities"]:
        ver = eng.version(name)
        for s in eng.entities():
            mine = eng.execute(ver["seq"], s)
            theirs = reference.run(ref, ver["base"], s)
            compared += 1
            nonempty += bool(mine)
            agree += mine == theirs
    return {
        "one_observation_stays_pending": first["result"] == "ambiguous" and len(first["supported"]) == 2,
        "accumulated_acquires": second.get("seq") == ["rel:parent", "rel:parent"] and second["result"] == "qualified",
        "library_control_finds_nothing": control["result"] == "none",
        "library_reuse": with_lib.get("result") == "qualified" and eng.version("great")["base"] == ["parent"] * 3
            and "cap:grand@1" in eng.version("great")["seq"],
        "library_matches_deep_search": deep_res.get("seq") == ["rel:parent"] * 3,
        "binary_equals_walk": compared > 0 and agree == compared and nonempty >= 6,
        "_binary_measure": {"compared": compared, "nonempty": nonempty, "agree": agree,
                            "evaluated_lib_depth2": with_lib["evaluated"], "evaluated_nolib_depth3": deep_res["evaluated"]},
    }


def build_world(n):
    triples = []
    for i in range(n):
        triples += [("x", f"r{i}", f"m{i}"), (f"m{i}", f"r{i}", "z")]
        for bit in range(max(1, (n - 1).bit_length())):
            hop = f"h{i}_{bit}"
            triples += [(f"q{bit}", f"r{i}", hop), (hop, f"r{i}", "yes" if (i >> bit) & 1 else "no")]
    triples += [("x", "rg", "mg"), ("mg", "rg", "z")]  # gap: no q facts, so no prediction
    return triples


def world_engine(path, triples):
    eng = Engine(path)
    for t in triples:
        eng.tell(*t, source="world")
    return eng


def discovery_checks(tmp) -> dict:
    results = []
    for seed in (1, 7, 13, 21, 42):
        target = random.Random(seed).randrange(8)
        triples = build_world(8)
        eng = world_engine(tmp / f"disc{seed}.json", triples)
        env, objs = [], sorted({t[2] for t in triples})
        for t in triples:
            field_add(env, *t)
        hidden = f"r{target}"

        def oracle(subject, env=env, objs=objs, hidden=hidden):
            mid = field_ask(env, subject, hidden, objs)
            return field_ask(env, mid, hidden, objs) if mid else None

        eng.observe("out", "x", "z")
        start = eng.acquire("out")
        start_live = eng.state["hypotheses"]["out"]["live"]
        got = eng.discover("out", oracle)
        rec = eng.state["hypotheses"]["out"]
        rg = [h for h in rec["live"] if h["seq"] == ["rel:rg", "rel:rg"]]
        # resolve the gap by teaching the missing knowledge: rg answers "no" everywhere
        for bit in range(3):
            eng.tell(f"q{bit}", "rg", f"g{bit}", source="teacher")
            eng.tell(f"g{bit}", "rg", "no" if (target >> bit) & 1 else "yes", source="teacher")
        settled = eng.acquire("out")
        results.append({
            "seed": seed, "target": target, "live_at_start": sum(h["support"] >= 1 for h in start_live),
            "zero_support_kept": start["zero_support"], "asks": len(got["asked"]), "seq": got.get("seq"),
            "status": got.get("result"), "blocking": got.get("blocking"),
            "ok": got.get("seq") == [f"rel:{hidden}"] * 2,
            "gap_undetermined": bool(rg) and rg[0]["status"] == "undetermined" and ["rel:rg", "rel:rg"] in got.get("blocking", []),
            "start_uniform": all(h["status"] == "supported" and h["support"] == 1 for h in start_live if h["support"]),
            "provisional_then_qualified": got.get("result") == "provisional" and settled.get("result") == "qualified"
                and settled.get("seq") == [f"rel:{hidden}"] * 2,
        })
    eng = world_engine(tmp / "silent.json", build_world(8))
    eng.observe("out", "x", "z")
    eng.acquire("out")
    silent = eng.discover("out", lambda s: None)
    return {
        "missing_is_undetermined": judge(None, "yes") == "undetermined" and judge("no", "yes") == "contradicted",
        "all_seeds_discovered": all(r["ok"] for r in results),
        "gap_survives_as_undetermined": all(r["gap_undetermined"] for r in results),
        "start_gives_no_hint": all(r["start_uniform"] for r in results),
        "targets_vary": len({r["target"] for r in results}) > 1,
        "asks_within_log2": all(r["asks"] <= 3 for r in results),
        "start_has_nine_live": all(r["live_at_start"] == 9 for r in results),
        "gap_keeps_provisional_until_taught": all(r["provisional_then_qualified"] for r in results),
        "silent_oracle_adopts_nothing": silent["result"] == "ambiguous" and "out" not in eng.state["capabilities"]
            and len(eng.state["hypotheses"]["out"].get("unanswered", [])) >= 1 and len(eng.state["observations"]["out"]) == 1,
        "_discovery": results,
    }


def persistence_checks(tmp) -> dict:
    path = tmp / "p.json"
    bak = tmp / "p.json.bak"
    eng = Engine.open(path)
    family(eng)
    eng.save()
    gen1 = path.read_text()
    eng.tell("ann", "parent", "bea")
    eng.save()
    re1 = Engine.open(path)
    roundtrip = re1.state == eng.state and re1.report == {"loaded": "primary"}
    backup_is_prior = bak.read_text() == gen1
    doc = json.loads(path.read_text())
    f0 = dict(doc["state"]["facts"][0])
    doc["state"]["facts"][0]["o"] = "zzz"
    path.write_text(json.dumps(doc))
    r_sum = Engine.open(path)
    doc["state"]["facts"][0]["id"] = "p0 parent zzz"
    doc = as_schema2(doc)  # stored packets (schema 2) of the ORIGINAL fact, then the tamper above
    doc["state"]["facts"][0]["bits"] = bind(f0["s"], f0["r"], f0["o"]).bits.hex()
    doc["checksum"] = _checksum(doc["state"])
    path.write_text(json.dumps(doc))
    r_bind = Engine.open(path)
    good_bak = bak.read_text()
    r_bind.save()  # loaded from backup: the tampered primary must not become the backup
    corrupt_not_backed_up = bak.read_text() == good_bak and Engine.open(path).report == {"loaded": "primary"}
    bak.write_text(good_bak)  # the truncation steps below start from the good backup either way
    path.write_text("{not json")
    r_trunc = Engine.open(path)
    bak.write_text("{also bad")
    try:
        Engine.open(path)
        both = "returned"
    except StateError:
        both = "raised"
    return {
        "roundtrip": roundtrip,
        "backup_is_prior_generation": backup_is_prior,
        "no_temp_left": not any(p.suffix == ".tmp" for p in tmp.iterdir()),
        "checksum_tamper_recovers_loudly": r_sum.report.get("recovered") is True and "checksum" in r_sum.report["primary_error"],
        "binding_tamper_recovers_loudly": r_bind.report.get("recovered") is True and "bind" in r_bind.report["primary_error"],
        "corrupt_primary_not_backed_up": corrupt_not_backed_up,
        "truncated_recovers": r_trunc.report.get("loaded") == "backup" and len(r_trunc.state["facts"]) == 9,
        "both_corrupt_raises": both == "raised",
    }


def cli(state, *lines) -> dict:
    out = subprocess.run([sys.executable, "-m", "packetlm.engine", str(state), *lines],
                         cwd=ROOT, capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        return {"error": out.stderr[-500:]}
    return json.loads(out.stdout)


def fresh_process_checks(tmp) -> dict:
    s = tmp / "fresh.json"
    p1 = cli(s, "construct owns: ada owns box = ada box; ned owns key = ned key",
             "construct parent: ada parent box = ada box; ned parent key = ned key",
             "rex owns map", "ann parent bea", "bea parent cy", "cy parent dee",
             "observe grand ann cy")
    p2 = cli(s, "what is rex owns", "observe grand bea dee", "acquire grand")
    p3 = cli(s, "what is ann grand", "derive grand ann")
    p4 = cli(s, "correct bea parent eve", "correct rex owns key")
    p5 = cli(s, "what is rex owns", "what is ann grand", "what is bea parent")
    s.write_text(s.read_text()[:-40])
    p6 = cli(s, "what is rex owns")
    r4 = p4.get("replies", [""])
    return {
        "p1_new_state": p1.get("load") == {"loaded": "new"} and p1["replies"][2] == "recorded rex owns map",
        "p2_reads_p1": p2.get("load") == {"loaded": "primary"} and p2["replies"][0] == "rex owns map"
            and p2["replies"][2] == "qualified grand rel:parent+rel:parent",
        "p3_uses_capability": p3.get("replies") == ["ann grand cy [no construction for grand]", "derived ann cap:grand cy (1 proofs)"],
        "p4_correction_drops_derived": r4[0] == "corrected bea parent eve; removed 2; retired example grand: ann -> cy; retired example grand: bea -> dee; grand@1 provisional: evidence retired: no active examples",
        "p5_sees_corrections": p5.get("replies") == ["rex owns key", "ann grand eve [no construction for grand] [provisional]", "bea parent eve"],
        "p6_recovery_reported": p6.get("load", {}).get("recovered") is True and p6["replies"] == ["rex owns key"],
        "_replies": {"p1": p1, "p2": p2, "p3": p3, "p4": p4, "p5": p5, "p6": p6},
    }


def as_schema2(doc) -> dict:
    """Test-side writer of the old format: every fact carries its stored packet."""
    doc = copy.deepcopy(doc)
    for f in doc["state"]["facts"]:
        pkt = bind(f["s"], f["r"], f["o"])
        f["bits"], f["count"] = pkt.bits.hex(), pkt.count
    doc["schema"] = SCHEMA_V2
    doc["checksum"] = _checksum(doc["state"])
    return doc


def migration_checks(tmp) -> dict:
    """A schema-2 state is checked in full, migrated explicitly and reported; answers do not change."""
    path = tmp / "m.json"
    eng = grand_engine(path)
    eng.save()
    before = [eng.turn(q) for q in ("what is p0 grand", "what is p1 parent", "what is p9 parent")]
    path.write_text(json.dumps(as_schema2(json.loads(path.read_text()))))
    m = Engine.open(path)
    after = [m.turn(q) for q in ("what is p0 grand", "what is p1 parent", "what is p9 parent")]
    m.save()
    again = Engine.open(path)
    return {
        "v2_migrates_reported": "migrated" in m.report and m.report["loaded"] == "primary",
        "v2_migration_same_answers": before == after and after[0] != "unknown",
        "v3_saved_without_packets": json.loads(path.read_text())["schema"] == SCHEMA
            and all("bits" not in f for f in json.loads(path.read_text())["state"]["facts"])
            and again.report == {"loaded": "primary"},
        "v2_kept_as_backup": json.loads((tmp / "m.json.bak").read_text())["schema"] == SCHEMA_V2,
    }


def corrupt(tmp, label, mutate) -> str:
    path = tmp / f"bad_{label}.json"
    eng = grand_engine(path)
    eng.observe("great", "p0", "p3")
    eng.observe("great", "p1", "p4")
    eng.acquire("great")
    eng.derive("grand", "p0")
    eng.save()
    eng.save()  # backup = a valid generation
    doc = json.loads(path.read_text())
    mutate(doc["state"])
    if label != "checksum":
        doc["checksum"] = _checksum(doc["state"])
    path.write_text(json.dumps(doc))
    got = Engine.open(path)
    return got.report.get("primary_error", "") if got.report.get("recovered") else "accepted"


def audit_checks(tmp) -> dict:
    out = {}
    # 1: zero-support hypotheses kept; count matches the independent reference
    triples = build_world(8)
    eng = world_engine(tmp / "a1.json", triples)
    eng.observe("out", "x", "z")
    eng.acquire("out")
    ref = reference.index(triples)
    rels = sorted(ref)
    ref_live = sum(1 for n in (1, 2) for seq in product(rels, repeat=n)
                   if reference.status(ref, seq, [("x", "z")]) != "contradicted")
    rec = eng.state["hypotheses"]["out"]
    zero = sum(1 for h in rec["live"] if h["support"] == 0)
    agree = all(h["status"] == reference.status(ref, [s[4:] for s in h["seq"]], [("x", "z")]) for h in rec["live"])
    ref_zero = sum(1 for n in (1, 2) for seq in product(rels, repeat=n)
                   if reference.status(ref, seq, [("x", "z")]) == "undetermined"
                   and len(reference.run(ref, seq, "x")) != 1)
    full = Engine(tmp / "a1_full.json", copy.deepcopy(eng.state), activation=False)
    full.acquire("out")
    frec = full.state["hypotheses"]["out"]
    fzero = sum(1 for h in frec["live"] if h["support"] == 0)
    # activation keeps zero-support hypotheses as a counted complement; without it they are stored one by one
    out["zero_support_kept"] = len(rec["live"]) + rec["pruned"] == ref_live and agree and zero + rec["pruned"] == ref_zero \
        and len(frec["live"]) == ref_live and fzero == ref_zero and frec["pruned"] == 0 and ref_zero > 0
    out["activation_same_decision"] = rec.get("candidate") == frec.get("candidate") and \
        sorted(map(tuple, (h["seq"] for h in rec["live"] if h["support"]))) == sorted(map(tuple, (h["seq"] for h in frec["live"] if h["support"])))
    out["_hypotheses"] = {"live_stored": len(rec["live"]), "zero_support_stored": zero, "pruned": rec["pruned"],
                          "reference_live": ref_live, "reference_zero_support": ref_zero,
                          "evaluated_with_activation": rec["evaluated"], "evaluated_without": frec["evaluated"]}

    # deepening: a shorter program that fits the examples is not qualified while a
    # program one level longer also fits them but differs elsewhere (lookahead blocking)
    eng = Engine(tmp / "look.json", deepen=3)
    for t in [("x1", "p", "y1"), ("x2", "p", "y2"), ("x3", "p", "y3"), ("x1", "q", "m1"), ("x2", "q", "m2"),
              ("x3", "q", "m3"), ("m1", "r", "y1"), ("m2", "r", "y2"), ("m3", "r", "z3")]:
        eng.tell(*t)
    eng.observe("hop", "x1", "y1")
    eng.observe("hop", "x2", "y2")
    g1 = eng.acquire("hop")
    q = eng.investigate("hop")
    eng.observe("hop", "x3", "y3")
    g2 = eng.acquire("hop")
    out["open_world_blocks_longer_alternative"] = g1["result"] == "provisional" and g1.get("seq") == ["rel:p"] \
        and ["rel:q", "rel:r"] in g1.get("blocking", []) and q.get("subject") == "x3" and g2["result"] == "qualified" \
        and eng.state["hypotheses"]["hop"]["scan"]["horizon"] == 3
    # P0 (audit 283f526): an alternative with zero support that conflicts elsewhere still blocks;
    # one whose image of the candidate's domain is empty is counted compatible, not eliminated
    zw = Engine(tmp / "zero.json", deepen=2)
    for t in [("x1", "p", "y1"), ("x2", "p", "y2"), ("x3", "p", "y3"), ("x3", "s", "w3"), ("u", "t", "v")]:
        zw.tell(*t)
    zw.observe("zp", "x1", "y1")
    zw.observe("zp", "x2", "y2")
    gz = zw.acquire("zp")
    qz = zw.investigate("zp")
    zw.observe("zp", "x3", "y3")
    gz2 = zw.acquire("zp")
    out["zero_support_conflict_blocks"] = gz["result"] == "provisional" and ["rel:s"] in gz.get("blocking", []) \
        and gz["scan"]["conflicts"] >= 1 and gz["scan"]["pruned_compatible"] >= 1 and qz.get("subject") == "x3" \
        and gz2["result"] == "qualified"
    # the scan agrees with brute force: every primitive sequence up to the horizon,
    # judged by the independent reference (blocker extensions compared as base sets)
    bf = Engine(tmp / "brute.json", deepen=3)
    for t in [("x1", "p", "y1"), ("x2", "p", "y2"), ("x3", "p", "y3"), ("x1", "q", "m1"), ("x2", "q", "m2"),
              ("x3", "q", "m3"), ("m1", "r", "y1"), ("m2", "r", "y2"), ("m3", "r", "z3"), ("x3", "s", "w3"),
              ("m1", "s", "y1"), ("y3", "r", "x1"), ("u", "t", "v")]:
        bf.tell(*t)
    bf.observe("bp", "x1", "y1")
    bf.observe("bp", "x2", "y2")
    bf.BLOCK_KEEP = 10 ** 6
    gb = bf.acquire("bp")
    ref = reference.index([(f["s"], f["r"], f["o"]) for f in bf.state["facts"]])
    rels = sorted(ref)
    ents = sorted({f["s"] for f in bf.state["facts"]} | {f["o"] for f in bf.state["facts"]})
    one = lambda seq, e: (lambda r: next(iter(r)) if len(r) == 1 else None)(reference.run(ref, list(seq), e))
    cand = gb.get("seq") and [x[4:] for x in gb["seq"]]
    want = {e: one(cand, e) for e in ents} if cand else {}
    brute = set()
    for n in (1, 2, 3):
        for seq in product(rels, repeat=n):
            if list(seq) == cand:
                continue
            pv = {e: one(seq, e) for e in ents}
            if any(pv[s] is not None and pv[s] != v for s, v in [("x1", "y1"), ("x2", "y2")]):
                continue
            sup = sum(pv[s] == v for s, v in [("x1", "y1"), ("x2", "y2")])
            conflict = any(pv[e] is not None and want[e] is not None and pv[e] != want[e] for e in ents)
            if conflict or (sup >= 1 and any(pv[e] != want[e] for e in ents)):
                brute.add(seq)
    mine_b = {tuple(x[4:] for x in b) for b in gb.get("blocking", [])}
    out["scan_matches_bruteforce"] = bool(cand) and mine_b == brute and len(brute) > 0
    out["_bruteforce"] = {"result": gb.get("result"), "engine": sorted(mine_b), "brute": sorted(brute)}
    # geom.compose / geom.bits (set-bit iteration) agree with the naive bit-by-bit definition
    import random as _r
    from . import geom as _g
    rr = _r.Random(7)
    ok = True
    for _ in range(300):
        n = rr.randint(1, 300)
        rows = [rr.getrandbits(n) for _ in range(n)]
        a = rr.getrandbits(n) & rr.getrandbits(n)
        naive = 0
        for k in range(n):
            if a >> k & 1:
                naive |= rows[k]
        ok = ok and _g.compose([a], rows) == [naive] and _g.bits(a) == [k for k in range(n) if a >> k & 1]
    out["compose_matches_naive"] = ok
    out["_zero_support"] = {"first": gz.get("result"), "scan": {k: v for k, v in gz.get("scan", {}).items() if k != "assumption"},
                            "question": qz, "after": gz2.get("result")}
    # P1 (audit 283f526): retiring evidence requalifies; the earlier qualification stays in qualified_at
    rq = Engine(tmp / "requal.json", deepen=2)
    for t in [("a1", "f", "b1"), ("a2", "f", "b2"), ("a3", "f", "b3"), ("a1", "g", "c1"), ("a2", "g", "b2"), ("a3", "g", "b3")]:
        rq.tell(*t)
    for x, y in [("a1", "b1"), ("a2", "b2")]:
        rq.observe("rf", x, y)
    r1 = rq.acquire("rf")
    ev = rq.correct("a1", "f", "b9")
    ver = rq.version("rf")
    out["retirement_requalifies"] = r1["result"] == "qualified" and ver["status"] == "provisional" \
        and len(ver.get("qualified_at", [])) == 1 and any("requalified on 1 active examples" in e for e in ev["review"])
    out["_requalify"] = {"first": r1["result"], "review": ev["review"], "now": ver["status"], "qualified_at": ver.get("qualified_at")}
    amb = Engine(tmp / "amb.json", deepen=3)
    for t in [("x1", "p", "y1"), ("x1", "s", "y1"), ("x1", "q", "m1"), ("m1", "r", "y1")]:
        amb.tell(*t)
    amb.observe("two", "x1", "y1")
    ga = amb.acquire("two")
    out["deepen_stops_at_ambiguity"] = ga["result"] == "ambiguous" and amb.state["hypotheses"]["two"]["searched_len"] == 1 \
        and sorted(map(tuple, ga["supported"])) == [("rel:p",), ("rel:s",)]
    out["_lookahead"] = {"first": g1["result"], "blocking": g1.get("blocking"), "question": q, "after": g2["result"]}

    # 3: contradiction suspends; re-acquisition makes v2; teacher revokes
    eng = Engine(tmp / "a3.json")
    for t in [("u1", "a", "w1"), ("u2", "a", "w2"), ("u2", "b", "w2"), ("u3", "a", "w3"), ("u3", "b", "w9")]:
        eng.tell(*t)
    eng.observe("boss", "u1", "w1")
    eng.observe("boss", "u2", "w2")
    r1 = eng.acquire("boss")
    ev = eng.observe("boss", "u3", "w9")
    r2 = eng.acquire("boss")
    eng.tell("u1", "b", "w1")
    r3 = eng.acquire("boss")
    rv = eng.revoke("boss")
    out["contradiction_suspends"] = r1.get("result") == "provisional" and r1.get("seq") == ["rel:a"] \
        and ev == ["boss@1 suspended: contradicted by its observations"] and r2["result"] == "none"
    out["reacquired_as_v2"] = r3.get("result") == "qualified" and r3.get("version") == 2 and r3["seq"] == ["rel:b"] \
        and eng.version("boss", 1)["status"] == "suspended"
    out["teacher_revokes"] = rv == ["boss@2 revoked: revoked by teacher"] and eng.answer("u1", "boss")["status"] == "unknown"

    # 4: versions pin; superseding leaves dependents on the old definition
    eng = Engine(tmp / "a4.json")
    for t in [("s1", "k", "t1"), ("t1", "m", "u1"), ("u1", "m", "w1")]:
        eng.tell(*t)
    eng.observe("nm", "s1", "u1")
    n1 = eng.acquire("nm")
    eng.observe("far", "s1", "w1")
    f1 = eng.acquire("far")
    before = eng.answer("s1", "far")
    for t in [("s1", "j", "t1"), ("s2", "j", "t2"), ("t2", "m", "u2")]:
        eng.tell(*t)
    eng.observe("nm", "s2", "u2")
    n2 = eng.acquire("nm")
    after = eng.answer("s1", "far")
    out["versions_pin_dependents"] = n1.get("seq") == ["rel:k", "rel:m"] and f1.get("seq") == ["cap:nm@1", "rel:m"] \
        and n2.get("version") == 2 and n2.get("seq") == ["rel:j", "rel:m"] and eng.version("nm", 1)["status"] == "superseded" \
        and before == after and after.get("value") == "w1" and eng.version("far")["seq"] == ["cap:nm@1", "rel:m"] \
        and any("still pinned to nm@1" in h["reason"] for h in eng.version("far")["history"])
    out["_versions"] = {"nm_v2_status": n2.get("result"), "nm_v2_blocking": n2.get("blocking")}

    # 5: separate identities; 6: no cycles offered
    eng = grand_engine(tmp / "a5.json")
    eng.observe("great", "p0", "p3")
    eng.observe("great", "p1", "p4")
    eng.acquire("great")
    eng.derive("grand", "p0")
    eng.tell("p0", "grand", "zz", source="teacher")
    prims_other = eng.primitives("other")
    out["identities_separate"] = "rel:grand" in prims_other and "cap:grand@1" in prims_other \
        and eng._find("p0", "cap:grand", "p2") != [] and eng.ask("p0", "grand")["value"] == "zz" \
        and eng.execute(["cap:grand@1"], "p0") == {"p2"}
    out["no_cycle_offered"] = "cap:great@1" not in eng.primitives("grand") and "cap:grand@1" in eng.primitives("great")

    # 7/8: two proofs; one retraction keeps, two remove
    eng = grand_engine(tmp / "a7.json")
    for t in [("k0", "parent", "k1"), ("k0", "parent", "k2"), ("k1", "parent", "k3"), ("k2", "parent", "k3")]:
        eng.tell(*t)
    d = eng.derive("grand", "k0")
    f = eng._find("k0", "cap:grand", "k3")
    two = len(f[0]["supports"]) if f else 0
    eng.retract("k0", "parent", "k1")
    kept = copy.deepcopy(eng._find("k0", "cap:grand", "k3"))
    eng.retract("k0", "parent", "k2")
    out["two_proofs_stored"] = d.get("status") == "derived" and two == 2
    out["one_retraction_keeps_conclusion"] = len(kept) == 1 and len(kept[0]["supports"]) == 1 \
        and not eng._find("k0", "cap:grand", "k3")

    # 9: inference separate from expression
    eng = grand_engine(tmp / "a9.json")
    eng.turn("construct owns: ada owns box = ada box; ned owns key = ned key")
    out["missing_construction_reported"] = eng.turn("what is p0 grand") == "p0 grand p2 [no construction for grand]" \
        and eng.turn("what is rex owns") == "rex owns map"

    # 10: nested validation
    def dangling(st):
        st["facts"][0]["supports"].append({"kind": "derived", "source": "x", "turn": 1, "premises": ["nope a b"], "program": None})

    def missing_dep(st):
        st["capabilities"]["great"]["versions"][0]["seq"] = ["cap:ghost@1", "rel:parent"]

    def dup(st):
        st["facts"].append(copy.deepcopy(st["facts"][0]))

    def badstatus(st):
        st["capabilities"]["grand"]["versions"][0]["status"] = "maybe"

    def cycle(st):
        st["capabilities"]["grand"]["versions"][0]["seq"] = ["cap:great@1"]

    def checksum(st):
        st["turn"] += 1

    def binding(st):  # schema 3 must not carry a stored packet at all
        st["facts"][0]["bits"] = bind("a", "b", "c").bits.hex()

    errs = {k: corrupt(tmp, k, fn) for k, fn in [("dangling", dangling), ("missing_dep", missing_dep), ("dup", dup),
                                                    ("badstatus", badstatus), ("cycle", cycle), ("checksum", checksum),
                                                    ("binding", binding)]}
    want = {"dangling": "dangling premise", "missing_dep": "missing dependency", "dup": "duplicate fact",
            "badstatus": "bad version", "cycle": "dependency cycle", "checksum": "checksum", "binding": "bind"}
    out["nested_validation"] = all(want[k] in errs[k] for k in want)
    out["_validation"] = errs

    # 14: hard cases
    eng = Engine(tmp / "a14.json")
    for t in [("c", "parent", "d1"), ("c", "parent", "d2"), ("d1", "parent", "e1"), ("d2", "parent", "e2")]:
        eng.tell(*t)
    h = eng.evaluate(["rel:parent", "rel:parent"], [["c", "e1"]])
    out["ambiguous_path_undetermined"] = h["status"] == "undetermined" and \
        reference.mark(reference.index([(f["s"], f["r"], f["o"]) for f in eng.state["facts"]]), ["parent", "parent"], "c", "e1") == "undetermined"
    out["multiple_conclusions_ambiguous"] = eng.answer("c", "parent")["status"] == "ambiguous" and \
        eng.turn("what is c parent") == "ambiguous: d1 or d2?"
    eng.observe("pick", "d1", "e1")
    eng.observe("pick", "d1", "e2")
    # a correction of an example (not of a premise) invalidates the procedure
    eng2 = grand_engine(tmp / "a14b.json")
    ce = eng2.turn("correct example grand: p1 -> p9")
    while_suspended = eng2.answer("p0", "grand")["status"]
    fixed = eng2.turn("correct example grand: p1 -> p3")
    out["example_correction_invalidates"] = ce.startswith("corrected example grand: p1 -> p9; none grand") \
        and "grand@1 suspended: contradicted by its observations" in ce and while_suspended == "unknown" \
        and fixed.startswith("corrected example grand: p1 -> p3; qualified grand rel:parent+rel:parent") \
        and eng2.version("grand")["v"] == 1 and eng2.answer("p0", "grand")["value"] == "p2" \
        and len(eng2.state["retired"]["grand"]) == 2
    out["conflicting_observations_adopt_nothing"] = eng.acquire("pick")["result"] == "none" and "pick" not in eng.state["capabilities"]
    return out


def run() -> dict:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        sections = {
            "memory": memory_checks(tmp),
            "constructions": construction_checks(tmp),
            "acquisition": acquisition_checks(tmp),
            "discovery": discovery_checks(tmp),
            "persistence": persistence_checks(tmp),
            "fresh_process": fresh_process_checks(tmp),
            "migration": migration_checks(tmp),
            "audit": audit_checks(tmp),
        }
    checks = {f"{sec}.{k}": bool(v) for sec, c in sections.items() for k, v in c.items() if not k.startswith("_")}
    measures = {f"{sec}.{k[1:]}": v for sec, c in sections.items() for k, v in c.items() if k.startswith("_")}
    failed = [k for k, v in checks.items() if not v]
    receipt = {"schema": SCHEMA, "checks": checks, "measures": measures, "count": len(checks), "failed": failed,
               "claim": "one engine; symbolic and bitwise; not a mind"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/g44_receipt.json").write_text(json.dumps(receipt, indent=2, default=list))
    print(json.dumps(receipt, indent=2, default=list))
    if failed:
        raise SystemExit(1)
    return receipt


if __name__ == "__main__":
    run()
