"""G56: the long-lived engine protocol (docs/G56.md).

One process serves many calls. A call has the same meaning as one `python -m packetlm.engine STATE
[flags] line ...` process: the lines are turned by a fresh `Engine` object over the state, then the
call's state is made durable before the reply is returned. What changes is only where the state
lives between calls and how it is made durable:

- The state of the open STATE path stays in memory. A call on another path, or with other flags,
  first closes the open one (snapshot) and opens the new one from disk exactly as the per-process
  engine does (`Engine.open`, then journal recovery). A path with no file starts from
  `empty_state()`: B tasks start from a fresh in-memory empty state, never a reused one.
- After the lines, `Engine.finish` runs (growth re-scans, archiving), then the resulting state is
  validated in memory by the same validator the per-process engine applies before every save
  (`validate_lean`, full checks; only the checksum is not computed, because no bytes are written).
- Durability is a journal `STATE.journal`: one fsync'd record per call (flags, lines, sha256 of the
  replies) after a header naming the snapshot it extends. Every SNAPSHOT_EVERY calls, and on close,
  the state is written by the ordinary `save` (lean: validated, backup kept, atomic, fsync) and the
  journal restarts on the new snapshot.
- Recovery (`open_path`): load the snapshot as the per-process engine does, then replay the journal
  call by call through fresh `Engine` objects; every replayed call must reproduce its recorded
  reply hash, or the load fails with StateError (no silent reconstruction). A journal whose header
  names the backup's checksum (crash after the snapshot write, before the journal restart) is
  already contained in the primary and is dropped; any other mismatch is an error.

Accounting: each call reports `cpu_total_s` = CPU of this process since the end of the previous
charged request (the first call carries interpreter start-up and imports), so the per-call values
sum to the process's whole CPU except `inspect` requests, which are measurement only and reported
separately (`inspect_cpu_s`).

Protocol: one JSON request per stdin line, one JSON response per stdout line.
  {"op": "call", "state": PATH, "flags": [...], "lines": [...]}
  {"op": "inspect", "state": PATH}   -> writes PATH.inspect (the state document); uncharged
  {"op": "close"}                    -> snapshots the open path; charged
Run: python -m packetlm.serve
"""
from __future__ import annotations
import hashlib
import json
import os
import resource
import sys
import time
from pathlib import Path

from .engine import Engine, StateError, SCHEMA, validate_lean, parse_cli, empty_state, _need

SNAPSHOT_EVERY = 64
JOURNAL_SCHEMA = "packetlm.journal/1"


def _cpu() -> float:
    return sum(resource.getrusage(resource.RUSAGE_SELF)[:2])


def _rhash(replies) -> str:
    return hashlib.sha256(json.dumps(replies).encode()).hexdigest()


def _file_checksum(p: Path):
    """The checksum field of a state document on disk (None if absent or unreadable)."""
    try:
        return json.loads(p.read_bytes()).get("checksum")
    except (OSError, ValueError, AttributeError):
        return None


class Open:
    """The one state path held in memory."""

    def __init__(self, path: Path, kw: dict, flags: list):
        self.path, self.kw, self.flags = path, kw, flags
        self.state, self.report, self.known, self.since = None, None, None, 0
        self.jpath = path.with_name(path.name + ".journal")
        self.jfh = None


