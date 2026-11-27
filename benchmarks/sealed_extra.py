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
print(len(toks))
