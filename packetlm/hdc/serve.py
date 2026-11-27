"""G60H long-lived protocol for the HDC engine: the JSON-lines protocol of packetlm/serve.py
(ops call / inspect / close, same reply fields and CPU accounting), so the G56/G58/G59 harness drives it
unchanged. Durability mirrors serve.py: one fsync'd journal record per call, a snapshot (JSON of the
exact journal copy, with the full validation) every SNAPSHOT_EVERY journaled calls and when the path
changes or closes; a new path gets an empty snapshot first. After a snapshot the long-lived state is
moved to the permanent GC generation (as G59 §2d). Per call: change-scoped validation (charged).
Run: python -m packetlm.hdc.serve
"""
from __future__ import annotations
import gc
import hashlib
import json
import os
import resource
import sys
import time
from pathlib import Path

from .engine import HEngine

SNAPSHOT_EVERY = 64
KNOWN = {"--answers", "--bounded", "--lean", "--no-library"}


def _cpu():
    return sum(resource.getrusage(resource.RUSAGE_SELF)[:2])


def parse(flags):
    kw = {"library": True, "deepen": 5}
    for f in flags:
        if f == "--no-library":
            kw["library"] = False
        elif f.startswith("--deepen="):
            kw["deepen"] = int(f.split("=", 1)[1])
        elif f not in KNOWN:
            raise ValueError(f"unknown flag {f}")
    return kw


class Server:
    def __init__(self, every=SNAPSHOT_EVERY):
        self.every, self.cur, self.mark = every, None, _cpu()

    def _snapshot(self):
        o = self.cur
        o["eng"].validate_full()
        p = o["path"]
        tmp = p.with_name(p.name + ".tmp")
        data = json.dumps({"schema": "packetlm.hdc/1", "state": o["eng"].state_doc()})
        with open(tmp, "w") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, p)
        if o.get("jfh"):
            o["jfh"].close()
        o["jfh"] = open(str(p) + ".journal", "wb")
        o["jfh"].write((json.dumps({"base": hashlib.sha256(data.encode()).hexdigest()}) + "\n").encode())
        o["since"] = 0
        gc.collect(1)
        gc.freeze()

    def open_path(self, path, flags):
        kw = parse(flags)
        if path.exists():
            doc = json.loads(path.read_text())["state"]
            eng = HEngine.from_doc(doc, **kw)
            jp = Path(str(path) + ".journal")
            if jp.exists():  # replay (crash recovery); every record must reproduce its replies
                for raw in jp.read_bytes().splitlines()[1:]:
                    rec = json.loads(raw)
                    got = [eng.turn(x) for x in rec["lines"]]
                    assert hashlib.sha256(json.dumps(got).encode()).hexdigest() == rec["replies_sha256"], "journal replay diverged"
            report = {"loaded": "primary"}
        else:
            eng, report = HEngine(**kw), {"loaded": "new"}
        self.cur = {"path": path, "flags": list(flags), "eng": eng, "since": 0, "jfh": None}
        self._snapshot()
        return report

    def close(self):
        o = self.cur
        if o is None:
            return
        if o["since"]:
            self._snapshot()
        if o.get("jfh"):
            o["jfh"].close()
        self.cur = None
        if gc.get_freeze_count():
            gc.unfreeze()

    def call(self, path, flags, lines):
        t0 = time.process_time()
        path = Path(path)
        o = self.cur
        if o is None or o["path"] != path or o["flags"] != list(flags):
            self.close()
            report = self.open_path(path, flags)
            o = self.cur
        else:
            report = {"loaded": "memory"}
        eng = o["eng"]
        eng.new_stats()
        replies = [eng.turn(x) for x in lines]
        eng.validate_touched()
        o["jfh"].write((json.dumps({"lines": list(lines), "replies_sha256":
                                    hashlib.sha256(json.dumps(replies).encode()).hexdigest()}) + "\n").encode())
        o["jfh"].flush()
        os.fsync(o["jfh"].fileno())
        o["since"] += 1
        if o["since"] >= self.every:
            self._snapshot()
        now = _cpu()
        stats = dict(eng.stats, **{"cum_" + k: v for k, v in eng.counters.items()})
        out = {"load": report, "replies": replies, "stats": stats, "cpu_s": round(time.process_time() - t0, 4),
               "cpu_total_s": round(now - self.mark, 4)}
        self.mark = now
        return out

    def inspect(self, path):
        c0 = _cpu()
        path = Path(path)
        dst = path.with_name(path.name + ".inspect")
        ok = self.cur is not None and self.cur["path"] == path
        if ok:
            dst.write_text(json.dumps({"state": self.cur["eng"].state_doc()}))
        elif dst.exists():
            dst.unlink()
        dt = _cpu() - c0
        self.mark += dt
        return {"inspected": ok, "inspect_cpu_s": round(dt, 4)}

    def handle(self, req):
        op = req.get("op")
        if op == "call":
            return self.call(req["state"], req.get("flags", []), req["lines"])
        if op == "inspect":
            return self.inspect(req["state"])
        if op == "close":
            self.close()
            now = _cpu()
            out = {"closed": True, "cpu_total_s": round(now - self.mark, 4)}
            self.mark = now
            return out
        raise ValueError(f"unknown op {op}")


def main():
    srv = Server(int(os.environ.get("PACKETLM_SNAPSHOT_EVERY", SNAPSHOT_EVERY)))
    for raw in sys.stdin:
        if not raw.strip():
            continue
        try:
            resp = srv.handle(json.loads(raw))
        except (ValueError, KeyError, AssertionError) as exc:
            resp = {"error": f"{type(exc).__name__}: {exc}"}
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()
    srv.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
