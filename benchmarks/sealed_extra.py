"""Write the sealed tokens of every registered curriculum besides G46 (verification L3).
teach.py refuses any token in benchmarks/sealed_tokens*.json.
Run: python3 benchmarks/sealed_extra.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT))
import g46  # noqa: E402
import g46u  # noqa: E402

toks = set()
for s in (11, 22, 33):
    toks |= g46.sealed_tokens(g46u.world_unrelated(s))
(ROOT / "benchmarks/sealed_tokens_g46u.json").write_text(json.dumps(sorted(toks)) + "\n")
print("g46u", len(toks))
# G47-AR new seeds (verification L2 of 82dd0a2)
toks = set()
for s in (44, 55):
    toks |= g46.sealed_tokens(g46.world(s))
(ROOT / "benchmarks/sealed_tokens_g47ar.json").write_text(json.dumps(sorted(toks)) + "\n")
print("g47ar", len(toks))
# G48-family items: every evaluated item of every committed registered run (generated at run time,
# so this is refreshed after each run; teaching sessions are refused these tokens from then on)
toks = set()
for raw in sorted((ROOT / "docs/evidence").glob("g48*/g48*_raw.json")):
    for v in json.loads(raw.read_text()).values():
        for t in v["tasks"]:
            toks |= {r["s"] for r in t["rows"]}
for raw in sorted((ROOT / "docs/evidence").glob("px*/px*_raw.json")):  # PX part A uses G48 worlds
    for v in json.loads(raw.read_text())["A"].values():
        for t in v["tasks"]:
            toks |= {r["s"] for r in t["rows"]}
(ROOT / "benchmarks/sealed_tokens_g48.json").write_text(json.dumps(sorted(toks)) + "\n")
print("g48", len(toks))
# G49 (docs/G49.md): evaluated rows, window rows and abstention items (verification L4 of e944840)
toks = set()
for raw in sorted((ROOT / "docs/evidence").glob("g49*/g49*_raw.json")):
    for v in json.loads(raw.read_text()).values():
        for t in v["tasks"]:
            toks |= {r["s"] for r in t["rows"]} | {r["s"] for r in (t.get("window_rows") or [])}
            toks |= set(t.get("abstain", {}).get("items", []))
(ROOT / "benchmarks/sealed_tokens_g49.json").write_text(json.dumps(sorted(toks)) + "\n")
print("g49", len(toks))
# G50 (A: G49 harness; B: G46 worlds 61-67), G51 (G46 71-77, G46-U 81-87), G52 (G49 harness)
toks = set()
for s in list(range(61, 68)) + list(range(71, 78)):
    toks |= g46.sealed_tokens(g46.world(s))
for s in range(81, 88):
    toks |= g46.sealed_tokens(g46u.world_unrelated(s))
for raw in [ROOT / "docs/evidence/g50/g50a_raw.json", ROOT / "docs/evidence/g52/g52_raw.json"]:
    for v in json.loads(raw.read_text()).values():
        for t in v["tasks"]:
            toks |= {r["s"] for r in t["rows"]} | {r["s"] for r in (t.get("window_rows") or [])}
            toks |= set(t.get("abstain", {}).get("items", []))
(ROOT / "benchmarks/sealed_tokens_g50_g52.json").write_text(json.dumps(sorted(toks)) + "\n")
print("g50-g52", len(toks))
# G53 (G46 worlds 121-127, G46-U worlds 131-137; dev seeds 951-954 are also sealed)
toks = set()
for s in list(range(121, 128)) + [951, 952]:
    toks |= g46.sealed_tokens(g46.world(s))
for s in list(range(131, 138)) + [953, 954]:
    toks |= g46.sealed_tokens(g46u.world_unrelated(s))
(ROOT / "benchmarks/sealed_tokens_g53.json").write_text(json.dumps(sorted(toks)) + "\n")
print("g53", len(toks))
