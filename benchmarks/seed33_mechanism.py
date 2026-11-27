"""Reproduce the G46 seed-33 threshold-6 failure analysis (docs/G46_SEED33.md).
Needs artifacts/g46/seed33/C.json from a G46 run (v4 engine). Read-only on that state.
Run: python3 benchmarks/seed33_mechanism.py
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT))
import g46  # noqa: E402
from packetlm.engine import Engine, judge  # noqa: E402

raw = json.loads((ROOT / "artifacts/g46/g46_raw.json").read_text())
task = [t for t in raw["33:C"]["tasks"] if not t["acquired"]][0]
d = Path(tempfile.mkdtemp())
shutil.copy(ROOT / "artifacts/g46/seed33/C.json", d / "C.json")
eng = Engine.open(d / "C.json")
rec = eng.state["hypotheses"][task["name"]]
cands = [h["seq"] for h in rec["live"] if h["support"] >= 1]
fams = g46.world(33)
fam = fams[task["family"]]
hidden = fam["tasks"][task["task"]]["hidden"]
sealed = g46.sealed_tokens(fams)
out = {"task": {k: task[k] for k in ("family", "task", "shape", "name", "status", "evidence", "asked")},
       "unanswered": rec.get("unanswered"), "hidden": hidden,
       "candidates": [{"seq": c, "base": eng.expand(c), "is_hidden": eng.expand(c) == hidden} for c in cands],
       "differences": []}
for s in sorted({t[0] for t in fam["triples"]}):
    preds = [eng.execute(c, s) for c in cands]
    if len({tuple(sorted(p or ())) for p in preds}) > 1:
        tv = g46.truth(fam["triples"], hidden, s)
        single = [next(iter(p)) if p and len(p) == 1 else None for p in preds]
        out["differences"].append({"subject": s, "predictions": [sorted(p or ()) for p in preds], "truth": tv,
                                   "sealed": s in sealed,
                                   "single_value_judgement": [judge(v, tv[1]) if tv[0] == "val" else None for v in single]})
out["answerable_discriminators"] = [x["subject"] for x in out["differences"]
                                    if x["truth"][0] == "val" and not x["sealed"] and "contradicted" in x["single_value_judgement"]]
print(json.dumps(out, indent=1))