class Server:
    def __init__(self, snapshot_every=SNAPSHOT_EVERY):
        self.cur: Open | None = None
        self.every = snapshot_every
        self.mark = 0.0  # CPU at the end of the previous charged request

    # ---------- persistence ----------

    def _engine(self, o: Open) -> Engine:
        eng = Engine(o.path, o.state, dict(o.report), **o.kw)
        eng._known_bytes = o.known
        return eng

    def _journal_start(self, o: Open, base) -> None:
        if o.jfh:
            o.jfh.close()
        tmp = o.jpath.with_name(o.jpath.name + ".tmp")
        with open(tmp, "wb") as fh:
            fh.write((json.dumps({"schema": JOURNAL_SCHEMA, "base": base}) + "\n").encode())
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, o.jpath)
        o.jfh = open(o.jpath, "ab")

    def _snapshot(self, o: Open) -> None:
        eng = self._engine(o)
        eng.save()  # lean save: full validation, backup kept, atomic replace, fsync
        o.state, o.known, o.since = eng.state, eng._known_bytes, 0
        self._journal_start(o, _file_checksum(o.path))

    def open_path(self, path: Path, kw: dict, flags: list) -> Open:
        _need(kw.get("lean"), "the long-lived protocol requires --lean snapshots")
        # adaptive retention counts engine constructions as calls; not supported by this protocol
        _need(kw.get("retention", "static") == "static", "the long-lived protocol requires static retention")
        o = Open(path, kw, flags)
        eng = Engine.open(path, **kw)  # same load as the per-process engine (validation, backup recovery)
        o.state, o.report, o.known = eng.state, eng.report, eng._known_bytes
        if o.jpath.exists():
            lines = o.jpath.read_bytes().splitlines()
            head = json.loads(lines[0]) if lines else {}
            _need(head.get("schema") == JOURNAL_SCHEMA, "journal header invalid")
            have = _file_checksum(path) if eng.report.get("loaded") == "primary" else \
                _file_checksum(path.with_name(path.name + ".bak"))
            if eng.report.get("loaded") == "new":
                have = None
            bak = _file_checksum(path.with_name(path.name + ".bak"))
            if head["base"] == have:
                done = 0
                for k, raw in enumerate(lines[1:], 1):
                    try:
                        rec = json.loads(raw)
                    except ValueError:
                        _need(k == len(lines) - 1, "journal record corrupt before its end")
                        break  # a torn final record: its call never returned a reply
                    e = Engine(path, o.state, dict(o.report), **parse_cli(rec["flags"])[0])
                    e._known_bytes = o.known
                    got = [e.turn(x) for x in rec["lines"]]
                    e.finish()
                    _need(_rhash(got) == rec["replies_sha256"], f"journal replay diverged at record {k}")
                    o.state = e.state
                    done += 1
                o.report = {**o.report, "journal_replayed": done}
            elif head["base"] is not None and head["base"] == bak and eng.report.get("loaded") == "primary":
                o.report = {**o.report, "journal_dropped": "contained in the primary snapshot"}
            else:
                raise StateError("journal does not extend the loaded snapshot")
            self._snapshot(o)  # replayed calls become a snapshot; the journal restarts on it
        else:
            self._journal_start(o, _file_checksum(path) if path.exists() else None)
        return o

    def close(self) -> None:
        o, self.cur = self.cur, None
        if o is None:
            return
        if o.since or not o.path.exists():
            self._snapshot(o)
        if o.jfh:
            o.jfh.close()

    # ---------- requests ----------

    def call(self, path, flags, lines) -> dict:
        t0 = time.process_time()
        path = Path(path)
        kw, rest = parse_cli(list(flags))
        _need(not rest, f"unknown flags {rest}")
        o = self.cur
        if o is None or o.path != path or o.flags != list(flags):
            self.close()
            o = self.cur = self.open_path(path, kw, list(flags))
            report = dict(o.report)
        else:
            report = {"loaded": "memory"}
        eng = self._engine(o)
        replies = [eng.turn(x) for x in lines]
        eng.finish()
        validate_lean({"schema": SCHEMA, "checksum": None, "state": eng.state}, checksum_ok=True)
        o.state = eng.state
        o.jfh.write((json.dumps({"flags": list(flags), "lines": list(lines), "replies_sha256": _rhash(replies)})
                     + "\n").encode())
        o.jfh.flush()
        os.fsync(o.jfh.fileno())
        o.since += 1
        if o.since >= self.every:
            self._snapshot(o)
        now = _cpu()
        out = {"load": report, "replies": replies, "stats": eng.stats, "cpu_s": round(time.process_time() - t0, 4),
               "cpu_total_s": round(now - self.mark, 4)}
        self.mark = now
        return out

    def inspect(self, path) -> dict:
        """Measurement only: write the open (or on-disk) state document for the harness to read."""
        c0 = _cpu()
        path = Path(path)
        st = self.cur.state if self.cur and self.cur.path == path else None
        dst = path.with_name(path.name + ".inspect")
        if st is not None:
            dst.write_text(json.dumps({"schema": SCHEMA, "checksum": None, "state": st}))
        elif dst.exists():
            dst.unlink()
        dt = _cpu() - c0
        self.mark += dt  # excluded from the next charged request
        return {"inspected": st is not None, "inspect_cpu_s": round(dt, 4)}

    def handle(self, req) -> dict:
        op = req.get("op")
        if op == "call":
            try:
                return self.call(req["state"], req.get("flags", []), req["lines"])
            except BaseException:
                # as when an engine process fails: nothing of this call is kept; the next call
                # reloads from the snapshot and the journal
                o, self.cur = self.cur, None
                if o and o.jfh:
                    o.jfh.close()
                raise
        if op == "inspect":
            return self.inspect(req["state"])
        if op == "close":
            self.close()
            now = _cpu()
            out = {"closed": True, "cpu_total_s": round(now - self.mark, 4)}
            self.mark = now
            return out
        raise ValueError(f"unknown op {op}")


def main() -> int:
    srv = Server(int(os.environ.get("PACKETLM_SNAPSHOT_EVERY", SNAPSHOT_EVERY)))
    out = sys.stdout
    for raw in sys.stdin:
        if not raw.strip():
            continue
        try:
            resp = srv.handle(json.loads(raw))
        except (StateError, ValueError, KeyError) as exc:
            resp = {"error": f"{type(exc).__name__}: {exc}"}
        out.write(json.dumps(resp) + "\n")
        out.flush()
    srv.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
