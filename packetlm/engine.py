"""G44 canonical engine.

One persistent state. Memory, constructions, bitwise execution,
acquisition, discovery, a capability library, and an atomic save.
It reuses field (bind/ask/decode), roles (induce/select),
geom (rows_from/compose/bits) and system.invalidate.
Symbolic and bitwise. No transformer. Not a mind.
"""

from __future__ import annotations
import hashlib
import json
import os
import sys
from itertools import product
from pathlib import Path
from .field import bind, partial, pack, decode
from .packets import Packet
from .roles import induce, select
from .system import invalidate

SCHEMA = "packetlm.engine/1"
FACT_KEYS = {"id": str, "s": str, "r": str, "o": str, "bits": str, "count": int,
             "source": str, "turn": int, "premises": list, "program": (str, type(None))}
STATE_KEYS = {"turn": int, "facts": list, "log": list, "library": list,
              "capabilities": dict, "observations": dict, "pending": dict}


class StateError(Exception):
    pass


# Shared language helpers. chat and geom route through these.

def choose(library, meaning):
    hits = [c for c in library if c and c.get("meaning") == meaning]
    return hits[0] if len(hits) == 1 else None


def express(construction, fact):
    if not construction:
        return None
    s, _, o = fact
    roles = {"s": s, "r": construction["word"], "o": o}
    return " ".join(roles[role] for role in construction["order"])


def judge(pred, ans):
    """Missing knowledge is undetermined, never contradicted."""
    if pred is None:
        return "undetermined"
    return "supported" if pred == ans else "contradicted"


def _geom():
    from . import geom  # lazy: geom imports choose/express from here
    return geom


def empty_state() -> dict:
    return {"turn": 0, "facts": [], "log": [], "library": [],
            "capabilities": {}, "observations": {}, "pending": {}}


def _checksum(state: dict) -> str:
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()


def validate(doc) -> dict:
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise StateError("schema mismatch")
    state = doc.get("state")
    if not isinstance(state, dict):
        raise StateError("state missing")
    if doc.get("checksum") != _checksum(state):
        raise StateError("checksum mismatch")
    for key, typ in STATE_KEYS.items():
        if not isinstance(state.get(key), typ):
            raise StateError(f"bad field {key}")
    for f in state["facts"]:
        for key, typ in FACT_KEYS.items():
            if key not in f or not isinstance(f[key], typ):
                raise StateError(f"bad fact key {key}")
        if bind(f["s"], f["r"], f["o"]).bits.hex() != f["bits"]:
            raise StateError(f"packet does not bind {f['id']}")
    for c in state["library"]:
        if not {"order", "rel_at", "word", "meaning"} <= set(c):
            raise StateError("bad construction")
    for name, cap in state["capabilities"].items():
        if not isinstance(cap.get("seq"), list) or not cap["seq"]:
            raise StateError(f"bad capability {name}")
    return state


