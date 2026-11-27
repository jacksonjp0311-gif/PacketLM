"""Chat on the canonical engine (G45).

Every line, scripted or typed, goes through Engine.turn. The engine owns
facts, constructions, examples, procedures and persistence. The scripted run
starts from an empty state, teaches through the interface, then plays
data/dialogue.txt. The old chat-local discover/acquire/turn were removed;
the pre-migration file is kept at docs/evidence/chat_pre_g45.py.txt.
Controlled language, not open natural language. Not a mind.
"""

from __future__ import annotations
import json
import sys
from pathlib import Path
from .engine import Engine, choose, express  # noqa: F401  (re-exported for older callers)

STATE = Path("data/chat_state.json")

SETUP = [
    "construct isa: mira isa dax = mira dax; sam isa cat = sam cat",
    "construct owns: ada owns box = ada box; ned owns key = ned key",
    "construct hastail: mira hastail green = mira green; sam hastail blue = sam blue",
    "construct at: mira at dock = mira dock; sam at bay = sam bay",
    "question owns: what does ada own = ada; what does ned own = ned",
    "fact mira isa dax",
    "fact dax tail green",
    "fact mira in lab",
    "fact lab at dock",
    "example tail: mira -> green",
    "express tail as hastail",
    "example location: mira -> dock",
    "express location as at",
]


def _requalified_scope() -> bool:
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        e = Engine(Path(d) / "scope.json")
        for line in SETUP:
            e.turn(line)
        before = e.turn("fact orion isa dax") and e.turn("what is orion tail")
        e.turn("requalify tail")
        return before == "orion hastail green [provisional]" and e.turn("what is orion tail") == "orion hastail green"


def run() -> dict:
    if STATE.exists():
        STATE.unlink()  # the scripted run is reproducible: it always starts empty
    eng = Engine(STATE)
    setup = [eng.turn(line) for line in SETUP]
    lines = [ln for ln in Path("data/dialogue.txt").read_text().splitlines() if ln.strip()]
    replies = [eng.turn(line) for line in lines]
    eng.save()
    loaded = Engine.open(STATE)
    checks = {
        "two": list(loaded.state["capabilities"]) == ["tail", "location"],
        # adapts to the corrected premise; since G46-prep the only example was retired, so the
        # answer is marked provisional (audit 283f526 item 4; ledger 2026-11-26)
        "tail": loaded.turn("what is orion tail") == "orion hastail red [provisional]",
        "location": loaded.turn("what is mira location") == "mira at dock",
        "age_abstains": loaded.turn("what is orion age") == "unknown",
        # orion was told after `tail` was qualified: the answer generalizes, but outside the domain
        # the scan decided it is provisional (verification M2 of b2bb9b8); `requalify` widens the scope
        "generic": replies[7] == "orion hastail green [provisional]",
        "generic_requalified": _requalified_scope(),
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {**checks, "setup": setup, "replies": replies, "load": loaded.report, "failed": failed,
               "claim": "operators acquired through the engine interface; the asked word picks"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/chat_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt


def interactive(path=STATE):
    eng = Engine.open(path)
    print(f"[{eng.report['loaded']}] controlled language; 'quit' to leave")
    while True:
        try:
            line = input("> ")
        except EOFError:
            break
        if line.strip() in {"quit", "exit"}:
            break
        print(eng.turn(line))
        eng.save()


if __name__ == "__main__":
    if "--interactive" in sys.argv:
        interactive()
    else:
        run()
