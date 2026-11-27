"""G44 test. One engine, checked as separate claims.

Every check can fail. Controls are named. Not a mind.
"""

from __future__ import annotations
import copy
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path
from .engine import Engine, StateError, judge, validate, _checksum
from .field import add as field_add, ask as field_ask

ROOT = Path(__file__).resolve().parent.parent


def family(eng):
    for i in range(6):
        eng.tell(f"p{i}", "parent", f"p{i+1}", source="test")
    eng.tell("p0", "friend", "p2", source="test")
    eng.tell("p1", "friend", "p5", source="test")
    eng.tell("rex", "owns", "map", source="test")


def memory_checks(tmp) -> dict:
    eng = Engine.open(tmp / "mem.json")
    print(eng.turn("construct owns: ada owns box = ada box; ned owns key = ned key"))
    rec = eng.turn("rex owns map")
    told = eng._find("rex", "owns", "map")
    family(eng)
    eng.observe("grand", "p0", "p2")
    eng.observe("grand", "p1", "p3")
    eng.acquire("grand")
    d = eng.derive("grand", "p0")
    derived = eng._find("p0", "grand", "p2")
    corr = eng.correct("p1", "parent", "p9")
    after_corr = eng.ask("p0", "grand")
    eng.tell("sam", "owns", "key")
    eng.tell("sam", "owns", "cup")
    amb = eng.ask("sam", "owns")
    eng.correct("sam", "owns", "key")
    amb_fixed = eng.ask("sam", "owns")
    gone = eng.retract("rex", "owns", "map")
    return {
        "provenance_told": rec == "recorded rex owns map" and told and told[0]["source"] == "sentence" and told[0]["turn"] > 0,
        "derived_provenance": d.get("status") == "derived" and derived
            and derived[0]["premises"] == ["p0:parent:p1", "p1:parent:p2"] and derived[0]["program"] == "grand",
        "correction_drops_derived": "p0:grand:p2" in corr["removed"] and after_corr["status"] == "unknown"
            and eng.ask("p2", "parent")["value"] == "p3",
        "correction_logged": any(e["id"] == "p0:grand:p2" and e["reason"].startswith("correct") for e in eng.state["log"]),
        "ambiguity_abstains": amb == {"status": "ambiguous", "value": None, "candidates": ["cup", "key"]},
        "ambiguity_resolved_by_correction": amb_fixed == {"status": "known", "value": "key"},
        "retraction": gone == ["rex:owns:map"] and eng.ask("rex", "owns")["status"] == "unknown"
            and any(e["reason"].startswith("retract") for e in eng.state["log"]),
    }


def construction_checks(tmp) -> dict:
    eng = Engine.open(tmp / "con.json")
    a = eng.turn("construct owns: ada owns box = ada box; ned owns key = ned key")
    b = eng.turn("construct vek: box vek ada = ada box; key vek ned = ned key")
    clash = eng.turn("construct holds: ada owns box = ada box; ned owns key = ned key")
    rec = eng.turn("map vek rex")
    return {
        "induced_orders": a == "construction owns sro" and b == "construction vek ors",
        "osv_read": rec == "recorded rex vek map" and eng.ask("rex", "vek")["value"] == "map",
        "speak_roundtrip": eng.speak(("rex", "vek", "map")) == "map vek rex" and eng.read("map vek rex") == ("rex", "vek", "map"),
        "unknown_word_abstains": eng.turn("rex holds map") == "unparsed",
        "word_clash_rejected": clash == "construction rejected",
    }


def acquisition_checks(tmp) -> dict:
    eng = Engine.open(tmp / "acq.json")
    family(eng)
    eng.observe("grand", "p0", "p2")
    first = eng.acquire("grand")
    eng.observe("grand", "p1", "p3")
    second = eng.acquire("grand")
    eng.observe("great", "p0", "p3")
    eng.observe("great", "p1", "p4")
    no_lib_state = copy.deepcopy(eng.state)
    control = eng.acquire("great", max_len=2, use_library=False)
    eng.state["pending"].pop("great", None)
    with_lib = eng.acquire("great", max_len=2, use_library=True)
    deep = Engine(tmp / "deep.json", no_lib_state, {})
    deep_res = deep.acquire("great", max_len=3, use_library=False)
    # binary execution vs step-by-step geometric walk, every capability and subject
    compared = nonempty = agree = 0
    for name, cap in eng.state["capabilities"].items():
        for s in eng.entities():
            bits = eng.execute(cap["seq"], s)
            walk, _ = eng.walk(cap["seq"], s)
            compared += 1
            nonempty += bool(bits)
            agree += (bits == {walk}) if walk is not None else (len(bits) != 1)
    return {
        "one_observation_stays_pending": first["result"] == "pending" and len(first["live"]) == 2,
        "accumulated_acquires": second.get("seq") == ["parent", "parent"],
        "library_control_finds_nothing": control["result"] == "none",
        "library_reuse": with_lib.get("result") == "acquired"
            and eng.state["capabilities"]["great"]["base"] == ["parent"] * 3,
        "library_matches_deep_search": deep_res.get("seq") == ["parent", "parent", "parent"],
        "binary_equals_walk": compared > 0 and agree == compared and nonempty >= 6,
        "_binary_measure": {"compared": compared, "nonempty": nonempty, "agree": agree},
    }