def _write_atomic(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


class Engine:
    def __init__(self, path: Path | str, state: dict, report: dict):
        self.path = Path(path)
        self.state = state
        self.report = report

    # ---------- persistence ----------

    @classmethod
    def open(cls, path) -> "Engine":
        path = Path(path)
        bak = path.with_name(path.name + ".bak")
        if not path.exists() and not bak.exists():
            return cls(path, empty_state(), {"loaded": "new"})
        errors = {}
        for label, p in (("primary", path), ("backup", bak)):
            if not p.exists():
                errors[label] = "missing"
                continue
            try:
                state = validate(json.loads(p.read_text()))
            except (ValueError, StateError) as exc:
                errors[label] = str(exc)
                continue
            report = {"loaded": label}
            if label == "backup":
                report["recovered"] = True
                report["primary_error"] = errors["primary"]
            return cls(path, state, report)
        raise StateError(f"no valid state: {errors}")

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            try:
                validate(json.loads(self.path.read_text()))
                _write_atomic(self.path.with_name(self.path.name + ".bak"), self.path.read_bytes())
            except (ValueError, StateError):
                pass  # never back up a corrupt primary over a good backup
        doc = {"schema": SCHEMA, "checksum": _checksum(self.state), "state": self.state}
        _write_atomic(self.path, json.dumps(doc).encode())
        try:
            dfd = os.open(self.path.parent, os.O_RDONLY)
            os.fsync(dfd)
            os.close(dfd)
        except OSError:
            pass

    # ---------- semantic memory ----------

    def _tick(self) -> int:
        self.state["turn"] += 1
        return self.state["turn"]

    def entities(self) -> list[str]:
        seen = []
        for f in self.state["facts"]:
            for t in (f["s"], f["o"]):
                if t not in seen:
                    seen.append(t)
        return seen

    def relations(self) -> list[str]:
        return sorted({f["r"] for f in self.state["facts"]})

    def _find(self, s, r, o=None):
        return [f for f in self.state["facts"] if f["s"] == s and f["r"] == r and (o is None or f["o"] == o)]

    def tell(self, s, r, o, source="told", premises=None, program=None) -> dict:
        existing = self._find(s, r, o)
        if existing:
            return existing[0]
        pkt = bind(s, r, o)
        fact = {"id": f"{s}:{r}:{o}", "s": s, "r": r, "o": o, "bits": pkt.bits.hex(),
                "count": pkt.count, "source": source, "turn": self._tick(),
                "premises": list(premises or []), "program": program}
        self.state["facts"].append(fact)
        return fact

    def _remove(self, ids: list[str], reason: str) -> list[str]:
        facts = self.state["facts"]
        gone = set()
        for key in ids:
            gone.add(key)
            before = {f["id"] for f in facts}
            facts = [f for f in facts if f["id"] != key]
            facts = invalidate(facts, key)  # system.invalidate: recursive premise drop
            gone |= before - {f["id"] for f in facts}
        turn = self._tick()
        for key in sorted(gone):
            self.state["log"].append({"id": key, "turn": turn, "reason": reason})
        self.state["facts"] = facts
        return sorted(gone)

    def retract(self, s, r, o=None) -> list[str]:
        ids = [f["id"] for f in self._find(s, r, o)]
        return self._remove(ids, f"retract {s} {r} {o or '*'}") if ids else []

    def correct(self, s, r, o) -> dict:
        ids = [f["id"] for f in self._find(s, r) if f["o"] != o]
        removed = self._remove(ids, f"correct {s} {r} {o}") if ids else []
        fact = self.tell(s, r, o, source="correction")
        return {"fact": fact["id"], "removed": removed}

    def ask(self, s, r) -> dict:
        """Geometric recall: unbind the partial query from each packet and decode."""
        q = partial(s, r)
        qi = int.from_bytes(q.bits, "big")
        names = self.entities()
        found = []
        for f in self.state["facts"]:
            pkt = Packet(bits=bytes.fromhex(f["bits"]), count=f["count"])
            if pkt.score(q) <= 0:
                continue
            got = decode(pack(int.from_bytes(pkt.bits, "big") ^ qi), names)
            if got and got not in found:
                found.append(got)
        if not found:
            return {"status": "unknown", "value": None}
        if len(found) > 1:
            return {"status": "ambiguous", "value": None, "candidates": sorted(found)}
        return {"status": "known", "value": found[0]}

    # ---------- constructions ----------

    def learn_construction(self, examples) -> dict | None:
        c = induce(examples)
        if not c:
            return None
        lib = self.state["library"]
        if any(x["word"] == c["word"] and x["rel_at"] == c["rel_at"] and x["meaning"] != c["meaning"] for x in lib):
            return None  # the same surface word cannot mean two things
        if c not in lib:
            lib.append(c)
        return c

    def read(self, sentence):
        return select(self.state["library"], sentence)

    def speak(self, fact):
        return express(choose(self.state["library"], fact[1]), fact)

    # ---------- binary execution ----------

    def expand(self, seq, depth=0) -> list[str]:
        if depth > 8:
            raise StateError("capability cycle")
        out = []
        for step in seq:
            cap = self.state["capabilities"].get(step)
            out += self.expand(cap["seq"], depth + 1) if cap else [step]
        return out

    def execute(self, seq, subject):
        """Run a program as bit-row matrix composition (geom.compose)."""
        g = _geom()
        names = self.entities()
        if subject not in names:
            return set()
        index = {n: i for i, n in enumerate(names)}
        triples = [(index[f["s"]], f["r"], index[f["o"]]) for f in self.state["facts"]]
        row = 1 << index[subject]
        for rel in self.expand(seq):
            row = g.compose([row], g.rows_from(triples, len(names), rel))[0]
            if not row:
                return set()
        return {names[i] for i in g.bits(row)}

    def walk(self, seq, subject):
        """Reference executor: step-by-step geometric ask. Used as a control."""
        cur, path = subject, []
        for rel in self.expand(seq):
            got = self.ask(cur, rel)
            if got["status"] != "known":
                return None, path
            path.append(f"{cur}:{rel}:{got['value']}")
            cur = got["value"]
        return cur, path

    def predict(self, seq, subject):
        out = self.execute(seq, subject)
        return next(iter(out)) if len(out) == 1 else None

    # ---------- acquisition ----------

    def observe(self, name, subject, value) -> None:
        obs = self.state["observations"].setdefault(name, [])
        if [subject, value] not in obs:
            obs.append([subject, value])
        self._tick()

    def evaluate(self, seq, observations) -> dict:
        marks = [judge(self.predict(seq, s), v) for s, v in observations]
        if "contradicted" in marks:
            status = "contradicted"
        elif marks and all(m == "supported" for m in marks):
            status = "supported"
        else:
            status = "undetermined"
        return {"seq": list(seq), "status": status, "support": marks.count("supported")}

    def hypotheses(self, name, max_len=2, use_library=True) -> list[dict]:
        prims = [r for r in self.relations() if r != name]
        if use_library:
            prims += sorted(c for c in self.state["capabilities"] if c != name)
        obs = self.state["observations"].get(name, [])
        out, seen = [], set()
        for n in range(1, max_len + 1):
            for seq in product(prims, repeat=n):
                key = tuple(self.expand(seq))
                if key in seen:
                    continue  # same base program through another name
                seen.add(key)
                h = self.evaluate(seq, obs)
                if h["status"] != "contradicted" and h["support"] > 0:
                    out.append(h)
        return out

    def acquire(self, name, max_len=2, use_library=True) -> dict:
        live = self.hypotheses(name, max_len, use_library)
        supported = [h for h in live if h["status"] == "supported"]
        if len(live) == 1 and supported:
            return self._adopt(name, supported[0], "acquired")
        self.state["pending"][name] = live
        return {"name": name, "result": "pending" if live else "none", "live": live}

    def _adopt(self, name, h, how) -> dict:
        self.state["capabilities"][name] = {
            "seq": h["seq"], "base": self.expand(h["seq"]), "how": how,
            "observations": len(self.state["observations"].get(name, [])), "turn": self._tick()}
        self.state["pending"].pop(name, None)
        return {"name": name, "result": how, "seq": h["seq"]}

    def discover(self, name, oracle, budget=8) -> dict:
        """Choose questions that split live hypotheses. The oracle only answers."""
        live = [h["seq"] for h in self.state["pending"].get(name, [])]
        asked = []
        for _ in range(budget):
            if len(live) <= 1:
                break
            done = {s for s, _ in self.state["observations"].get(name, [])} | set(asked)
            best, best_score = None, 0
            for s in self.entities():
                if s in done:
                    continue
                known = [p for p in (self.predict(h, s) for h in live) if p is not None]
                counts = {v: known.count(v) for v in set(known)}
                score = min(counts.values()) if len(counts) >= 2 else 0
                if score > best_score:
                    best, best_score = s, score
            if best is None:
                break
            asked.append(best)
            ans = oracle(best)
            if ans is not None:
                self.observe(name, best, ans)
            obs = self.state["observations"].get(name, [])
            live = [h for h in live if self.evaluate(h, obs)["status"] != "contradicted"]
        obs = self.state["observations"].get(name, [])
        judged = [self.evaluate(h, obs) for h in live]
        supported = [h for h in judged if h["status"] == "supported"]
        result = {"name": name, "asked": asked, "live": judged}
        if len(supported) == 1:
            result.update(self._adopt(name, supported[0], "discovered"))
            result["undetermined"] = [h["seq"] for h in judged if h["status"] == "undetermined"]
        else:
            self.state["pending"][name] = judged
            result["result"] = "pending"
        return result

    def derive(self, name, subject) -> dict:
        cap = self.state["capabilities"].get(name)
        if not cap:
            return {"status": "no capability"}
        value, path = self.walk(cap["seq"], subject)
        if value is None or {value} != self.execute(cap["seq"], subject):
            return {"status": "unknown"}
        fact = self.tell(subject, name, value, source="derived", premises=path, program=name)
        return {"status": "derived", "fact": fact["id"], "premises": path}

    # ---------- turns (G45 start: structured teaching through this runtime) ----------

    def turn(self, line: str) -> str:
        raw = line.strip().rstrip("?").rstrip(".")
        parts = raw.lower().split()
        if not parts:
            return "empty"
        head, rest = parts[0], parts[1:]
        if head == "construct" and ":" in raw:
            meaning = raw.split(":", 1)[0].split()[1].lower()
            examples = []
            for chunk in raw.split(":", 1)[1].split(";"):
                if "=" not in chunk:
                    return "unparsed"
                sent, so = chunk.split("=")
                so = so.split()
                if len(so) != 2:
                    return "unparsed"
                examples.append((sent.strip().lower(), (so[0], meaning, so[1])))
            c = self.learn_construction(examples)
            return f"construction {meaning} {''.join(c['order'])}" if c else "construction rejected"
        if head == "correct" and len(rest) == 3:
            got = self.correct(*rest)
            return f"corrected {' '.join(rest)}; removed {len(got['removed'])}"
        if head == "retract" and len(rest) in (2, 3):
            gone = self.retract(*rest)
            return f"retracted {len(gone)}" if gone else "nothing to retract"
        if head == "observe" and len(rest) == 3:
            self.observe(*rest)
            return f"observed {rest[0]} {rest[1]} {rest[2]}"
        if head == "acquire" and len(rest) == 1:
            got = self.acquire(rest[0])
            return f"{got['result']} {rest[0]}" + (f" {'+'.join(got['seq'])}" if "seq" in got else f" live {len(got['live'])}")
        if head == "derive" and len(rest) == 2:
            got = self.derive(*rest)
            return f"derived {got['fact']}" if got["status"] == "derived" else got["status"]
        if head in ("what", "ask") and (len(rest) == 3 and rest[0] == "is" or head == "ask" and len(rest) == 2):
            s, r = rest[-2], rest[-1]
            got = self.ask(s, r)
            if got["status"] == "unknown" and r in self.state["capabilities"]:
                value = self.predict(self.state["capabilities"][r]["seq"], s)
                got = {"status": "known", "value": value} if value else got
            if got["status"] == "ambiguous":
                return "ambiguous " + " ".join(got["candidates"])
            if got["status"] != "known":
                return "unknown"
            return self.speak((s, r, got["value"])) or f"{s} {r} {got['value']}"
        fact = self.read(raw.lower())
        if fact:
            self.tell(*fact, source="sentence")
            return f"recorded {' '.join(fact)}"
        return "unparsed"


def main(argv) -> int:
    if len(argv) < 2:
        print("usage: python -m packetlm.engine STATE 'line' ['line' ...]")
        return 2
    eng = Engine.open(argv[0])
    replies = [eng.turn(line) for line in argv[1:]]
    eng.save()
    print(json.dumps({"load": eng.report, "replies": replies}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
