"""Reconstructs the G48 dev-3 source (receipt source_sha256 f7932ad5...) from git, to show what
changed between dev 3 and the registered engine 6a61c9d (verification L4 of 82dd0a2).
dev 3 = packetlm/*.py at 8fa5c7b, except g44_test.py and mutations.py at 6d01612 (the G48 checks
and mutations were added after dev 3) and engine.py with the `unanswered` variable rename undone
(behaviour-neutral; made so the `unanswered_lost` mutation site stays unique).
Run from the repo root: python3 docs/evidence/g48/dev/reconstruct_hash.py  -> f7932ad5...
"""
import hashlib
import subprocess
import tempfile
from pathlib import Path


def show(rev, f):
    return subprocess.run(["git", "show", f"{rev}:{f}"], capture_output=True, check=True).stdout


with tempfile.TemporaryDirectory() as d:
    pk = Path(d)
    names = subprocess.run(["git", "ls-tree", "--name-only", "8fa5c7b", "packetlm/"], capture_output=True,
                           text=True, check=True).stdout.split()
    for f in names:
        if f.endswith(".py"):
            rev = "6d01612" if f.endswith(("g44_test.py", "mutations.py")) else "8fa5c7b"
            (pk / Path(f).name).write_bytes(show(rev, f))
    e = pk / "engine.py"
    s = e.read_text()
    new = ('        unanswered = self.state["hypotheses"].get(name, {}).get("unanswered")\n        if unanswered:\n'
           '            record["unanswered"] = unanswered  # questions the teacher could not answer stay recorded')
    old = ('        prior = self.state["hypotheses"].get(name, {})\n        if prior.get("unanswered"):\n'
           '            record["unanswered"] = prior["unanswered"]')
    assert s.count(new) == 1
    e.write_text(s.replace(new, old))
    h = hashlib.sha256()
    for q in sorted(pk.glob("*.py")):
        h.update(q.name.encode() + q.read_bytes())
    print(h.hexdigest())
