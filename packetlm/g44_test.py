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
from .engine import Engine, StateError, judge, judge_set, judge_closed, _checksum, SCHEMA, SCHEMA_V2
from .field import add as field_add, ask as field_ask, bind
from . import reference
from . import programs as progs

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


def retention_script(seed=5, families=8):
    """Calls (lists of lines) over unrelated families, with fillers that age old families,
    retention probes that touch all of them, a late correction, a relation shared by two
    entity-disjoint families, a construction sentence and a full listing."""
    rng = random.Random(seed)
    calls = [["construct owns: ada owns box = ada box; ned owns key = ned key"]]
    asked = []
    for k in range(families):
        ra = "f0a" if k == families - 1 else f"f{k}a"  # last family shares a relation with family 0
        rb = f"f{k}b"
        L = [[f"e{k}_{l}_{j}" for j in range(4)] for l in range(3)]
        facts = []
        for j in range(4):
            facts.append((L[0][j], ra, L[1][rng.randrange(4)]))
            facts.append((L[1][j], rb, L[2][rng.randrange(4)]))
        val = {s: next(o2 for s1, r1, o1 in facts if s1 == s and r1 == ra
                       for s2, r2, o2 in facts if s2 == o1 and r2 == rb) for s in L[0]}
        t = f"t{k}"
        calls.append([f"fact {a} {b} {c}" for a, b, c in facts] +
                     [f"example {t}: {L[0][0]} -> {val[L[0][0]]}", f"example {t}: {L[0][1]} -> {val[L[0][1]]}"])
        calls.append([f"investigate {t}"])
        calls.append([f"example {t}: {L[0][2]} -> {val[L[0][2]]}", f"investigate {t}"])
        calls.append([f"what is {L[0][3]} {t}", f"what is {L[0][0]} {ra}"])
        if k == 2:
            calls.append([f"{L[0][0]} owns cup2", f"what is {L[0][0]} owns"])
        for _ in range(9):
            calls.append([f"what is {L[1][rng.randrange(4)]} {rb}"])
        asked.append((L[0][3], t))
        if k == 4:
            calls.append([f"correct {L0_1} {r1a} {L1_1}" for L0_1, r1a, L1_1 in [("e1_0_3", "f1a", "e1_1_0")]] +
                         ["what is e1_0_3 t1"])
        if k % 3 == 2:
            calls.append([f"what is {s} {t}" for s, t in asked])
    calls.append(["capabilities"])
    calls.append(["show t0", "why e0_0_0 t0", "what is e3_0_3 t3"])
    return calls


