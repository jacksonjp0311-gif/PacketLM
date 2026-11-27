"""Teaching sessions for the persistent trained state.

`python -m packetlm.teach data/teaching/NNN_name.txt` runs one session file
through Engine.turn on data/trained/state.json, in this one fresh process.
Lines starting with `expect ` are retention probes:
    expect <question> => <exact reply>
They accumulate in data/trained/probes.json. After each session every probe
so far is re-asked, so retention of older sessions is measured.
Sessions are logged to data/trained/sessions.jsonl and docs/RESEARCH_LEDGER.md.
A line `options operators deepen=3` sets engine options for the session (recorded).
Sealed evaluation tokens (benchmarks/sealed_tokens.json) are refused.
"""

from __future__ import annotations
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from .engine import Engine

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data/trained/state.json"
PROBES = ROOT / "data/trained/probes.json"
LOG = ROOT / "data/trained/sessions.jsonl"
SEALED = ROOT / "benchmarks/sealed_tokens.json"
LEDGER = ROOT / "docs/RESEARCH_LEDGER.md"


def source_hash() -> str:
    h = hashlib.sha256()
    for p in sorted((ROOT / "packetlm").glob("*.py")):
        h.update(p.name.encode() + p.read_bytes())
    return h.hexdigest()


def inventory(eng) -> dict:
    caps = eng.state["capabilities"]
    status = {}
    for c in caps.values():
        if c["current"]:
            s = c["versions"][c["current"] - 1]["status"]
            status[s] = status.get(s, 0) + 1
    return {"facts": len(eng.state["facts"]), "relations": len(eng.relations()), "entities": len(eng.entities()),
            "constructions": len(eng.state["library"]), "lexicon": len(eng.state["lexicon"]),
            "capabilities": len(caps), "capability_status": status,
            "observations": sum(len(v) for v in eng.state["observations"].values()),
            "retired": sum(len(v) for v in eng.state["retired"].values())}


def run(path) -> dict:
    path = Path(path)
    text = path.read_text()
    sealed = set(json.loads(SEALED.read_text())) if SEALED.exists() else set()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    leaked = sorted({t for ln in lines for t in ln.lower().replace(":", " ").split() if t in sealed})
    if leaked:
        raise SystemExit(f"refused: session uses sealed evaluation tokens {leaked[:5]}")
    opts = {}
    for ln in [x for x in lines if x.startswith("options ")]:  # e.g. `options operators deepen=3`
        for tok in ln.split()[1:]:
            k, _, v = tok.partition("=")
            opts[k] = int(v) if v.isdigit() else True
    lines = [x for x in lines if not x.startswith("options ")]
    t0 = time.process_time()
    eng = Engine.open(STATE, **opts)
    before = inventory(eng)
    probes = json.loads(PROBES.read_text()) if PROBES.exists() else []
    new_probes, replies = [], []
    for ln in lines:
        if ln.startswith("expect "):
            q, want = [x.strip() for x in ln[7:].split("=>", 1)]
            new_probes.append({"q": q, "want": want, "session": path.name})
            continue
        replies.append({"line": ln, "reply": eng.turn(ln)})
    for p in probes:  # a later expectation for the same question supersedes the old one (intended change)
        if any(n["q"] == p["q"] for n in new_probes) and not p.get("superseded_by"):
            p["superseded_by"] = path.name
    live = [p for p in probes if not p.get("superseded_by")]
    old_pass = [eng.turn(p["q"]) == p["want"] for p in live]
    new_pass = [eng.turn(p["q"]) == p["want"] for p in new_probes]
    eng.save()
    after = inventory(eng)
    probes += new_probes
    PROBES.write_text(json.dumps(probes, indent=1))
    rec = {"session": path.name, "file_sha256": hashlib.sha256(text.encode()).hexdigest(),
           "engine_sha256": source_hash(), "time": datetime.now().astimezone().isoformat(timespec="seconds"),
           "load": eng.report, "options": opts, "before": before, "after": after, "lines": len(replies),
           "retention_old": f"{sum(old_pass)}/{len(old_pass)}", "new_probes": f"{sum(new_pass)}/{len(new_pass)}",
           "superseded_probes": sum(1 for p in probes if p.get("superseded_by") == path.name),
           "failed_probes": [p["q"] for p, ok in zip(live + new_probes, old_pass + new_pass) if not ok],
           "cpu_s": round(time.process_time() - t0, 3), "state_bytes": STATE.stat().st_size, "stats": eng.stats}
    with LOG.open("a") as fh:
        fh.write(json.dumps(rec) + "\n")
    (ROOT / "data/trained/replies").mkdir(exist_ok=True)
    (ROOT / "data/trained/replies" / (path.stem + ".json")).write_text(json.dumps(replies, indent=1))
    with LEDGER.open("a") as fh:
        fh.write(f"\n- teaching `{path.name}` {rec['time']}: facts {before['facts']}→{after['facts']}, "
                 f"capabilities {before['capabilities']}→{after['capabilities']} {after['capability_status']}, "
                 f"constructions {before['constructions']}→{after['constructions']}; retention {rec['retention_old']}, "
                 f"new probes {rec['new_probes']}; cpu {rec['cpu_s']}s; engine {rec['engine_sha256'][:12]}\n")
    print(json.dumps(rec, indent=1))
    return rec


if __name__ == "__main__":
    for p in sys.argv[1:]:
        run(p)
