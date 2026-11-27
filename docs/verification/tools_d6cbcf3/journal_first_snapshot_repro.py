"""Verifier repro (d6cbcf3): a crash inside the FIRST snapshot of a new path (primary written,
journal not yet restarted) leaves a journal with base null beside a valid primary and no backup;
reopening fails ("journal does not extend the loaded snapshot"), although the primary already
contains every journaled call. Second probe: deleting STATE and STATE.bak (a reset) while a
base-null journal remains brings the old state back. Run from the repo root."""
import os, sys, tempfile
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")))
from pathlib import Path
from packetlm.serve import Server
from packetlm.engine import StateError
F = ["--answers", "--bounded", "--lean"]
d = Path(tempfile.mkdtemp()); st = d / "s.json"
s = Server(64); s.call(st, F, ["fact a ra b", "example kk: a -> b"])
o = s.cur; s._engine(o).save(); o.jfh.close()          # snapshot written; crash before _journal_start
print("files:", sorted(p.name for p in d.iterdir()), "| journal head:", open(d / "s.json.journal").readline().strip())
try:
    print("reopen:", Server().call(st, F, ["what is a kk"])["replies"])
except StateError as x:
    print("reopen FAILS:", x)
d = Path(tempfile.mkdtemp()); st = d / "s.json"
s = Server(64); s.call(st, F, ["fact a ra b", "example kk: a -> b"]); s.cur.jfh.close()   # crash before any snapshot
for p in (st, d / "s.json.bak"):
    if p.exists():
        p.unlink()
print("after deleting s.json and s.json.bak:", sorted(p.name for p in d.iterdir()))
print("new call on the reset path:", Server().call(st, F, ["what is a kk"])["replies"], "(a fresh per-process engine: unknown)")