def retention_checks(tmp) -> dict:
    """Adaptive retention must be invisible in every reply (differential against static),
    must actually archive and restore (not vacuous), and must never delete an archive file."""
    calls = retention_script()
    st, ad = tmp / "ret_static.json", tmp / "ret_adaptive.json"
    same, archived, restored, smallest = True, 0, 0, 1.0
    diffs = []
    for lines in calls:
        e1 = Engine.open(st, deepen=3)
        r1 = [e1.turn(x) for x in lines]
        e1.save()
        e2 = Engine.open(ad, deepen=3, retention="adaptive")
        r2 = [e2.turn(x) for x in lines]
        e2.save()
        archived += e2.stats.get("archived", 0)
        restored += e2.stats.get("restored", 0)
        smallest = min(smallest, ad.stat().st_size / st.stat().st_size)
        if r1 != r2:
            same = False
            diffs.append({"lines": lines, "static": r1, "adaptive": r2})
    folder = ad.with_name(ad.name + ".archive")
    files = sorted(p.name for p in folder.glob("*.json"))
    events = [json.loads(x) for x in (folder / "events.jsonl").read_text().splitlines()] if folder.exists() else []
    ever = {e["archived"] for e in events if "archived" in e}
    from .retention import GUARD, line_tokens
    recent_ok = True
    for e in events:
        if "archived" in e:
            i = e["call"] - 1  # adaptive call k is script call k-1
            seen = set().union(*(line_tokens(x, {"lexicon": {}, "library": []}) for c in calls[max(0, i - GUARD + 1):i + 1] for x in c))
            recent_ok = recent_ok and not (seen & set(e["tokens"]))
    from .retention import refs, refs_walk
    st_doc = json.loads(st.read_text())["state"]
    refs_ok = all(sorted(refs(v)) == sorted(refs_walk(v)) for key in ("capabilities", "hypotheses", "observations")
                  for v in st_doc[key].values()) and len(st_doc["hypotheses"]) >= 8
    final = Engine.open(ad)  # static open restores everything, loudly
    return {
        "adaptive_matches_static": same,
        "adaptive_archives_and_restores": archived >= 3 and restored >= 3,
        "archive_never_deleted": all(f"{sha}.json" in files for sha in ever) and len(ever) >= 3,
        "adaptive_hot_state_smaller": smallest < 0.6,
        "refs_regex_matches_walk": refs_ok,
        "rearchive_reuses_file": len(files) < archived,
        "gate_keeps_recently_touched": recent_ok and any("archived" in e for e in events),
        "static_open_restores_all": "restored_all" in final.report and not final.state["retention"]["archived"]
            and sorted(final.state["capabilities"]) == sorted(Engine.open(st).state["capabilities"]),
        "_retention": {"archived": archived, "restored": restored, "smallest_ratio": round(smallest, 3),
                       "calls": len(calls), "diffs": diffs[:3]},
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


def program_checks(tmp) -> dict:
    """G48 program grammar (packetlm/programs.py, docs/G48.md)."""
    out = {}

    def val(e, name, x):
        d = e.derive(name, x)
        return d["fact"].split()[-1] if d.get("status") == "derived" else None
    rng = random.Random(48)
    # 1-2. differential: memoized interpreter vs independent naive one; trace ends vs run
    agree = nonempty = cmp = trace_ok = 0
    for g in range(6):
        nodes = [f"n{g}_{i}" for i in range(14)]
        ref = {}
        for _ in range(30):
            ref.setdefault(rng.choice(["u", "v"]), {}).setdefault(rng.choice(nodes), set()).add(rng.choice(nodes))
        for x in nodes:
            ref.setdefault("k", {}).setdefault(x, set()).add(rng.choice(["a", "b", "c"]))
        facts = {}
        for r, m in ref.items():
            for x, ts in m.items():
                for t in ts:
                    facts.setdefault((x, r), []).append({"o": t, "id": f"{x} {r} {t}"})
        find = lambda x, r, o=None: [f for f in facts.get((x, r), []) if o is None or f["o"] == o]  # noqa: E731
        ind = progs.Inducer(progs.Ctx(ref), [], nodes, (["u", "v"], []), [("k", "a"), ("k", "b")])
        for k in (2, 3, 4):
            ps = list(ind.programs(k))
            for p in rng.sample(ps, min(60, len(ps))):
                for x in nodes[:7]:
                    a, b = progs.run(progs.Ctx(ref), p, x), progs.run_naive(ref, p, x)
                    cmp += 1
                    agree += set(a) == set(b)
                    nonempty += bool(a)
                    ends = {e for e, _ in progs.trace(p, x, find, lambda t, z: [])}
                    trace_ok += ends == set(a)
    out["prog_run_matches_naive"] = agree == cmp and cmp >= 2000
    out["prog_differential_nonvacuous"] = nonempty >= cmp // 10
    out["prog_trace_ends_match_run"] = trace_ok == cmp
    out["_prog_compared"] = cmp
    # ordered choice: the first clause with a result wins (not a union)
    ref = {"k": {"e": {"A"}}, "r1": {"e": {"x"}}, "r2": {"e": {"y"}, "f": {"z"}}}
    pc = progs.parse("prog:is:k:A>rel:r1|rel:r2")
    out["prog_ordered_choice"] = progs.run(progs.Ctx(ref), pc, "e") == {"x"} and progs.run(progs.Ctx(ref), pc, "f") == {"z"}
    # 3. until-like program acquired from depth 1-2 examples, applied at depth 4
    eng = Engine(tmp / "prog.json", programs=True)
    tri = [("top", "in", "sky"), ("c1", "in", "top"), ("c2", "in", "top"), ("c1", "kind", "land"), ("c2", "kind", "land"),
           ("top", "kind", "roof")]
    chain = {}
    for root in ("c1", "c2"):
        for depth in (1, 2, 3, 4):
            parent = root
            for d in range(depth):
                node = f"{root}_{depth}_{d}"
                tri += [(node, "in", parent), (node, "kind", "mid" if d < depth - 1 else "leaf")]
                chain[node] = root
                parent = node
    for t in tri:
        eng.tell(*t)
    for x in ("c1_1_0", "c2_2_1", "c2_1_0"):
        eng.observe("home", x, chain[x])
    r = eng.acquire("home")
    seq = r.get("seq") or [""]
    deep = [n for n in chain if n.endswith("_4_3") or n.endswith("_3_2")]
    out["prog_until_acquired"] = r["result"] in ("qualified", "provisional") and "self" in seq[0] and ("is:" in seq[0] or "not:" in seq[0])
    out["prog_until_generalizes_depth"] = all(val(eng, "home", n) == chain[n] for n in deep) and len(deep) == 4
    out["prog_until_open_world_provisional"] = r.get("result") == "provisional" and bool(r.get("blocking"))
    # 4. composition through the library; the dependency inside the program string is tracked
    for root, cap in (("c1", "k1"), ("c2", "k2")):
        eng.tell(root, "cap", cap)
    for x in ("c1_1_0", "c2_2_1"):
        eng.observe("hcap", x, {"c1": "k1", "c2": "k2"}[chain[x]])
    r4 = eng.acquire("hcap")
    s4 = (r4.get("seq") or [""])[0]
    out["prog_composition_uses_library"] = s4.startswith("prog:cap:home@") and val(eng, "hcap", "c1_4_3") == "k1"
    ev = eng.revoke("home")
    out["prog_dependency_suspends_dependent"] = eng.version("hcap")["status"] == "suspended" and any("hcap" in e for e in ev)
    eng.save()
    re = Engine.open(tmp / "prog.json", programs=True)
    out["prog_state_reloads"] = re.version("hcap")["seq"] == [s4] and re.report.get("loaded") == "primary"
    # 5. conditional and 6. type filter, acquired from observations; filter qualifies (scan completes)
    e2 = Engine(tmp / "prog2.json", programs=True)
    for i in range(8):
        e = f"p{i}"
        e2.tell(e, "kind", "A" if i % 2 == 0 else "B")
        e2.tell(e, "r1", f"o{i}a")
        e2.tell(e, "r2", f"o{i}b")
        for o in (f"o{i}a", f"o{i}b"):
            e2.tell(o, "kind", "obj")
    for i in (0, 1, 2, 3):
        e2.observe("cond", f"p{i}", f"o{i}a" if i % 2 == 0 else f"o{i}b")
    rc = e2.acquire("cond")
    sc = (rc.get("seq") or [""])[0]
    out["prog_conditional_acquired"] = "|" in sc and all(
        val(e2, "cond", f"p{i}") == (f"o{i}a" if i % 2 == 0 else f"o{i}b") for i in range(4, 8))
    e3 = Engine(tmp / "prog3.json", programs=True)
    for i in range(6):
        e3.tell(f"q{i}", "has", f"t{i}")
        e3.tell(f"t{i}", "kind", "T")
        for j in range(2):
            e3.tell(f"q{i}", "has", f"d{i}{j}")
            e3.tell(f"d{i}{j}", "kind", "D")
    for i in range(3):
        e3.observe("filt", f"q{i}", f"t{i}")
    rf = e3.acquire("filt")
    # full horizon: a longer alternative that is undefined where the candidate is defined and defined
    # on the T-typed objects (`is:kind:T|...`) blocks, so the filter stays provisional (N2)
    out["prog_filter_acquired"] = rf["seq"] == ["prog:rel:has>is:kind:T"] and \
        all(val(e3, "filt", f"q{i}") == f"t{i}" for i in range(3, 6))
    out["prog_filter_full_horizon_blocks"] = rf["result"] == "provisional" and rf["scan"]["horizon"] == progs.MAX_SIZE \
        and any("|" in b[0] and len(progs.parse(b[0])[0]) + len(progs.parse(b[0])[-1]) > 2 for b in rf["blocking"])
    # 7. investigate asks where one hypothesis predicts nothing (one-sided split)
    e4 = Engine(tmp / "prog4.json", programs=True)
    for t in [("a", "in", "r"), ("a", "in", "w"), ("b", "in", "r"), ("b", "in", "w"), ("w", "kind", "Q"),
              ("r", "kind", "R"), ("r", "tag", "u"), ("x", "in", "s"), ("x", "in", "w"), ("s", "kind", "R")]:
        e4.tell(*t)
    e4.observe("up", "a", "r")
    e4.observe("up", "b", "r")
    e4.acquire("up")
    q = e4.investigate("up")
    out["prog_investigate_one_sided"] = q.get("result") == "question" and q.get("subject") == "x" and \
        e4.state["hypotheses"]["up"].get("supported_programs", 0) >= 2
    # the question does not depend on fact storage order (retention restores reorder facts)
    e6 = Engine(tmp / "prog6.json", programs=True)
    facts = [("a", "in", "r"), ("a", "in", "w"), ("b", "in", "r"), ("b", "in", "w"), ("w", "kind", "Q"),
             ("r", "kind", "R"), ("r", "tag", "u"), ("y", "in", "s2"), ("y", "in", "w"), ("s2", "kind", "R"),
             ("x", "in", "s"), ("x", "in", "w"), ("s", "kind", "R")]
    for t in facts:
        e6.tell(*t)
    e6.observe("up", "a", "r")
    e6.observe("up", "b", "r")
    e6.acquire("up")
    e7 = Engine(tmp / "prog7.json", programs=True)
    for t in reversed(facts):
        e7.tell(*t)
    e7.observe("up", "a", "r")
    e7.observe("up", "b", "r")
    e7.acquire("up")
    q6, q7 = e6.investigate("up"), e7.investigate("up")
    out["prog_question_independent_of_fact_order"] = q6.get("result") == "question" and q6 == q7
    # questions stay inside the observations' component (an unrelated world is never asked about)
    for t in [("aa1", "in", "aa2"), ("aa2", "kind", "AA")]:
        e6.tell(*t)  # a disconnected world (no shared token) whose names sort first
    pool = e6._question_pool("up")
    out["prog_question_inside_component"] = "aa1" not in pool and "aa2" not in pool and {"x", "y"} <= set(pool) \
        and pool == sorted(pool) and e6.investigate("up").get("subject") == q6.get("subject")
    # set, not just order: with adaptive retention (other world archived, the task's own world archived
    # and restored on reference) the question pool and the question equal the static engine's
    from . import retention as ret_mod
    # the unrelated world shares no token, relations included, so retention sees two components
    worlds = facts + [("aa1", "on", "aa2"), ("aa1", "on", "aa3"), ("aa2", "sort", "AR"), ("aa3", "sort", "AQ")]
    es = Engine(tmp / "prog8.json", programs=True)
    ea = Engine(tmp / "prog9.json", programs=True, retention="adaptive")
    for e_ in (es, ea):
        for t in worlds:
            e_.tell(*t)
        e_.observe("up", "a", "r")
        e_.observe("up", "b", "r")
        e_.acquire("up")
    comps, _ = ret_mod.components(ea.state)
    for comp in list(comps.values()):
        ret_mod.archive(ea.state, ea.state["retention"], ea._archive_dir, comp, {"why": "test"})
    ea._dirty()
    archived_all = not ea.state["facts"] and len(comps) == 2
    rs, ra = es.turn("investigate up"), ea.turn("investigate up")
    out["prog_question_pool_same_set_under_retention"] = archived_all and rs == ra and \
        es._question_pool("up") == ea._question_pool("up") and "aa1" not in ea.entities() and "aa1" in es.entities()
    # programs off: no program tokens are ever hypothesised
    e5 = Engine(tmp / "prog5.json", deepen=3)
    for t in tri:
        e5.tell(*t)
    for x in ("c1_1_0", "c2_2_1", "c2_1_0"):
        e5.observe("home", x, chain[x])
    r5 = e5.acquire("home")
    out["prog_off_no_program_tokens"] = not any(str(x).startswith("prog:") for x in (r5.get("seq") or []))
    return out


def px_checks(tmp) -> dict:
    """PX teacher statements `-> !none` / `-> !several` (docs/PX.md)."""
    out = {}
    table = [(set(), "!none", "supported"), ({"x"}, "!none", "contradicted"), ({"x", "y"}, "!none", "contradicted"),
             (set(), "!several", "undetermined"), ({"x"}, "!several", "contradicted"), ({"x", "y"}, "!several", "supported"),
             (set(), "x", "undetermined"), ({"x"}, "x", "supported"), ({"y"}, "x", "contradicted"), (None, "!none", "undetermined")]
    out["px_judge_table"] = all(judge_set(o, a) == w and progs.judge_set(o or set(), a) == (w if o is not None else "supported")
                                for o, a, w in table)

    def world(path, answers):
        e = Engine(path, deepen=2, answers=answers)
        for t in [("a", "r1", "x"), ("a", "r2", "x"), ("b", "r1", "x2"), ("b", "r2", "x2"), ("c", "r1", "y")]:
            e.tell(*t)
        e.observe("h", "a", "x")
        e.observe("h", "b", "x2")
        return e, e.acquire("h")
    e0, r0 = world(tmp / "px0.json", False)
    q0 = e0.investigate("h")
    e1, r1 = world(tmp / "px1.json", True)
    q1 = e1.investigate("h")
    asked = q1.get("subject")
    e1.observe("h", asked, "!none")  # truth of the hidden r2 at c: no value (stated, not withheld)
    r2 = e1.acquire("h")
    out["px_base_one_sided_unresolved_without"] = r0["result"] == "ambiguous" and q0["result"] != "question"
    out["px_base_none_resolves_ambiguity"] = r1["result"] == "ambiguous" and asked == "c" and \
        r2.get("seq") == ["rel:r2"] and r2["result"] in ("qualified", "provisional")
    # base scan: a more-defined alternative is contradicted by `!none` where the candidate is empty
    out["px_base_qualifies_after_none"] = r2["result"] == "qualified"
    # programs: the filter's open-world blocker `is:kind:T|...` is defined on the T objects, where the
    # truth is stated as none; after that statement no blocker of that form remains among those kept
    e3 = Engine(tmp / "px3.json", programs=True, answers=True)
    for i in range(6):
        e3.tell(f"q{i}", "has", f"t{i}")
        e3.tell(f"t{i}", "kind", "T")
        for j in range(2):
            e3.tell(f"q{i}", "has", f"d{i}{j}")
            e3.tell(f"d{i}{j}", "kind", "D")
    for i in range(3):
        e3.observe("filt", f"q{i}", f"t{i}")
    before = e3.acquire("filt")
    selfish = lambda r: [b[0] for b in r.get("blocking", []) if b[0].startswith("prog:is:kind:T|")]  # noqa: E731
    for i in range(3):
        e3.observe("filt", f"t{i}", "!none")
    after = e3.acquire("filt")
    out["px_programs_none_contradicts_more_defined"] = bool(selfish(before)) and not selfish(after) and \
        after.get("seq") == ["prog:rel:has>is:kind:T"]
    out["px_statements_not_guard_proposals"] = ("kind", "T") in progs.proposals(
        {"kind": {"t0": {"T"}}}, [("q0", "t0"), ("t1", "!none")])
    out["_px_blockers_before_after"] = [len(before.get("blocking", [])), len(after.get("blocking", []))]
    return out


def g49_checks(tmp) -> dict:
    """G49: exact pruned scan, P1 guard (statements alone adopt nothing), `complete X` (docs/G49.md)."""
    from . import scan_exact_proof as proof
    out = {}
    rng = random.Random(4949)
    same, cases, closed_cases = True, 0, 0
    for _ in range(14):
        ctx, obs, ents, steps, guards, closed = proof.world(rng)
        ind = progs.Inducer(ctx, obs, ents, steps, guards, closed=closed)
        _, sup = ind.search()
        cand = sup[0] if sup else next(ind.programs(1))
        pred = {e: progs.run(ctx, cand, e) for e in ind.domain}
        order, count = proof.brute(ind, cand, pred)
        ex = progs.Exact(ind).run(cand, pred, keep=10 ** 9)
        same &= ex["complete"] and ex["blockers"] == order and ex["programs"] == count
        cases += 1
        closed_cases += bool(closed)
    out["exact_scan_equals_brute_force"] = same and cases == 14 and closed_cases >= 3
    # P1 of e944840: a statement alone never founds a capability, in either mode
    for mode, kw in (("programs", {"programs": True, "answers": True}), ("base", {"deepen": 2, "answers": True})):
        e = Engine(tmp / f"p1{mode}.json", **kw)
        e.tell("a", "p", "b")
        e.tell("b", "p", "c")
        e.observe("k", "c", "!none")
        r = e.acquire("k")
        v0 = e.version("k")
        e.observe("k", "a", "b")
        r2 = e.acquire("k")
        out[f"p1_statement_alone_adopts_nothing_{mode}"] = r["result"] == "none" and not v0 \
            and r2["result"] in ("qualified", "provisional")

    def fcw(path, programs):
        e = Engine(path, deepen=2, programs=programs)
        for t in [("a", "r1", "x"), ("a", "r2", "m"), ("m", "r3", "x"), ("b", "r1", "x2"), ("c", "r1", "x3"),
                  ("c", "r2", "m3"), ("m3", "r3", "x3")]:
            e.tell(*t)
        e.observe("h", "a", "x")
        e.observe("h", "b", "x2")
        return e, e.acquire("h")
    table = [(set(), "x", "contradicted"), ({"x"}, "x", "supported"), ({"x", "y"}, "x", "contradicted"),
             (set(), "!several", "contradicted"), ({"x"}, "!none", "contradicted"), (None, "x", "undetermined")]
    out["fc_judge_table"] = all(judge_closed(o, a) == w for o, a, w in table) and \
        all(progs.judge_closed(o, a) == w for o, a, w in table if o is not None)
    for mode in ("base", "programs"):
        e, r = fcw(tmp / f"fc{mode}.json", mode == "programs")
        unobs = e.turn("complete c")  # scope: no observation at c, nothing changes
        st0 = e.version("h")["status"]
        obs = e.state["observations"]["h"]
        alt = ["prog:rel:r2>rel:r3"] if mode == "programs" else ["rel:r2", "rel:r3"]
        ev0 = e.evaluate(alt, obs)["status"]
        msg = e.turn("complete b")
        st1 = e.version("h")["status"]
        ev1 = e.evaluate(alt, obs)["status"]
        out[f"fc_evaluate_closed_at_complete_{mode}"] = ev0 != "contradicted" and ev1 == "contradicted"
        e.turn("fact b r4 z")  # falsifies the statement: retracted, re-acquired open-world
        st2 = e.version("h")["status"]
        log = e.state.get("complete_log", [])
        if mode == "programs":
            # after the H1 fix the guard space under `complete` is every pair on the component, so the
            # fcw world stays provisional (is:r1:x2>rel:r1 etc. are real alternatives at m); the
            # programs-mode positive uses a world where completeness at both subjects decides it
            st1 = []
            for comp in (False, True):
                ep = Engine(tmp / f"fcq{comp}.json", programs=True)
                for t in [("a", "r1", "c"), ("c", "r1", "c"), ("c", "r2", "c"), ("d", "r1", "e")]:
                    ep.tell(*t)
                for s_, v_ in (("a", "c"), ("c", "c")):
                    ep.turn(f"example hq: {s_} -> {v_}")
                    if comp:
                        ep.turn(f"complete {s_}")
                st1.append(ep.version("hq")["status"])
            st1 = "qualified" if st1 == ["provisional", "qualified"] else str(st1)
        out[f"fc_less_defined_refuted_qualifies_{mode}"] = r["result"] == "provisional" and r["blocking"] and \
            msg.startswith("complete b") and st1 == "qualified"
        out[f"fc_scope_unobserved_changes_nothing_{mode}"] = unobs.startswith("complete c") and st0 == "provisional"
        out[f"fc_violation_retracts_and_demotes_{mode}"] = st2 == "provisional" and \
            [x["x"] for x in log] == ["b"] and "b" not in e.state.get("complete", {}) and "c" in e.state["complete"]
    e, r = fcw(tmp / "fcdrop.json", False)
    e.turn("complete b")
    e.retract("b", "r1")  # a removed told fact inside the closure falsifies it too
    out["fc_removed_fact_retracts"] = [x["x"] for x in e.state.get("complete_log", [])] == ["b"]
    eo = Engine(tmp / "l3.json", deepen=2, operators=True)
    for t in [("a", "p", "b"), ("b", "kind", "T"), ("c", "p", "d"), ("d", "kind", "T")]:
        eo.tell(*t)
    eo.observe("u", "a", "b")
    eo.observe("u", "c", "d")
    before = eo._operator_prims("u")
    eo.observe("u", "b", "!none")
    out["l3_statement_not_operator_answer"] = bool(before) and eo._operator_prims("u") == before
    # G50 tie-break: equally splitting subjects -> smallest closure first, then name
    for ans in (False, True):
        et = Engine(tmp / f"tb{ans}.json", programs=True, answers=ans)
        for t in [("a", "r1", "x"), ("a", "r2", "x"), ("b", "r1", "x"), ("b", "r2", "z"), ("z", "r3", "w"),
                  ("w", "r3", "v"), ("c", "r1", "x"), ("c", "r2", "q")]:
            et.tell(*t)
        et.observe("h", "a", "x")
        rr = et.acquire("h")
        sizes = et._closure_sizes()
        q = et.investigate("h")
        out[f"g50_tiebreak_smallest_closure_{'answers' if ans else 'values'}"] = rr["result"] == "ambiguous" and \
            sizes["b"] == 5 and sizes["c"] == 3 and q.get("subject") == "c"
    # G51: --qualified-library offers only qualified capabilities as library steps
    libs = {}
    for ql in (False, True):
        el = Engine(tmp / f"ql{ql}.json", deepen=2, qualified_library=ql)
        for t in [("p1", "s", "v1"), ("p2", "s", "v2"), ("a", "r1", "x"), ("a", "r2", "m"), ("m", "r3", "x"),
                  ("b", "r1", "x2"), ("c", "r1", "x3"), ("c", "r2", "m3"), ("m3", "r3", "x3")]:
            el.tell(*t)
        el.observe("good", "p1", "v1")
        el.observe("good", "p2", "v2")
        el.acquire("good")
        el.observe("open", "a", "x")
        el.observe("open", "b", "x2")
        el.acquire("open")
        libs[ql] = ([el.version(n)["status"] for n in ("good", "open")],
                    sorted(p for p in el.primitives("new") if p.startswith("cap:")))
    out["g51_qualified_library_offers_only_qualified"] = libs[False][0] == libs[True][0] == ["qualified", "provisional"] \
        and libs[False][1] == ["cap:good@1", "cap:open@1"] and libs[True][1] == ["cap:good@1"]
    # verification b2bb9b8 regressions (H1, M1, M2), the verifier's reproductions
    def run_lines(fn, lines, **kw):
        e_ = Engine(tmp / fn, answers=True, **kw)
        return e_, [e_.turn(l) for l in lines]
    h1 = ["fact e0 k cb", "fact e0 ra e4", "fact e1 ra e4", "fact e2 k ca", "fact e2 ra e3", "fact e3 ra e4",
          "fact e4 k cb", "fact e4 ra e0", "example kk: e4 -> e0", "complete e4", "example kk: e2 -> e2", "complete e2"]
    eh, rh = run_lines("h1.json", h1 + ["what is e1 kk", "what is e3 kk"], programs=True)
    # truth (is:k:ca|is:k:cb>rel:ra>is:k:cb) has no value at e1 or e3: no qualified value may be given
    out["h1_hidden_guard_no_wrong_qualified"] = all(not r.startswith(("e1 kk", "e3 kk")) or "[provisional]" in r
                                                    for r in rh[-2:]) \
        and eh.state["hypotheses"]["kk"].get("scan", {}).get("guard_gap", 0) == 0 and "k" in str(eh.state["hypotheses"]["kk"]["guards"])
    w21 = [("e0", "ra", "e7"), ("e1", "k", "cb"), ("e1", "ra", "e6"), ("e2", "k", "cb"), ("e2", "ra", "e1"), ("e3", "k", "cb"),
           ("e3", "ra", "e0"), ("e3", "ra", "e5"), ("e4", "ra", "e8"), ("e5", "ra", "e5"), ("e7", "k", "cb"), ("e7", "ra", "e1"),
           ("e7", "ra", "e8"), ("e8", "k", "cb"), ("e8", "ra", "e7"), ("e9", "k", "cb"), ("e9", "ra", "e1")]
    l21 = [f"fact {a_} {r_} {b_}" for a_, r_, b_ in w21]
    for x in ("e7", "e9", "e0", "e3", "e1"):  # truth: not:k:ca|... with no k ca told = identity
        l21 += [f"example kk: {x} -> {x}", f"complete {x}"]
    _, r21 = run_lines("h1b.json", l21 + ["what is e4 kk"], programs=True)
    # L2 of cdb4828: the positive case, the identity truth is answered (e4 -> e4)
    out["h1_identity_expressible_under_complete"] = r21[-1].startswith("e4 kk e4")
    m1p = ["fact a p b", "fact x q w", "example k1: a -> b", "complete a", "example k1: x -> y", "complete x"]
    em, _ = run_lines("m1p.json", m1p, programs=True)
    base7 = ["fact a p b", "fact b p c", "fact c k top", "fact b k mid", "fact x p y", "fact y k top", "fact z p a"]
    eb, rb = run_lines("m1b.json", base7 + ["example k1: a -> c", "example k1: x -> y", "complete a", "complete x",
                                              "what is z k1"], deepen=2)
    out["m1_complete_after_example_reviews_version"] = em.version("k1")["status"] not in ("qualified",) \
        and eb.version("k1")["status"] == "suspended" and not rb[-1].startswith("z k1")
    # H1: more component pairs than MAX_GUARDS -> the guard space stays data-dependent -> not qualified
    eg, _ = run_lines("h1gap.json", [f"fact {a_} {r_} {b_}" for a_, r_, b_ in
                                     [("a", "r1", "c"), ("c", "r1", "c"), ("c", "r2", "c"), ("d", "r1", "e")]
                                     + [("c", "k", f"v{i}") for i in range(8)]]
                      + ["example hq: a -> c", "complete a", "example hq: c -> c", "complete c"], programs=True)
    sg = eg.state["hypotheses"]["hq"]["scan"]
    out["h1_guard_gap_caps_at_provisional"] = sg["guard_gap"] > 0 and sg["blocking_n"] == 0 and sg["complete"] \
        and eg.version("hq")["status"] == "provisional"
    # G55 (option 3): an observation-independent budget covering the component removes the gap
    eg16, _ = run_lines("h1gap16.json", [f"fact {a_} {r_} {b_}" for a_, r_, b_ in
                                         [("a", "r1", "c"), ("c", "r1", "c"), ("c", "r2", "c"), ("d", "r1", "e")]
                                         + [("c", "k", f"v{i}") for i in range(8)]]
                        + ["example hq: a -> c", "complete a", "example hq: c -> c", "complete c"], programs=True,
                        closed_guards=16)
    s16 = eg16.state["hypotheses"]["hq"]["scan"]
    out["g55_budget_covers_component"] = s16["guard_gap"] == 0 and sg["guard_gap"] > 0 \
        and len(eg16.state["hypotheses"]["hq"]["guards"]) > progs_max_guards() \
        and (eg16.version("hq")["status"] == "qualified") == (s16["complete"] and s16["blocking_n"] == 0)
    # M2: a qualified version answers [provisional] outside the domain its scan decided
    e2_, r2_ = run_lines("m2.json", ["fact a r1 x", "fact b r1 y", "example g: a -> x", "example g: b -> y",
                                     "fact n1 r1 n2", "what is n1 g", "what is a g"], deepen=2)
    out["m2_qualified_scoped_to_domain"] = e2_.version("g")["status"] == "qualified" \
        and "[provisional]" in r2_[-2] and r2_[-2].startswith("n1") and "[provisional]" not in r2_[-1]
    # S1 of cdb4828: facts growing inside a qualified version's region re-run its scan
    s1 = ["fact a r1 c", "fact c r1 c", "fact c r2 c", "fact m r1 c", "example hq: a -> c", "complete a",
          "example hq: c -> c", "complete c", "what is m hq"]
    es1, rs1 = run_lines("s1.json", s1 + ["fact u r3 z", "what is m hq", "fact m r3 z", "what is m hq"], programs=True)
    out["s1_growth_in_region_requalifies"] = "[provisional]" not in rs1[8] and "[provisional]" not in rs1[10] \
        and "[provisional]" in rs1[12] and es1.stats.get("grown_requalified") == 1
    # N1 of 050bebd: a re-acquisition after a retraction that finds no candidate caps the version
    n1 = ["fact e0 ra e1", "fact e0 ra e2", "fact e1 k cb", "fact e1 ra e2", "fact e1 rb e1", "fact e2 k ca",
          "fact e2 rb e4", "fact e3 ra e2", "fact e3 ra e4", "example kk: e4 -> e4", "complete e4", "example kk: e2 -> e2",
          "complete e2", "example kk: e1 -> e1", "complete e1", "example kk: e3 -> e4", "complete e3",
          "example kk: e0 -> e0", "complete e0", "show kk", "fact e3 ra n2", "show kk", "what is e3 kk"]
    en1, rn1 = run_lines("n1.json", n1, programs=True)
    out["n1_no_candidate_caps_at_provisional"] = " qualified;" in rn1[19] and en1.state["hypotheses"]["kk"].get("candidate") is None \
        and " provisional;" in rn1[21] and rn1[22].endswith("[provisional]")
    # L1 of cdb4828: qualified only on qualified dependencies; a demoted dependency demotes dependents
    el1 = Engine(tmp / "l1dep.json", deepen=2)
    for t in [("p1", "s", "v1"), ("p2", "s", "v2"), ("v1", "t", "w1"), ("v2", "t", "w2")]:
        el1.tell(*t)
    el1.observe("y", "p1", "v1")
    el1.observe("y", "p2", "v2")
    el1.acquire("y")
    el1._set_status("y", 1, "provisional", "test")
    el1._adopt("k", {"seq": ["cap:y@1", "rel:t"], "support": 2}, "qualified", [])
    k_cap = el1.version("k")["status"]
    el1._set_status("y", 1, "qualified", "test")
    el1._adopt("k2", {"seq": ["cap:y@1", "rel:t"], "support": 2}, "qualified", [])
    k2_q = el1.version("k2")["status"]
    el1._set_status("y", 1, "provisional", "test")
    out["l1_qualified_needs_qualified_deps"] = k_cap == "provisional" and k2_q == "qualified" \
        and el1.version("k2")["status"] == "provisional"
    # G53 (docs/G53.md): --bounded is exact. Scan outputs equal the unbounded scan's, with a library
    def g53_world(bd):
        e_ = Engine(tmp / f"g53w{bd}.json", deepen=3, answers=True, bounded=bd)
        ents = [f"n{i}" for i in range(14)]
        for i in range(14):
            e_.tell(ents[i], "a", ents[(i + 1) % 14])
            e_.tell(ents[i], "b", ents[(i * 3 + 2) % 14])
            if i % 2:
                e_.tell(ents[i], "c", ents[(i + 5) % 14])
        for nm, sq, subs in (("ab", ["rel:a", "rel:b"], ents[:3]), ("ba", ["rel:b", "rel:a"], ents[3:6])):
            for s_ in subs:
                o_ = e_.execute(sq, s_)
                e_.turn(f"example {nm}: {s_} -> {next(iter(o_))}")
        e_.observe("nx", "n1", "n5")
        return e_
    scans = {}
    for bd in (False, True):
        e_ = g53_world(bd)
        keep = ("scanned", "evaluated", "contradicted", "compatible", "blocking_n", "conflicts", "blocking", "domain")
        scans[bd] = [{k: v for k, v in e_._scan(n, sq, 3).items() if k in keep}
                     for n, sq in (("ab", e_.version("ab")["seq"]), ("ba", e_.version("ba")["seq"]), ("nx", ["rel:a", "rel:a", "rel:a", "rel:a"]),
                                   ("nx", ["cap:ab@1", "rel:c"]))]
        scans[bd].append([e_.version(n)["status"] for n in ("ab", "ba")])
    out["g53_bounded_scan_equals_unbounded"] = scans[False] == scans[True] and any(x["blocking_n"] for x in scans[True][:4]) \
        and sum(x["scanned"] for x in scans[True][:4]) > 50
    # G53: a new `complete` statement does not re-scan a settled (qualified, still supported,
    # unchanged basis) version; a changed basis or a retraction does
    sk = {}
    for bd in (False, True):
        e_ = Engine(tmp / f"g53fc{bd}.json", deepen=2, bounded=bd)
        for t in [("p1", "s", "v1"), ("p2", "s", "v2"), ("p4", "s", "v4")]:
            e_.tell(*t)
        e_.turn("example good: p1 -> v1")
        e_.turn("example good: p2 -> v2")
        st0 = e_.version("good")["status"]
        e_.turn("complete p1")
        n1 = e_.stats.get("fc_skipped", 0)
        e_.turn("fact p3 s v3")  # basis changes (fact epoch)
        e_.turn("complete p2")
        n2 = e_.stats.get("fc_skipped", 0)
        e_.turn("fact p1 t z")  # inside p1's closure: retracts the statement -> re-acquired
        n3 = e_.stats.get("fc_skipped", 0)
        sk[bd] = (st0, n1, n2, n3, e_.version("good")["status"], len(e_.state.get("complete_log", [])))
    out["g53_fc_skip_only_settled"] = sk[True][0] == "qualified" and sk[True][1:4] == (1, 1, 1) \
        and sk[False][1:4] == (0, 0, 0) and sk[True][4] == sk[False][4] and sk[True][5] == sk[False][5] == 1
    # G54 (docs/G54.md): --lean is exact (replies, recall) and keeps the persistence guarantees
    import random as _r
    rg = _r.Random(54)
    ents = [f"n{i}" for i in range(40)]
    rels = ["ra", "rb", "rc"]
    wl = sorted({(rg.choice(ents), rg.choice(rels), rg.choice(ents)) for _ in range(120)})
    lines54 = [f"fact {a} {b} {c}" for a, b, c in wl] + ["example kx: n1 -> n2", "example kx: n3 -> n4"]
    qs54 = [f"what is {e} {r}" for e in ents for r in rels + ["kx"]]
    rep54, rec54 = {}, {}
    for ln in (False, True):
        e_ = Engine(tmp / f"lean{ln}.json", answers=True, lean=ln, deepen=3)
        rep54[ln] = [e_.turn(l) for l in lines54 + qs54]
        rec54[ln] = [e_.ask(e, r) for e in ents for r in rels]
        e_.save()
    known = sum(x["status"] == "known" for x in rec54[True])
    amb = sum(x["status"] == "ambiguous" for x in rec54[True])
    out["g54_lean_replies_and_recall_equal"] = rep54[False] == rep54[True] and rec54[False] == rec54[True] \
        and known > 0 and amb > 0
    # persistence: lean files open in either engine; a tampered primary is refused and the backup
    # (the previous primary, byte for byte) is used; an invalid state is never written
    pl = tmp / "leanp.json"
    e1 = Engine.open(pl, lean=True)
    e1.turn("fact a r b")
    e1.save()
    first = pl.read_bytes()
    e2 = Engine.open(pl, lean=True)
    e2.turn("fact b r c")
    e2.save()
    second = pl.read_bytes()
    bak_ok = (tmp / "leanp.json.bak").exists() and (tmp / "leanp.json.bak").read_bytes() == first
    plain_reads = Engine.open(pl).report == {"loaded": "primary"} and Engine.open(pl, lean=True).report == {"loaded": "primary"}
    import re as _re
    # structurally valid edit of the state's turn counter (the first key in insertion order since M1)
    tampered = _re.sub(rb'"state": \{"turn": \d+', b'"state": {"turn": 999', second, count=1)
    pl.write_bytes(tampered)
    try:
        tam = Engine.open(pl, lean=True).report
    except StateError:
        tam = {"loaded": "none"}
    pl.write_bytes(second)
    e3 = Engine.open(pl, lean=True)
    e3.state["facts"].append(dict(e3.state["facts"][0]))  # duplicate fact: invalid
    try:
        e3.save()
        refused = False
    except StateError:
        refused = True
    # a primary corrupted by someone else after this process loaded it is never backed up over a good backup
    e4 = Engine.open(pl, lean=True)
    good_bak = (tmp / "leanp.json.bak").read_bytes()
    pl.write_bytes(b"{corrupt")
    e4.save()
    kept = (tmp / "leanp.json.bak").read_bytes() == good_bak
    pl.write_bytes(second)
    out["g54_lean_persistence_guarantees"] = kept and bak_ok and plain_reads and tampered != second and tam.get("loaded") == "backup" \
        and tam.get("recovered") is True and refused and pl.read_bytes() == second
    # fast validation accepts exactly what `validate` accepts (fuzzed corruptions of real states)
    from .engine import _valid_fast, validate as _validate
    base_docs = []
    for ln in (False, True):
        st_ = json.loads(json.dumps(Engine.open(tmp / f"lean{ln}.json").state))
        base_docs.append(st_)
    ev = Engine(tmp / "fz.json", answers=True, deepen=3)
    for l in ["fact a p b", "fact b q c", "fact d p e", "fact e q f", "example g1: a -> b", "example g1: d -> e",
              "example g2: a -> c", "example g2: d -> f"]:
        ev.turn(l)
    base_docs.append(json.loads(json.dumps(ev.state)))
    fz = _r.Random(541)

    def corrupt(st_):
        st_ = copy.deepcopy(st_)
        k = fz.randrange(12)
        facts = st_["facts"]
        if k == 0 and facts:
            facts.append(copy.deepcopy(fz.choice(facts)))
        elif k == 1 and facts:
            fz.choice(facts)["id"] += "x"
        elif k == 2 and facts:
            fz.choice(facts)["supports"][0]["premises"].append("nope nope nope")
        elif k == 3 and facts:
            fz.choice(facts)["supports"] = []
        elif k == 4:
            st_[fz.choice(["turn", "facts", "log", "capabilities", "observations"])] = "bad"
        elif k == 5 and st_["capabilities"]:
            c = st_["capabilities"][fz.choice(sorted(st_["capabilities"]))]
            c["current"] = len(c["versions"]) + 1
        elif k == 6 and st_["capabilities"]:
            n = fz.choice(sorted(st_["capabilities"]))
            st_["capabilities"][n]["versions"][0]["seq"] = [f"cap:{n}@1"]  # self-cycle
        elif k == 7 and st_["capabilities"]:
            n = fz.choice(sorted(st_["capabilities"]))
            st_["capabilities"][n]["versions"][0]["status"] = "weird"
        elif k == 8 and st_["observations"]:
            st_["observations"][fz.choice(sorted(st_["observations"]))].append(["only"])
        elif k == 9 and facts:
            fz.choice(facts)["bits"] = "00"
        elif k == 10 and facts:
            fz.choice(facts)["supports"][0]["kind"] = "guessed"
        elif k == 11:
            st_["lexicon"]["w"] = 3
        return st_

    agree, rejected, total = 0, 0, 0
    for i in range(300):
        st_ = corrupt(fz.choice(base_docs)) if i % 5 else copy.deepcopy(fz.choice(base_docs))
        doc = {"schema": SCHEMA, "checksum": _checksum(st_) if isinstance(st_, dict) else "", "state": st_}
        try:
            _validate(doc)
            ok = True
        except StateError:
            ok = False
        except Exception:
            continue
        total += 1
        rejected += not ok
        agree += _valid_fast(doc) == ok
    out["g54_fast_validation_equivalent"] = agree == total and total >= 250 and 100 <= rejected < total
    ea = Engine(tmp / "fcret.json", deepen=2, retention="adaptive")
    out["fc_refused_with_adaptive_retention"] = ea.turn("complete b").startswith("complete is not supported")
    return out


SERVE_FLAGS = ["--answers", "--bounded", "--lean", "--deepen=3"]
SERVE_SCRIPT = [
    ["fact a1 p b1", "fact b1 q c1", "fact a2 p b2", "fact b2 q c2", "fact a3 p b3", "fact b3 q c3",
     "fact a4 p b4", "fact b4 q c4"],
    ["example pq: a1 -> c1", "example pq: a2 -> c2"],
    ["investigate pq"],
    ["what is a3 pq", "what is a4 pq"],
    ["correct b4 q c9"],
    ["what is a4 pq", "capabilities"],
    ["fact a5 p b5", "fact b5 q c5", "what is a5 pq"],
    ["retract b1 q c1"],
    ["what is a1 pq", "why a5 pq", "show pq"],
]


def _per_process(path, script):
    """The per-process protocol in-process: open, turn, save per call (as `python -m packetlm.engine`)."""
    from .engine import parse_cli
    kw = parse_cli(SERVE_FLAGS)[0]
    out = []
    for lines in script:
        e = Engine.open(path, **kw)
        out.append([e.turn(x) for x in lines])
        e.save()
    return out


def serve_checks(tmp: Path) -> dict:
    """G56: the long-lived protocol (packetlm/serve.py) gives the per-process replies and state, its
    journal recovers every returned call, replay is verified, and a new path starts empty.
    Each check is guarded: an exception fails that check by name, not the section."""
    from . import serve
    from .engine import StateError as SE, parse_cli
    out = {}

    def guarded(name, fn):
        try:
            out[name] = bool(fn())
        except Exception as exc:  # noqa: BLE001
            out[name] = False
            out["_" + name + "_error"] = f"{type(exc).__name__}: {exc}"[:200]

    ref = _per_process(tmp / "s_ref.json", SERVE_SCRIPT)
    ref_state = json.loads((tmp / "s_ref.json").read_text())["state"]

    def equal():
        srv = serve.Server(snapshot_every=5)  # 9 calls: the closing snapshot carries calls 6-9
        got = [srv.call(tmp / "s_srv.json", SERVE_FLAGS, lines)["replies"] for lines in SERVE_SCRIPT]
        srv.close()
        srv_state = json.loads((tmp / "s_srv.json").read_text())["state"]
        return got == ref and srv_state == ref_state and len(ref) == len(SERVE_SCRIPT) \
            and any("qualified" in " ".join(r) for r in ref)
    guarded("g56_serve_replies_and_state_equal", equal)

    # crash after 5 calls (snapshot after call 3, journal holds calls 4-5): nothing returned is lost
    p = tmp / "s_crash.json"
    jp, bakp = p.with_name(p.name + ".journal"), p.with_name(p.name + ".bak")
    srv = serve.Server(snapshot_every=3)
    for lines in SERVE_SCRIPT[:5]:
        srv.call(p, SERVE_FLAGS, lines)
    srv.cur.jfh.close()
    srv.cur = None  # killed: no closing snapshot
    jcopy, pcopy = jp.read_bytes(), p.read_bytes()
    bcopy = bakp.read_bytes() if bakp.exists() else None

    def restore(jbytes):
        p.write_bytes(pcopy)
        if bcopy is None:
            bakp.unlink(missing_ok=True)
        else:
            bakp.write_bytes(bcopy)
        jp.write_bytes(jbytes)

    def recovers():
        restore(jcopy)
        s1 = serve.Server(snapshot_every=3)
        r6 = s1.call(p, SERVE_FLAGS, SERVE_SCRIPT[5])
        rest = [r6["replies"]] + [s1.call(p, SERVE_FLAGS, lines)["replies"] for lines in SERVE_SCRIPT[6:]]
        s1.close()
        return r6["load"].get("journal_replayed") == 2 and rest == ref[5:] \
            and json.loads(p.read_text())["state"] == ref_state
    guarded("g56_serve_journal_recovers", recovers)

    def reopen(jbytes):
        restore(jbytes)
        s2 = serve.Server(snapshot_every=3)
        try:
            return s2.call(p, SERVE_FLAGS, SERVE_SCRIPT[5])
        except SE as exc:
            return {"error": str(exc)}

    def replay_verified():
        head, *recs = jcopy.splitlines()
        bad = json.loads(recs[0])
        bad["replies_sha256"] = "0" * 64
        tampered = reopen(b"\n".join([head, json.dumps(bad).encode(), *recs[1:]]) + b"\n")
        torn = reopen(jcopy + b'{"flags": ["--ans')
        wrong_base = reopen(b"\n".join([json.dumps({"schema": serve.JOURNAL_SCHEMA, "base": "f" * 64}).encode(),
                                        *recs]) + b"\n")
        return len(recs) == 2 and "diverged" in tampered.get("error", "") and torn.get("replies") == ref[5] \
            and torn["load"].get("journal_replayed") == 2 and "does not extend" in wrong_base.get("error", "")
    guarded("g56_serve_replay_verified", replay_verified)

    def contained():
        # crash between a snapshot and the journal restart: the old journal is in the primary; dropped
        restore(jcopy)
        s3 = serve.Server(snapshot_every=3)
        s3.call(p, SERVE_FLAGS, ["capabilities"])  # replays and snapshots (old primary becomes the backup)
        s3.cur.jfh.close()
        s3.cur = None
        jp.write_bytes(jcopy)  # the old journal reappears
        s4 = serve.Server(snapshot_every=3)
        r = s4.call(p, SERVE_FLAGS, SERVE_SCRIPT[5])
        s4.close()
        return "journal_dropped" in r["load"] and r["replies"] == ref[5]
    guarded("g56_serve_contained_journal_dropped", contained)

    def starts_empty():
        # B: a new path starts from a fresh empty state, never the open one
        s5 = serve.Server()
        s5.call(tmp / "s_b1.json", SERVE_FLAGS, SERVE_SCRIPT[0] + SERVE_SCRIPT[1])
        fresh = s5.call(tmp / "s_b2.json", SERVE_FLAGS, ["what is a1 pq", "capabilities"])["replies"]
        s5.close()
        e0 = Engine(tmp / "s_b0.json", **parse_cli(SERVE_FLAGS)[0])
        return fresh == [e0.turn("what is a1 pq"), e0.turn("capabilities")] and fresh[1] == "none"
    guarded("g56_serve_new_path_starts_empty", starts_empty)

    def validated():
        # the state after every call is validated in memory, as before every per-process save
        s6 = serve.Server()
        s6.call(tmp / "s_v.json", SERVE_FLAGS, SERVE_SCRIPT[0])
        s6.cur.state["retired"] = []
        try:
            s6.handle({"op": "call", "state": str(tmp / "s_v.json"), "flags": SERVE_FLAGS, "lines": ["capabilities"]})
            return False
        except SE as exc:
            return "retired" in str(exc) and s6.cur is None
    guarded("g56_serve_memory_state_validated", validated)

    def first_snapshot_crash():
        # verification S1 of d6cbcf3: crash after a snapshot is written, before the journal restarts
        # (the first snapshot after a new path's empty one)
        p = tmp / "s_fs.json"
        s7 = serve.Server(64)
        s7.call(p, SERVE_FLAGS, ["fact a ra b", "example kk: a -> b"])
        s7._engine(s7.cur).save()
        s7.cur.jfh.close()
        s8 = serve.Server()
        r = s8.call(p, SERVE_FLAGS, ["what is a kk"])
        ok = r["replies"] == ["a kk b [no construction for kk]"] and "contained" in r["load"].get("journal_dropped", "")
        s8.close()
        # the same crash, but the journal holds a call the primary does not: refused, not dropped
        p2 = tmp / "s_fs2.json"
        s9 = serve.Server(64)
        s9.call(p2, SERVE_FLAGS, ["fact a ra b", "example kk: a -> b"])
        s9._engine(s9.cur).save()
        s9.call(p2, SERVE_FLAGS, ["fact c ra d"])  # journaled after the primary was written
        s9.cur.jfh.close()
        try:
            serve.Server().call(p2, SERVE_FLAGS, ["what is a kk"])
            refused = False
        except SE as exc:
            refused = "does not extend" in str(exc)
        return ok and refused
    guarded("g56_serve_first_snapshot_crash_recovers", first_snapshot_crash)

    def stale_journal():
        # verification Low 1 of d6cbcf3: deleting STATE and STATE.bak leaves a journal of deleted state
        p = tmp / "s_st.json"
        s10 = serve.Server(64)
        s10.call(p, SERVE_FLAGS, ["fact a ra b", "example kk: a -> b"])
        s10.cur.jfh.close()
        for q in (p, tmp / "s_st.json.bak"):
            if q.exists():
                q.unlink()
        try:
            serve.Server().call(p, SERVE_FLAGS, ["what is a kk"])
            return False
        except SE as exc:
            return "base snapshot" in str(exc)
    guarded("g56_serve_stale_journal_refused", stale_journal)

    def per_process_refuses():
        # verification Low 2 of d6cbcf3: a per-process engine does not read past an unclosed journal
        p = tmp / "s_pp.json"
        s11 = serve.Server(64)
        s11.call(p, SERVE_FLAGS, ["fact a ra b"])
        s11.cur.jfh.close()
        r = subprocess.run([sys.executable, "-m", "packetlm.engine", str(p), *SERVE_FLAGS, "what is a ra"],
                           capture_output=True, text=True)
        s12 = serve.Server()
        s12.call(p, SERVE_FLAGS, ["what is a ra"])
        s12.close()  # closed: the journal holds only its header again
        r2 = subprocess.run([sys.executable, "-m", "packetlm.engine", str(p), *SERVE_FLAGS, "what is a ra"],
                            capture_output=True, text=True)
        return r.returncode == 3 and "unclosed" in r.stdout and r2.returncode == 0
    guarded("g56_engine_refuses_unclosed_journal", per_process_refuses)
    return out

def g57_checks(tmp: Path) -> dict:
    """G57 (`--indexed`): memoized recall, relation-grouped rows, component classes and the
    evidence-gated re-ask give the non-indexed, always-re-ask engine's replies and state bytes
    (docs/G57.md). Each check is guarded: an exception fails that check by name."""
    from . import serve, g57_diff
    from .engine import Memo, StateError as SE, bits_for
    from collections import Counter
    import random as _r
    out = {}

    def guarded(name, fn):
        try:
            out[name] = bool(fn())
        except Exception as exc:  # noqa: BLE001
            out[name] = False
            out["_" + name + "_error"] = f"{type(exc).__name__}: {exc}"[:200]

    def differential():
        # targeted scenarios (one per way a cached answer can go stale) + random adversarial sessions
        r = g57_diff.run(n=40, seed=57)
        out["_differential"] = {k: v for k, v in r.items() if k != "mismatch"}
        return r["ok"] and r["gated_answers"] > 0 and r["readonly_calls"] > 0 and r["sessions"] == 40 + len(g57_diff.SCENARIOS)
    guarded("g57_differential_replies_and_state_equal", differential)

    def memo_recall():
        rng = _r.Random(5)
        ents, rels = [f"x{i}" for i in range(30)], ["p", "q", "r"]
        m, trip = Memo(), []
        for step in range(60):
            if trip and rng.random() < 0.3:
                trip.pop(rng.randrange(len(trip)))  # removal anywhere (not only appends)
            else:
                trip.append((rng.choice(ents), rng.choice(rels), rng.choice(ents)))
            m.sync(list(trip))
            for _ in range(5):
                s_, r_ = rng.choice(ents), rng.choice(rels)
                qi = bits_for(s_, 0) ^ bits_for(r_, 1)
                ref = Counter(t for t in trip if 2 * (qi & Memo.packet(t)).bit_count() - Memo.packet(t).bit_count() > 0)
                if (s_, r_) in m.recall and m.recall[(s_, r_)] != ref:
                    return False
                m.recall.setdefault((s_, r_), ref)
            if [p for p, _ in m.pkl] != [Memo.packet(t) for t in trip]:
                return False
        return len(m.recall) > 50
    guarded("g57_memo_recall_equals_reference", memo_recall)

    def stamps():
        m = Memo()
        m.sync([("a", "p", "b")])
        s1 = m.stamp["p"]
        m.sync([("a", "p", "b"), ("c", "q", "d")])  # unrelated relation: p's stamp unchanged
        same = m.stamp["p"] == s1
        m.sync([("c", "q", "d")])  # removal only
        return same and m.stamp["p"] > s1 and m.stamp["q"] < m.stamp["p"]
    guarded("g57_stamps_on_add_and_remove", stamps)

    def components():
        rng = _r.Random(9)
        ents = [f"y{i}" for i in range(25)]
        m, trip = Memo(), []
        for step in range(80):
            if trip and rng.random() < 0.25:
                trip.pop(rng.randrange(len(trip)))
            else:
                trip.append((rng.choice(ents), rng.choice(["p", "cap:z"]), rng.choice(ents)))
            m.sync(list(trip))
            adj = {}
            for s_, r_, o_ in trip:
                if not r_.startswith("cap:"):
                    adj.setdefault(s_, set()).add(o_)
                    adj.setdefault(o_, set()).add(s_)
            seeds, grown = set(rng.sample(ents + ["new1"], 2)), set(rng.sample(ents + ["new2"], 2))
            seen, todo = set(seeds), list(seeds)
            while todo:
                for y in adj.get(todo.pop(), ()):
                    if y not in seen:
                        seen.add(y)
                        todo.append(y)
            if m.region_hits(seeds, grown) != bool(grown & seen):
                return False
        return True
    guarded("g57_component_classes_equal_bfs", components)

    def by_rel_rows():
        eng = Engine(tmp / "g57r.json", indexed=True)
        ref = Engine(tmp / "g57r2.json")
        for t in [("a", "p", "b"), ("b", "q", "c"), ("c", "p", "d"), ("d", "q", "a"), ("a", "p", "c")]:
            eng.tell(*t)
            ref.tell(*t)
        return all(eng._rows(r) == ref._rows(r) for r in ("p", "q", "zz")) and eng._rows("p") != eng._rows("q")
    guarded("g57_by_rel_rows_equal", by_rel_rows)

    def fingerprint():
        srv = serve.Server()
        p = tmp / "g57fp.json"
        fl = g57_diff.BASE + ["--indexed"]
        srv.call(p, fl, ["fact s1 k t1", "fact t1 m u1", "fact u1 m w1"])
        srv.call(p, fl, ["example nm: s1 -> u1"])
        srv.call(p, fl, ["example far: s1 -> w1"])
        eng = srv._engine(srv.cur)
        eng.readonly_call = True
        fp0 = eng._answer_fp("s1", "far")
        # a dependency's record (not far's own) changes
        st = srv.cur.state
        st["capabilities"]["nm"]["express"] = "zzz"
        eng._cap_fp = {}
        dep = eng._answer_fp("s1", "far") != fp0
        st["capabilities"]["nm"]["express"] = None
        eng._cap_fp = {}
        back = eng._answer_fp("s1", "far") == fp0
        unknown = eng._answer_fp("nobody", "far")
        known = (unknown[:4] == fp0[:4]) and unknown[4] is False and fp0[4] is True
        lib0 = eng._answer_fp("s1", "far")[5]
        st["library"].append({"name": "zz_test"})  # any change to the construction library
        eng._cap_fp = {}
        lib = eng._answer_fp("s1", "far")[5] != lib0
        srv.cur = None
        return dep and back and known and lib
    guarded("g57_fingerprint_covers_dependencies_entity_library", fingerprint)

    def readonly():
        lines_ok = all(serve.readonly_line(x) for x in ["what is a b", "What is A b?", "ask a b", "  what is a b.  "])
        lines_no = not any(serve.readonly_line(x) for x in ["what is a", "fact a b c", "ask a", "what was a b",
                                                            "correct a b c", "example z: a -> b"])
        srv = serve.Server(check_readonly=True)
        p = tmp / "g57ro.json"
        fl = g57_diff.BASE + ["--indexed"]
        srv.call(p, fl, ["fact a p b"])
        j0 = Path(str(p) + ".journal").stat().st_size
        r = srv.call(p, fl, ["what is a p", "ask a p"])
        j1 = Path(str(p) + ".journal").stat().st_size
        mixed = srv.call(p, fl, ["what is a p", "fact c p d"])
        j2 = Path(str(p) + ".journal").stat().st_size
        # a read-only call that changed the state is caught by the check
        orig = Engine.turn
        Engine.turn = lambda self, line: (self.state.__setitem__("turn", self.state["turn"] + 99), orig(self, line))[1]
        try:
            srv.call(p, fl, ["what is a p"])
            caught = False
        except SE:
            caught = True
        finally:
            Engine.turn = orig
        return lines_ok and lines_no and r.get("readonly") and j1 == j0 and not mixed.get("readonly") and j2 > j1 \
            and caught
    guarded("g57_readonly_calls_detected_checked_not_journaled", readonly)
    return out


def verify_3e2783c_checks(tmp: Path) -> dict:
    """verify-3e2783c: M1 (dict order is observable, so every protocol keeps insertion order),
    N1b (base re-acquisition with no candidate caps qualified), Low 1 (lean load: exactly one JSON
    value after the prefix)."""
    from . import serve
    import hashlib
    from .engine import parse_cli, _read_doc, _lean_prefix, empty_state, StateError as SE
    out = {}
    script = [["fact a r b", "fact c r d", "example zz: a -> b", "example zz: c -> d",
               "example aa: a -> b", "example aa: c -> d"],  # zz taught before aa
              ["correct a r q"], ["capabilities", "show zz", "show aa"]]

    def per_process(path, flags_by_call):
        res = []
        for lines, flags in zip(script, flags_by_call):
            e = Engine.open(path, **parse_cli(flags)[0])
            res.append([e.turn(x) for x in lines])
            e.save()
        return res
    plain = per_process(tmp / "o_plain.json", [["--answers"]] * 3)
    lean = per_process(tmp / "o_lean.json", [["--answers", "--lean"]] * 3)
    mixed = per_process(tmp / "o_mixed.json", [["--answers", "--lean"], ["--answers"], ["--answers", "--lean"]])
    srv = serve.Server()
    served = [srv.call(tmp / "o_srv.json", ["--answers", "--lean"], lines)["replies"] for lines in script]
    srv.close()
    corr = plain[1][0]
    out["m1_insertion_order_exact"] = plain == lean == mixed == served \
        and "retired example zz" in corr and corr.index("retired example zz") < corr.index("retired example aa")
    # N1b: base mode (no --programs)
    e = Engine(tmp / "o_n1b.json", answers=True)
    for x in ["fact a ra b", "fact c ra d", "fact e ra f", "example kk: a -> b", "example kk: c -> d"]:
        e.turn(x)
    before = e.version("kk")["status"]
    e.turn("fact a ra x")  # ra(a) = {b, x}: no program is supported on kk's own example
    shown = e.turn("show kk")  # a non-fact line flushes the growth re-scan
    v = e.version("kk")
    out["n1b_base_no_candidate_caps_at_provisional"] = before == "qualified" and v["status"] == "provisional" \
        and v["history"][-1]["reason"] == "re-acquisition found no candidate" \
        and e.state["hypotheses"]["kk"].get("candidate") is None and "provisional" in shown
    # Low 1: a duplicate top-level "state" after the hashed text is refused by lean and non-lean loads
    one = empty_state()
    e1 = Engine(tmp / "o_two.json")
    e1.turn("fact a r b")
    e1.turn("fact c r d")
    two = e1.state
    body = (json.dumps(two) + ', "state": ' + json.dumps(one)).encode()
    raw = _lean_prefix(SCHEMA, hashlib.sha256(body).hexdigest()) + body + b"}"
    bad = tmp / "o_dup.json"
    bad.write_bytes(raw)
    refused = []
    for kw in ({"lean": True}, {}):
        try:
            Engine.open(bad, **kw)
            refused.append(False)
        except SE:
            refused.append(True)
    good = tmp / "o_good.json"
    e2 = Engine(good, lean=True)
    e2.turn("fact a r b")
    e2.save()
    out["low1_single_value_after_prefix"] = refused == [True, True] and _read_doc(raw)[1] is False \
        and _read_doc(good.read_bytes())[1] is True and Engine.open(good, lean=True).state["facts"] == e2.state["facts"]
    return out


def progs_max_guards():
    from . import programs
    return programs.MAX_GUARDS


def g57b_checks(tmp: Path) -> dict:
    """G57b (`--indexed --incremental`): the persistent fact index, the exact recall candidate
    filter, indexed relations()/_find, sparse prediction tables and change-scoped validation give
    the G57 engine's replies and state bytes; the periodic full validation catches what the scoped
    one cannot (docs/G57b.md). Each check is guarded: an exception fails that check by name."""
    from . import serve, g57_diff
    from .engine import Memo, StateError as SE, bits_for, _fresh_index, SMALL_PACKET
    from collections import Counter
    import random as _r
    out = {}

    def guarded(name, fn):
        try:
            out[name] = bool(fn())
        except Exception as exc:  # noqa: BLE001
            out[name] = False
            out["_" + name + "_error"] = f"{type(exc).__name__}: {exc}"[:200]

    B = g57_diff.BASE

    def differential(full_every):
        r = g57_diff.run(n=40, seed=571 + full_every, ref_flags=B + ["--indexed"], new_flags=B + ["--indexed", "--incremental"],
                         full_every=full_every)
        out[f"_differential_k{full_every}"] = {k: v for k, v in r.items() if k != "mismatch"}
        p = r.get("paths", {})
        return r["ok"] and r["sessions"] == 40 + len(g57_diff.SCENARIOS) and r["gated_answers"] > 0 and all(
            p.get(k, 0) > 0 for k in ("scoped_validations", "full_validations", "ix_rebuilds", "ix_appends", "candidate_queries"))
    guarded("g57b_differential_vs_g57_default_period", lambda: differential(64))
    guarded("g57b_differential_vs_g57_period_3", lambda: differential(3))

    def eng_pair(tag):
        a = Engine(tmp / f"g57b_{tag}_a.json", indexed=True, incremental=True, lean=True)
        b = Engine(tmp / f"g57b_{tag}_b.json", indexed=True, lean=True)
        return a, b

    def candidates(dense):
        # the candidate set contains every triple that passes the recall test. `dense`: codes are
        # drawn from 128 bit positions instead of 4096 (engine.bits_for patched for this check), so
        # packets below SMALL_PACKET bits and multi-bit code overlaps are common; otherwise real codes
        from . import engine as E
        real = E.bits_for
        if dense:
            def fake(tok, role, _c={}):
                k = (tok, role)
                if k not in _c:
                    rr = _r.Random(f"{tok}/{role}")
                    _c[k] = sum(1 << b for b in rr.sample(range(128), 16))
                return _c[k]
            E.bits_for = fake
        try:
            rng = _r.Random(57)
            a, _ = eng_pair("cand%d" % dense)
            ents, rels = [f"c{i}" for i in range(40)], ["p", "q", "r", "s", "t"]
            sizes = []
            for step in range(300):
                a.tell(rng.choice(ents), rng.choice(rels), rng.choice(ents))
                a._idx()
                ix = a.memo.ix
                for _ in range(3):
                    s_, r_ = rng.choice(ents + ["zz"]), rng.choice(rels + ["u"])
                    qi = E.bits_for(s_, 0) ^ E.bits_for(r_, 1)
                    full = {t for t in ix["triples"] if 2 * (qi & a.memo.packet_of(t)).bit_count() > a.memo.packet_of(t).bit_count()}
                    cand = a.memo.recall_candidates(s_, r_)
                    if not full <= cand:
                        return False
                    sizes.append(len(cand) / max(1, len(set(ix["triples"]))))
            small = len(ix["small"])
            out[f"_candidates_dense{int(dense)}"] = {"small": small, "mean_candidate_fraction": round(sum(sizes) / len(sizes), 4)}
            return (0 < small < len(set(ix["triples"])) if dense else small == 0) and all(a.memo.packet_of(t).bit_count() < SMALL_PACKET for t in ix["small"])
        finally:
            E.bits_for = real
    guarded("g57b_recall_candidates_superset_real_codes", lambda: candidates(False))
    guarded("g57b_recall_candidates_superset_dense_codes", lambda: candidates(True))

    def index_equal():
        # after random tells, supports and removals the persistent index equals a fresh build,
        # relations() and _find equal the unindexed engine's
        rng = _r.Random(58)
        a, b = eng_pair("ix")
        ents, rels = [f"d{i}" for i in range(15)], ["p", "q", "r"]
        for step in range(150):
            x, r_, y = rng.choice(ents), rng.choice(rels), rng.choice(ents)
            for e in (a, b):
                e.tell(x, r_, y)
            if rng.random() < 0.1:
                for e in (a, b):
                    e.retract(x, r_, y)
            a._idx()
            b._idx()
            if a.relations() != b.relations() or a.entities() != b.entities():
                return False
            for _ in range(3):
                q = (rng.choice(ents), rng.choice(rels), rng.choice(ents))
                for qq in (q, q[:2]):
                    if [f["id"] for f in a._find(*qq)] != [f["id"] for f in b._find(*qq)]:
                        return False
            if a._ix_live():
                a.memo.ix_check(a.state, _fresh_index(a.state["facts"]))
        return a.memo.counts["ix_appends"] > 0 and a.state["facts"] == b.state["facts"]
    guarded("g57b_index_relations_find_equal_reference", index_equal)

    def guard_catches_corruption():
        # a corrupted fact the calls do not touch passes the change-scoped validation (that is the
        # scope), and the registered periodic full validation raises; the call is not kept, and the
        # reloaded state (snapshot + journal) is the uncorrupted one
        p = tmp / "g57b_guard.json"
        fl = B + ["--indexed", "--incremental"]
        srv = serve.Server(snapshot_every=1000, full_every=4)
        srv.handle({"op": "call", "state": str(p), "flags": fl, "lines": ["fact a p b", "fact b p c"]})  # full (first)
        srv.cur.state["facts"][0]["supports"] = []  # injected corruption of an untouched fact
        passed = 0
        try:
            for k in range(10):
                srv.handle({"op": "call", "state": str(p), "flags": fl, "lines": [f"fact g{k} q h{k}"]})
                passed += 1
        except SE:
            pass
        caught_at_period = passed == 3  # calls 2, 3, 4 scoped; call 5 is the full validation
        r = srv.handle({"op": "call", "state": str(p), "flags": fl, "lines": ["what is a p"]})
        st = srv.cur.state
        srv.close()
        clean = serve.Server(snapshot_every=1000)  # the same kept calls, never corrupted (G57 engine)
        q = tmp / "g57b_guard_clean.json"
        for lines in [["fact a p b", "fact b p c"]] + [[f"fact g{k} q h{k}"] for k in range(3)]:
            clean.handle({"op": "call", "state": str(q), "flags": B + ["--indexed"], "lines": lines})
        r2 = clean.handle({"op": "call", "state": str(q), "flags": B + ["--indexed"], "lines": ["what is a p"]})
        same = json.dumps(clean.cur.state, sort_keys=True) == json.dumps(st, sort_keys=True)
        clean.close()
        return caught_at_period and same and r["replies"] == r2["replies"] and st["facts"][0]["supports"] != []
    guarded("g57b_period_guard_catches_untouched_corruption", guard_catches_corruption)

    def ix_check_catches():
        # a corrupted persistent index (not the facts) is caught by the guard's index check
        p = tmp / "g57b_ixguard.json"
        fl = B + ["--indexed", "--incremental"]
        srv = serve.Server(snapshot_every=1000, full_every=3)
        srv.handle({"op": "call", "state": str(p), "flags": fl, "lines": ["fact a p b", "fact b p c", "what is a p"]})
        srv.cur.memo.ix["out"]["a"] = {"zz"}
        try:
            for k in range(5):
                srv.handle({"op": "call", "state": str(p), "flags": fl, "lines": [f"fact g{k} q h{k}"]})
            return False
        except SE as exc:
            return "incremental fact index diverged" in str(exc) and srv.cur is None
    guarded("g57b_period_guard_catches_index_corruption", ix_check_catches)

    def scoped_rejects_touched():
        # a call whose own (touched) fact is broken fails the scoped validation itself
        from .engine import _valid_scoped
        a, _ = eng_pair("sc")
        a.tell("a", "p", "b")
        a._idx()
        a.memo.scope = {"ok": True, "touched": []}
        a.tell("b", "p", "c")
        t = a.memo.scope["touched"]
        good = _valid_scoped(a.state, t, a.memo.ix["byid"])
        t[0]["supports"] = []
        return good and len(t) == 1 and not _valid_scoped(a.state, t, a.memo.ix["byid"])
    guarded("g57b_scoped_validation_checks_touched", scoped_rejects_touched)

    def dom_cache_content():
        # Info 2 of verify-35bda6b: replaced domain lists (whose addresses CPython may reuse) and
        # in-place edits never return a stale domain set
        e = Engine(tmp / "g57b_dom.json")
        rng = _r.Random(3)
        ver = {"v": 1}
        for k in range(200):
            if k % 3 == 2:
                ver["domain"].append(f"z{k}")  # in place
            else:
                ver["domain"] = [f"e{rng.randrange(50)}" for _ in range(rng.randrange(1, 5))]  # replaced
            if e._dom_set("cap", ver) != set(ver["domain"]):
                return False
        return True
    guarded("g57b_domain_cache_keyed_on_content", dom_cache_content)
    return out


def run() -> dict:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        sections = {}
        for sec, fn in [("memory", memory_checks), ("constructions", construction_checks),
                        ("acquisition", acquisition_checks), ("discovery", discovery_checks),
                        ("persistence", persistence_checks), ("fresh_process", fresh_process_checks),
                        ("migration", migration_checks), ("retention", retention_checks), ("audit", audit_checks),
                        ("programs", program_checks), ("px", px_checks), ("g49", g49_checks),
                        ("serve", serve_checks), ("verify_3e2783c", verify_3e2783c_checks),
                        ("g57", g57_checks), ("g57b", g57b_checks)]:
            # a section that raises is a failed check (named), not a crash that hides the other sections
            try:
                sections[sec] = fn(tmp)  # no pseudo-check when it completes (verification L3 of 82dd0a2)
            except Exception as exc:  # noqa: BLE001
                sections[sec] = {"completed": False, "_error": f"{type(exc).__name__}: {exc}"[:300]}
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