def build_world(n, target):
    triples = []
    for i in range(n):
        triples += [("x", f"r{i}", f"m{i}"), (f"m{i}", f"r{i}", "z")]
        for bit in range(max(1, (n - 1).bit_length())):
            hop = f"h{i}_{bit}"
            triples += [(f"q{bit}", f"r{i}", hop), (hop, f"r{i}", "yes" if (i >> bit) & 1 else "no")]
    triples += [("x", "rg", "mg"), ("mg", "rg", "z")]  # gap: no q facts, so no prediction
    return triples


def discovery_checks(tmp) -> dict:
    results = []
    for seed in (1, 7, 13, 21, 42):
        target = random.Random(seed).randrange(8)
        triples = build_world(8, target)
        eng = Engine.open(tmp / f"disc{seed}.json")
        for t in triples:
            eng.tell(*t, source="world")
        env, objs = [], sorted({t[2] for t in triples})
        for t in triples:
            field_add(env, *t)
        hidden = f"r{target}"

        def oracle(subject, env=env, objs=objs, hidden=hidden):
            mid = field_ask(env, subject, hidden, objs)
            return field_ask(env, mid, hidden, objs) if mid else None

        eng.observe("out", "x", "z")
        start = eng.acquire("out")
        got = eng.discover("out", oracle)
        results.append({
            "seed": seed, "target": target, "live_at_start": len(start["live"]),
            "asks": len(got["asked"]), "seq": got.get("seq"),
            "ok": got.get("seq") == [hidden, hidden],
            "gap_undetermined": ["rg", "rg"] in got.get("undetermined", []),
            "start_uniform": all(h["status"] == "supported" and h["support"] == 1 for h in start["live"]),
        })
    # control: an oracle that never knows eliminates nothing and adopts nothing
    eng = Engine.open(tmp / "silent.json")
    for t in build_world(8, 0):
        eng.tell(*t, source="world")
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
        "silent_oracle_adopts_nothing": silent["result"] == "pending" and len(silent["live"]) == 9,
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
    doc["state"]["facts"][0]["o"] = "zzz"
    path.write_text(json.dumps(doc))
    r_sum = Engine.open(path)
    doc["checksum"] = _checksum(doc["state"])
    path.write_text(json.dumps(doc))
    r_bind = Engine.open(path)
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
        "truncated_recovers": r_trunc.report.get("loaded") == "backup" and len(r_trunc.state["facts"]) == 9,
        "both_corrupt_raises": both == "raised",
    }


def cli(state, *lines) -> dict:
    out = subprocess.run([sys.executable, "-m", "packetlm.engine", str(state), *lines],
                         cwd=ROOT, capture_output=True, text=True, timeout=60)
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
    good = Path(str(s) + ".bak").read_text()
    s.write_text(s.read_text()[:-40])
    p6 = cli(s, "what is rex owns")
    return {
        "p1_new_state": p1.get("load") == {"loaded": "new"} and p1["replies"][2] == "recorded rex owns map",
        "p2_reads_p1": p2.get("load") == {"loaded": "primary"} and p2["replies"][0] == "rex owns map"
            and p2["replies"][2] == "acquired grand parent+parent",
        "p3_uses_capability": p3.get("replies") == ["ann grand cy", "derived ann:grand:cy"],
        "p4_correction_drops_derived": p4.get("replies", [""])[0] == "corrected bea parent eve; removed 2",
        "p5_sees_corrections": p5.get("replies") == ["rex owns key", "ann grand eve", "bea parent eve"],
        "p6_recovery_reported": p6.get("load", {}).get("recovered") is True and p6["replies"] == ["rex owns key"],
        "_replies": {"p1": p1, "p2": p2, "p3": p3, "p4": p4, "p5": p5, "p6": p6, "bak_len": len(good)},
    }


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
        }
    checks = {f"{sec}.{k}": bool(v) for sec, c in sections.items() for k, v in c.items() if not k.startswith("_")}
    measures = {f"{sec}.{k[1:]}": v for sec, c in sections.items() for k, v in c.items() if k.startswith("_")}
    failed = [k for k, v in checks.items() if not v]
    receipt = {"checks": checks, "measures": measures, "count": len(checks), "failed": failed,
               "claim": "one engine; symbolic and bitwise; not a mind"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/g44_receipt.json").write_text(json.dumps(receipt, indent=2, default=list))
    print(json.dumps(receipt, indent=2, default=list))
    if failed:
        raise SystemExit(1)
    return receipt


if __name__ == "__main__":
    run()
