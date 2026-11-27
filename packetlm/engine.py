"""Canonical PacketLM engine (schema 2).

One persistent state. Memory with proofs, constructions and a lexicon,
bit-matrix execution, acquisition from accumulated observations,
three-way hypothesis judgement, a versioned capability library and
atomic, validated persistence. Reuses field (bind/partial/pack),
roles (induce/select) and geom (rows_from/compose/bits).
Symbolic and bitwise. No transformer. Not a mind.

Uncertainty policy (docs/G44.md):
- A hypothesis is contradicted only by a single defined prediction that
  differs from the observed answer. No prediction, or several, is undetermined.
- Every non-contradicted hypothesis is kept, including zero-support ones.
- A candidate is the unique hypothesis supported by every observation.
- Blocking alternatives: other non-contradicted hypotheses with >= 1
  supported observation whose predictions differ from the candidate's
  on some entity of the current world.
- No blocking alternative -> qualified. Blocking alternatives -> provisional:
  it executes, and every answer through it is marked provisional.
"""

from __future__ import annotations
import hashlib
import json
import os
import sys
import time
from itertools import product
from pathlib import Path
from .field import bind, partial, pack, bits_for
from .packets import Packet
from .roles import induce, select
from . import reference

SCHEMA = "packetlm.engine/2"
EXEC_OK = ("qualified", "provisional")
PINNED_OK = EXEC_OK + ("superseded",)  # a pinned dependent keeps its old definition
VER_STATUS = ("qualified", "provisional", "suspended", "revoked", "superseded")


class StateError(Exception):
    pass


# ---------- shared language helpers (chat and geom route through these) ----------

def choose(library, meaning):
    hits = [c for c in library if c and c.get("meaning") == meaning and c.get("kind", "svo") == "svo"]
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
    return {"turn": 0, "facts": [], "log": [], "library": [], "lexicon": {},
            "capabilities": {}, "observations": {}, "retired": {}, "hypotheses": {}}


def _checksum(state: dict) -> str:
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()


def _need(cond, msg):
    if not cond:
        raise StateError(msg)


def _deps_of(seq):
    return [s for s in seq if s.startswith("cap:")]


def _split_cap(step):
    name, v = step[4:].rsplit("@", 1)
    return name, int(v)


def validate(doc) -> dict:
    _need(isinstance(doc, dict) and doc.get("schema") == SCHEMA, "schema mismatch")
    state = doc.get("state")
    _need(isinstance(state, dict), "state missing")
    _need(doc.get("checksum") == _checksum(state), "checksum mismatch")
    types = {"turn": int, "facts": list, "log": list, "library": list, "lexicon": dict,
             "capabilities": dict, "observations": dict, "retired": dict, "hypotheses": dict}
    for key, typ in types.items():
        _need(isinstance(state.get(key), typ), f"bad field {key}")
    ids = set()
    for f in state["facts"]:
        for key, typ in {"id": str, "s": str, "r": str, "o": str, "bits": str, "count": int, "supports": list}.items():
            _need(isinstance(f.get(key), typ), f"bad fact key {key}")
        _need(f["id"] == f"{f['s']} {f['r']} {f['o']}", f"bad fact id {f['id']}")
        _need(f["id"] not in ids, f"duplicate fact {f['id']}")
        ids.add(f["id"])
        _need(bind(f["s"], f["r"], f["o"]).bits.hex() == f["bits"], f"packet does not bind {f['id']}")
        _need(f["supports"], f"unsupported fact {f['id']}")
        for sp in f["supports"]:
            _need(sp.get("kind") in ("told", "derived") and isinstance(sp.get("premises"), list)
                  and isinstance(sp.get("turn"), int), f"bad support on {f['id']}")
    for f in state["facts"]:
        for sp in f["supports"]:
            for p in sp["premises"]:
                _need(p in ids, f"dangling premise {p} on {f['id']}")
    for c in state["library"]:
        kind = c.get("kind", "svo")
        if kind == "svo":
            _need({"order", "rel_at", "word", "meaning"} <= set(c), "bad construction")
        else:
            _need(kind == "question" and isinstance(c.get("template"), list) and "meaning" in c, "bad question construction")
    for word, target in state["lexicon"].items():
        _need(isinstance(word, str) and isinstance(target, str), "bad lexicon entry")
    for name, rs in state["retired"].items():
        _need(all(isinstance(x, dict) and {"s", "o", "reason"} <= set(x) for x in rs), f"bad retired {name}")
    for name, obs in state["observations"].items():
        _need(all(isinstance(o, list) and len(o) == 2 for o in obs), f"bad observations {name}")
    caps = state["capabilities"]
    for name, cap in caps.items():
        _need(isinstance(cap.get("versions"), list), f"bad capability {name}")
        cur = cap.get("current")
        _need(cur is None or 1 <= cur <= len(cap["versions"]), f"bad current version {name}")
        for i, ver in enumerate(cap["versions"], 1):
            _need(ver.get("v") == i and ver.get("status") in VER_STATUS and ver.get("seq"), f"bad version {name}@{i}")
            for d in _deps_of(ver["seq"]):
                dn, dv = _split_cap(d)
                _need(dn in caps and 1 <= dv <= len(caps[dn]["versions"]), f"missing dependency {d} of {name}")
    def visit(node, stack):
        _need(node not in stack, f"dependency cycle at {node}")
        name, v = _split_cap(node)
        for d in _deps_of(caps[name]["versions"][v - 1]["seq"]):
            visit(d, stack | {node})
    for name, cap in caps.items():
        for ver in cap["versions"]:
            visit(f"cap:{name}@{ver['v']}", set())
    return state


def _write_atomic(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


class Engine:
    def __init__(self, path, state=None, report=None, geometry=True, use_library=True, deepen=None):
        self.path = Path(path)
        self.state = state if state is not None else empty_state()
        self.report = report or {"loaded": "new"}
        self.geometry = geometry
        self.use_library = use_library
        self.deepen = deepen  # None: fixed depth 2. int: iterative deepening up to this length
        self.stats = {"evaluations": 0, "executions": 0, "row_ops": 0, "asks": 0}
        self._cache = None

    # ---------- persistence ----------

    @classmethod
    def open(cls, path, **kw) -> "Engine":
        path = Path(path)
        bak = path.with_name(path.name + ".bak")
        if not path.exists() and not bak.exists():
            return cls(path, empty_state(), {"loaded": "new"}, **kw)
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
            return cls(path, state, report, **kw)
        raise StateError(f"no valid state: {errors}")

    def save(self) -> None:
        validate({"schema": SCHEMA, "checksum": _checksum(self.state), "state": self.state})
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

    # ---------- indexes ----------

    def _idx(self):
        if self._cache is None:
            names, pos, decode, triples = [], {}, {}, []
            for f in self.state["facts"]:
                for t in (f["s"], f["o"]):
                    if t not in pos:
                        pos[t] = len(names)
                        names.append(t)
                        decode[pack(bits_for(t, 2)).bits] = t
                triples.append((f["s"], f["r"], f["o"]))
            self._cache = {"names": names, "pos": pos, "decode": decode, "rows": {},
                           "triples": triples, "ref": reference.index(triples),
                           "byid": {f["id"]: f for f in self.state["facts"]}}
        return self._cache

    def _dirty(self):
        self._cache = None

    def entities(self) -> list[str]:
        return list(self._idx()["names"])

    def relations(self) -> list[str]:
        """Primitive relation identities: told facts only, never cap:* conclusions."""
        return sorted({f["r"] for f in self.state["facts"]
                       if not f["r"].startswith("cap:") and any(sp["kind"] == "told" for sp in f["supports"])})

    # ---------- semantic memory ----------

    def _tick(self) -> int:
        self.state["turn"] += 1
        return self.state["turn"]

    def _find(self, s, r, o=None):
        return [f for f in self.state["facts"] if f["s"] == s and f["r"] == r and (o is None or f["o"] == o)]

    def tell(self, s, r, o, source="told", premises=None, program=None) -> dict:
        kind = "derived" if program else "told"
        support = {"kind": kind, "source": source, "turn": self._tick(),
                   "premises": list(premises or []), "program": program}
        existing = self._find(s, r, o)
        if existing:
            fact = existing[0]
            if not any(sp["kind"] == kind and sp["premises"] == support["premises"] and sp.get("program") == program
                       for sp in fact["supports"]):
                fact["supports"].append(support)
            return fact
        pkt = bind(s, r, o)
        fact = {"id": f"{s} {r} {o}", "s": s, "r": r, "o": o, "bits": pkt.bits.hex(),
                "count": pkt.count, "supports": [support]}
        self.state["facts"].append(fact)
        self._dirty()
        return fact

    def _drop(self, ids, reason, programs=()) -> dict:
        """Truth maintenance: remove facts, then any proof that used them or a dropped program.
        A conclusion stays while one independent proof remains."""
        removed = set(ids)
        dropped_proofs = 0
        changed = True
        while changed:
            changed = False
            for f in self.state["facts"]:
                if f["id"] in removed:
                    continue
                keep = [sp for sp in f["supports"]
                        if not (set(sp["premises"]) & removed) and sp.get("program") not in programs]
                if len(keep) != len(f["supports"]):
                    dropped_proofs += len(f["supports"]) - len(keep)
                    f["supports"] = keep
                    changed = True
                    if not keep:
                        removed.add(f["id"])
        self.state["facts"] = [f for f in self.state["facts"] if f["id"] not in removed]
        turn = self._tick()
        for key in sorted(removed):
            self.state["log"].append({"id": key, "turn": turn, "reason": reason})
        self._dirty()
        return {"removed": sorted(removed), "proofs_dropped": dropped_proofs}

    def _retire(self, ids, reason) -> list[str]:
        """An example whose value was explained through a fact that is now changing
        was dependent evidence. It is retired (kept, with the reason), not counted
        against the procedure. A capability keeps the status it earned; `show` and
        `why` report the retirement."""
        ids = set(ids)
        events = []
        for name in list(self.state["observations"]):
            ver = self.version(name)
            if not ver or ver["status"] not in EXEC_OK:
                continue
            base = self.expand(ver["seq"])
            keep = []
            for s, v in self.state["observations"][name]:
                if any(end == v and set(p) & ids for end, p in self.proofs(base, s)):
                    self.state["retired"].setdefault(name, []).append(
                        {"s": s, "o": v, "turn": self.state["turn"], "reason": reason})
                    events.append(f"retired example {name}: {s} -> {v}")
                else:
                    keep.append([s, v])
            self.state["observations"][name] = keep
        return events

    def retract(self, s, r, o=None) -> dict:
        ids = [f["id"] for f in self._find(s, r, o)]
        if not ids:
            return {"removed": [], "proofs_dropped": 0, "review": []}
        retired = self._retire(ids, f"retract {s} {r} {o or '*'}")
        out = self._drop(ids, f"retract {s} {r} {o or '*'}")
        out["review"] = retired + self.review()
        return out

    def correct(self, s, r, o) -> dict:
        ids = [f["id"] for f in self._find(s, r) if f["o"] != o]
        retired = self._retire(ids, f"correct {s} {r} {o}") if ids else []
        out = self._drop(ids, f"correct {s} {r} {o}") if ids else {"removed": [], "proofs_dropped": 0}
        self.tell(s, r, o, source="correction")
        out["review"] = retired + self.review()
        return out

    def correct_example(self, name, s, o) -> list[str]:
        """The teacher replaces an earlier example. The old one is retired; the
        procedure is re-checked and suspended if the new example contradicts it."""
        obs = self.state["observations"].setdefault(name, [])
        for old in [x for x in obs if x[0] == s]:
            obs.remove(old)
            self.state["retired"].setdefault(name, []).append(
                {"s": s, "o": old[1], "turn": self.state["turn"], "reason": f"example corrected to {o}"})
        return self.observe(name, s, o)

    def ask(self, s, r) -> dict:
        """Primitive recall. Geometric: unbind the partial query and decode the object role.
        Geometry disabled: a plain symbolic lookup (control)."""
        self.stats["asks"] += 1
        idx = self._idx()
        if not self.geometry:
            found = sorted(idx["ref"].get(r, {}).get(s, set()))
        else:
            q = partial(s, r)
            qi = int.from_bytes(q.bits, "big")
            found = []
            for f in self.state["facts"]:
                pkt = Packet(bits=bytes.fromhex(f["bits"]), count=f["count"])
                if pkt.score(q) <= 0:
                    continue
                got = idx["decode"].get(pack(int.from_bytes(pkt.bits, "big") ^ qi).bits)
                if got and got not in found:
                    found.append(got)
            found = sorted(found)
        if not found:
            return {"status": "unknown", "value": None}
        if len(found) > 1:
            return {"status": "ambiguous", "value": None, "candidates": found}
        return {"status": "known", "value": found[0]}

    # ---------- language ----------

    def learn_construction(self, examples) -> dict | None:
        c = induce(examples)
        if not c:
            return None
        lib = self.state["library"]
        if any(x.get("kind", "svo") == "svo" and x["word"] == c["word"] and x["rel_at"] == c["rel_at"]
               and x["meaning"] != c["meaning"] for x in lib):
            return None  # one surface word cannot mean two things
        if c not in lib:
            lib.append(c)
        return c

    def learn_question(self, meaning, examples) -> dict | None:
        """Variable-length question template: tokens equal to the given subject
        become the slot; all other tokens must agree across examples."""
        if len(examples) < 2 or len({s for _, s in examples}) < 2:
            return None
        toks = [sent.split() for sent, _ in examples]
        if len({len(t) for t in toks}) != 1:
            return None
        template = []
        for i in range(len(toks[0])):
            col = [t[i] for t in toks]
            if all(col[k] == examples[k][1] for k in range(len(examples))):
                template.append("<s>")
            elif len(set(col)) == 1:
                template.append(col[0])
            else:
                return None
        if template.count("<s>") != 1:
            return None
        c = {"kind": "question", "template": template, "meaning": meaning}
        lib = self.state["library"]
        if any(x.get("kind") == "question" and x["template"] == template and x["meaning"] != meaning for x in lib):
            return None
        if c not in lib:
            lib.append(c)
        return c

    def match_question(self, tokens):
        hits = []
        for c in self.state["library"]:
            if c.get("kind") != "question" or len(c["template"]) != len(tokens):
                continue
            slot = None
            for t, w in zip(c["template"], tokens):
                if t == "<s>":
                    slot = w
                elif t != w:
                    break
            else:
                hits.append((slot, c["meaning"]))
        return hits[0] if len(hits) == 1 else None

    def read(self, sentence):
        return select([c for c in self.state["library"] if c.get("kind", "svo") == "svo"], sentence)

    def speak(self, fact):
        return express(choose(self.state["library"], fact[1]), fact)

    # ---------- capabilities ----------

    def version(self, name, v=None):
        cap = self.state["capabilities"].get(name)
        if not cap:
            return None
        v = v or cap.get("current")
        return cap["versions"][v - 1] if v else None

    def expand(self, seq, depth=0):
        """Base relations of a program, or None if a pinned dependency cannot execute."""
        _need(depth <= 8, "capability nesting too deep")
        out = []
        for step in seq:
            if step.startswith("rel:"):
                out.append(step[4:])
            else:
                name, v = _split_cap(step)
                ver = self.version(name, v)
                if not ver or ver["status"] not in PINNED_OK:
                    return None
                sub = self.expand(ver["seq"], depth + 1)
                if sub is None:
                    return None
                out += sub
        return out

    def _closure(self, name, v, seen=None):
        seen = seen if seen is not None else set()
        for d in _deps_of(self.version(name, v)["seq"]):
            dn, dv = _split_cap(d)
            if (dn, dv) not in seen:
                seen.add((dn, dv))
                self._closure(dn, dv, seen)
        return seen

    def _dependents(self, name, v):
        out = []
        for n, cap in self.state["capabilities"].items():
            for ver in cap["versions"]:
                if f"cap:{name}@{v}" in ver["seq"]:
                    out.append((n, ver["v"]))
        return out

    def _set_status(self, name, v, status, reason):
        ver = self.version(name, v)
        if ver["status"] == status:
            return []
        ver["status"] = status
        ver.setdefault("history", []).append({"turn": self._tick(), "status": status, "reason": reason})
        events = [f"{name}@{v} {status}: {reason}"]
        if status not in EXEC_OK:
            self._drop([], f"{name}@{v} {status}", programs=(f"cap:{name}@{v}",))  # cached conclusions go
        for dn, dv in self._dependents(name, v):
            dep = self.version(dn, dv)
            if status in ("suspended", "revoked") and dep["status"] in EXEC_OK:
                events += self._set_status(dn, dv, "suspended", f"dependency {name}@{v} {status}")
            elif status == "superseded":
                dep.setdefault("history", []).append({"turn": self.state["turn"], "status": dep["status"],
                                                      "reason": f"still pinned to {name}@{v}; requalify to adopt the new version"})
                events.append(f"{dn}@{dv} stays pinned to {name}@{v}")
        return events

    def review(self) -> list[str]:
        """Re-check every executable capability against its own observations."""
        events = []
        for name, cap in self.state["capabilities"].items():
            ver = self.version(name)
            if not ver or ver["status"] not in EXEC_OK:
                continue
            h = self.evaluate(ver["seq"], self.state["observations"].get(name, []))
            if h["status"] == "contradicted":
                events += self._set_status(name, ver["v"], "suspended", "contradicted by its observations")
        return events

    # ---------- execution ----------

    def execute(self, seq, subject):
        """Run a program. Geometric: bit-row composition (geom.compose). Disabled: symbolic sets."""
        self.stats["executions"] += 1
        base = self.expand(seq) if any(s.startswith(("rel:", "cap:")) for s in seq) else list(seq)
        if base is None:
            return None
        idx = self._idx()
        if subject not in idx["pos"]:
            return set()
        if not self.geometry:
            return reference.run(idx["ref"], base, subject)
        g = _geom()
        n = len(idx["names"])
        row = 1 << idx["pos"][subject]
        for rel in base:
            if rel not in idx["rows"]:
                idx["rows"][rel] = g.rows_from([(idx["pos"][s], r, idx["pos"][o]) for s, r, o in idx["triples"] if r == rel], n, rel)
            row = g.compose([row], idx["rows"][rel])[0]
            self.stats["row_ops"] += 1
            if not row:
                return set()
        return {idx["names"][i] for i in g.bits(row)}

    def proofs(self, base, subject):
        """All fact paths for a base program (symbolic enumeration, used for provenance)."""
        paths = [(subject, [])]
        for rel in base:
            nxt = []
            for cur, prem in paths:
                for f in self._find(cur, rel):
                    nxt.append((f["o"], prem + [f["id"]]))
            paths = nxt[:256]
        return paths

    # ---------- acquisition ----------

    def observe(self, name, subject, value) -> list[str]:
        obs = self.state["observations"].setdefault(name, [])
        if [subject, value] not in obs:
            obs.append([subject, value])
        self._tick()
        return self.review()

    def evaluate(self, seq, observations) -> dict:
        marks = []
        for s, v in observations:
            self.stats["evaluations"] += 1
            out = self.execute(seq, s)
            marks.append(judge(next(iter(out)) if out and len(out) == 1 else None, v))
        if "contradicted" in marks:
            status = "contradicted"
        elif marks and all(m == "supported" for m in marks):
            status = "supported"
        else:
            status = "undetermined"
        return {"seq": list(seq), "status": status, "support": marks.count("supported")}

    def primitives(self, name):
        prims = [f"rel:{r}" for r in self.relations()]
        if self.use_library:
            for n in sorted(self.state["capabilities"]):
                ver = self.version(n)
                if n == name or not ver or ver["status"] not in EXEC_OK:
                    continue
                if any(dn == name for dn, _ in self._closure(n, ver["v"])):
                    continue  # would create a cycle
                prims.append(f"cap:{n}@{ver['v']}")
        return prims

    def hypotheses(self, name, max_len=2, min_len=1, seen=None):
        obs = self.state["observations"].get(name, [])
        out, evaluated, contradicted = [], 0, 0
        seen = set() if seen is None else seen
        for n in range(min_len, max_len + 1):
            for seq in product(self.primitives(name), repeat=n):
                base = self.expand(seq)
                if base is None or tuple(base) in seen:
                    continue
                seen.add(tuple(base))
                evaluated += 1
                h = self.evaluate(seq, obs)
                if h["status"] == "contradicted":
                    contradicted += 1
                else:
                    out.append(h)
        return out, evaluated, contradicted

    def _predictions(self, seq):
        out = {}
        for e in self.entities():
            r = self.execute(seq, e)
            out[e] = next(iter(r)) if r and len(r) == 1 else None
        return out

    def acquire(self, name, max_len=None) -> dict:
        if max_len is None and self.deepen:
            live, evaluated, contradicted, seen = [], 0, 0, set()
            for n in range(1, self.deepen + 1):
                lv, ev, co = self.hypotheses(name, n, n, seen)
                live += lv
                evaluated += ev
                contradicted += co
                if sum(h["status"] == "supported" for h in live) == 1:
                    break
            searched = n
        else:
            searched = max_len or 2
            live, evaluated, contradicted = self.hypotheses(name, searched)
        supported = [h for h in live if h["status"] == "supported"]
        record = {"turn": self.state["turn"], "evaluated": evaluated, "contradicted": contradicted, "searched_len": searched,
                  "live": live, "observations": len(self.state["observations"].get(name, []))}
        prior = self.state["hypotheses"].get(name, {})
        if prior.get("unanswered"):
            record["unanswered"] = prior["unanswered"]  # questions the oracle could not answer stay recorded
        self.state["hypotheses"][name] = record
        result = {"name": name, "evaluated": evaluated, "live": len(live),
                  "zero_support": sum(1 for h in live if h["support"] == 0)}
        if len(supported) != 1:
            result["result"] = "ambiguous" if supported else "none"
            result["supported"] = [h["seq"] for h in supported]
            cur = self.version(name)
            if cur and cur["status"] == "qualified" and supported:
                self._set_status(name, cur["v"], "provisional", "several supported programs")
            return result
        cand = supported[0]
        mine = self._predictions(cand["seq"])
        blocking = [h["seq"] for h in live if h is not cand and h["support"] >= 1
                    and self._predictions(h["seq"]) != mine]
        status = "provisional" if blocking else "qualified"
        record["candidate"] = cand["seq"]
        record["blocking"] = blocking
        result.update({"result": status, "seq": cand["seq"], "blocking": blocking})
        result["version"], result["events"] = self._adopt(name, cand, status, blocking)
        return result

    def _adopt(self, name, h, status, blocking):
        cap = self.state["capabilities"].setdefault(name, {"current": None, "versions": [], "express": None})
        cur = self.version(name)
        evidence = {"observations": len(self.state["observations"].get(name, [])),
                    "support": h["support"], "blocking": len(blocking), "turn": self._tick()}
        if cur and self.expand(cur["seq"]) == self.expand(h["seq"]) and cur["status"] in EXEC_OK + ("suspended",):
            cur["evidence"] = evidence
            return cur["v"], self._set_status(name, cur["v"], status, "requalified")
        events = []
        if cur and cur["status"] in EXEC_OK:
            events += self._set_status(name, cur["v"], "superseded", f"replaced by v{len(cap['versions']) + 1}")
        ver = {"v": len(cap["versions"]) + 1, "seq": h["seq"], "base": self.expand(h["seq"]),
               "status": status, "evidence": evidence,
               "history": [{"turn": evidence["turn"], "status": status, "reason": "acquired"}]}
        cap["versions"].append(ver)
        cap["current"] = ver["v"]
        return ver["v"], events

    def revoke(self, name) -> list[str]:
        ver = self.version(name)
        return self._set_status(name, ver["v"], "revoked", "revoked by teacher") if ver else []

    def investigate(self, name) -> dict:
        """Pick the subject whose answer would split the evidenced hypotheses."""
        rec = self.state["hypotheses"].get(name)
        if not rec:
            return {"result": "nothing to investigate"}
        live = [h["seq"] for h in rec["live"] if h["support"] >= 1]
        if len(live) <= 1:
            return {"result": "settled"}
        done = {s for s, _ in self.state["observations"].get(name, [])} | set(rec.get("unanswered", []))
        preds = {tuple(h): self._predictions(h) for h in live}
        best, best_score = None, 0
        for e in self.entities():
            if e in done:
                continue
            known = [p[e] for p in preds.values() if p[e] is not None]
            counts = {v: known.count(v) for v in set(known)}
            score = min(counts.values()) if len(counts) >= 2 else 0
            if score > best_score:
                best, best_score = e, score
        if best is None:
            gaps = [list(h) for h, p in preds.items() if all(v is None for e, v in p.items() if e not in done)]
            return {"result": "need knowledge", "undecidable": gaps}
        return {"result": "question", "subject": best}

    def discover(self, name, oracle, budget=8) -> dict:
        asked = []
        for _ in range(budget):
            q = self.investigate(name)
            if q["result"] != "question":
                break
            s = q["subject"]
            asked.append(s)
            ans = oracle(s)
            if ans is None:
                self.state["hypotheses"][name].setdefault("unanswered", []).append(s)
                continue
            self.observe(name, s, ans)
            self.acquire(name)
        final = self.acquire(name)
        final["asked"] = asked
        return final

    def derive(self, name, subject) -> dict:
        ver = self.version(name)
        if not ver or ver["status"] not in EXEC_OK:
            return {"status": "no executable capability"}
        out = self.execute(ver["seq"], subject)
        if not out or len(out) != 1:
            return {"status": "unknown" if not out else "ambiguous"}
        value = next(iter(out))
        paths = [p for end, p in self.proofs(self.expand(ver["seq"]), subject) if end == value]
        prog = f"cap:{name}@{ver['v']}"
        for p in paths:
            self.tell(subject, f"cap:{name}", value, source="derived", premises=p, program=prog)
        return {"status": "derived", "fact": f"{subject} cap:{name} {value}", "proofs": paths, "program": prog}

    # ---------- answering ----------

    def answer(self, s, word) -> dict:
        target = self.state["lexicon"].get(word, word)
        got = self.ask(s, target)
        if got["status"] != "unknown":
            return {**got, "relation": target, "via": "memory"}
        ver = self.version(target)
        if ver and ver["status"] in EXEC_OK:
            out = self.execute(ver["seq"], s)
            if out and len(out) == 1:
                return {"status": "known", "value": next(iter(out)), "relation": target,
                        "via": f"cap:{target}@{ver['v']}", "provisional": ver["status"] == "provisional"}
            if out:
                return {"status": "ambiguous", "value": None, "candidates": sorted(out), "relation": target,
                        "via": f"cap:{target}@{ver['v']}"}
        if ver and ver["status"] not in EXEC_OK:
            return {"status": "unknown", "value": None, "relation": target, "note": f"{target}@{ver['v']} {ver['status']}"}
        return {"status": "unknown", "value": None, "relation": target}

    def say(self, s, got) -> str:
        if got["status"] == "ambiguous":
            return "ambiguous: " + " or ".join(got["candidates"]) + "?"
        if got["status"] != "known":
            return "unknown" + (f" ({got['note']})" if got.get("note") else "")
        rel = got["relation"]
        cap = self.state["capabilities"].get(rel)
        meaning = (cap or {}).get("express") or rel
        text = self.speak((s, meaning, got["value"]))
        if text is None:
            text = f"{s} {rel} {got['value']} [no construction for {meaning}]"
        return text + (" [provisional]" if got.get("provisional") else "")

    def explain(self, s, word) -> str:
        got = self.answer(s, word)
        if got["status"] != "known":
            return self.say(s, got)
        if got["via"] == "memory":
            f = self._find(s, got["relation"], got["value"])[0]
            return "; ".join(f"{sp['kind']} by {sp['source']} at turn {sp['turn']}" for sp in f["supports"])
        name = got["relation"]
        ver = self.version(name)
        paths = [p for end, p in self.proofs(ver["base"], s) if end == got["value"]]
        ev = ver.get("evidence", {})
        retired = len(self.state["retired"].get(name, []))
        return (f"{got['via']} = {'+'.join(ver['seq'])} ({ver['status']}, {ev.get('observations', 0)} examples"
                + (f", {retired} retired" if retired else "") + f", {ev.get('blocking', 0)} open alternatives); path "
                + " | ".join(", ".join(p) for p in paths))

    def show(self, name) -> str:
        cap = self.state["capabilities"].get(name)
        if not cap:
            return "unknown capability"
        return "; ".join(f"v{v['v']} {'+'.join(v['seq'])} {v['status']}" for v in cap["versions"]) + \
            (f"; current v{cap['current']}" if cap["current"] else "")

    # ---------- turns: one controlled-language interface for people and tests ----------

    def turn(self, line: str) -> str:
        raw = line.strip().rstrip("?").rstrip(".").lower()
        parts = raw.split()
        if not parts:
            return "empty"
        head, rest = parts[0], parts[1:]
        if head in ("construct", "question") and ":" in raw:
            meaning = raw.split(":", 1)[0].split()[-1]
            chunks = [c for c in raw.split(":", 1)[1].split(";") if c.strip()]
            if any("=" not in c for c in chunks):
                return "unparsed"
            pairs = [(c.split("=")[0].strip(), c.split("=")[1].split()) for c in chunks]
            if head == "question":
                if any(len(so) != 1 for _, so in pairs):
                    return "unparsed"
                c = self.learn_question(meaning, [(sent, so[0]) for sent, so in pairs])
                return f"question {meaning} {' '.join(c['template'])}" if c else "question rejected"
            if any(len(so) != 2 for _, so in pairs):
                return "unparsed"
            c = self.learn_construction([(sent, (so[0], meaning, so[1])) for sent, so in pairs])
            return f"construction {meaning} {''.join(c['order'])}" if c else "construction rejected"
        if head == "fact" and len(rest) == 3:
            self.tell(*rest, source="fact")
            return f"recorded {' '.join(rest)}"
        if head == "define" and len(rest) == 3 and rest[1] == "as":
            self.state["lexicon"][rest[0]] = rest[2]
            return f"defined {rest[0]} as {rest[2]}"
        if head == "express" and len(rest) == 3 and rest[1] == "as":
            cap = self.state["capabilities"].get(rest[0])
            if not cap:
                return "unknown capability"
            cap["express"] = rest[2]
            return f"express {rest[0]} as {rest[2]}"
        if head == "example" and ":" in raw and "->" in raw:
            name = raw.split(":", 1)[0].split()[-1]
            lhs, rhs = raw.split(":", 1)[1].split("->")
            if len(lhs.split()) != 1 or len(rhs.split()) != 1:
                return "unparsed"
            events = self.observe(name, lhs.strip(), rhs.strip())
            got = self.acquire(name)
            msg = f"{got['result']} {name}" + (f" {'+'.join(got['seq'])}" if "seq" in got else "")
            return msg + (f"; {'; '.join(events + got.get('events', []))}" if events or got.get("events") else "")
        if head == "observe" and len(rest) == 3:
            events = self.observe(*rest)
            return f"observed {' '.join(rest)}" + (f"; {'; '.join(events)}" if events else "")
        if head == "unanswered" and ":" in raw:
            name = raw.split(":", 1)[0].split()[-1]
            subj = raw.split(":", 1)[1].split()
            if len(subj) != 1 or name not in self.state["hypotheses"]:
                return "unparsed"
            self.state["hypotheses"][name].setdefault("unanswered", []).append(subj[0])
            return f"noted: no answer for {subj[0]} {name}"
        if head in ("learn", "acquire", "requalify") and len(rest) == 1:
            got = self.acquire(rest[0])
            return f"{got['result']} {rest[0]}" + (f" {'+'.join(got['seq'])}" if "seq" in got else "")
        if head == "investigate" and len(rest) == 1:
            got = self.investigate(rest[0])
            if got["result"] == "question":
                return f"what is {got['subject']} {rest[0]}"
            if got["result"] == "need knowledge":
                return "need knowledge for " + " | ".join("+".join(h) for h in got["undecidable"])
            return got["result"]
        if head == "derive" and len(rest) == 2:
            got = self.derive(rest[0], rest[1])  # derive NAME SUBJECT
            return f"derived {got['fact']} ({len(got['proofs'])} proofs)" if got["status"] == "derived" else got["status"]
        if head == "correct" and rest and rest[0] == "example" and ":" in raw and "->" in raw:
            name = raw.split(":", 1)[0].split()[-1]
            lhs, rhs = raw.split(":", 1)[1].split("->")
            events = self.correct_example(name, lhs.strip(), rhs.strip())
            got = self.acquire(name)
            msg = f"corrected example {name}: {lhs.strip()} -> {rhs.strip()}; {got['result']} {name}"
            return msg + (f" {'+'.join(got['seq'])}" if "seq" in got else "") + (f"; {'; '.join(events)}" if events else "")
        if head == "correct" and len(rest) == 3:
            got = self.correct(*rest)
            return f"corrected {' '.join(rest)}; removed {len(got['removed'])}" + \
                (f"; {'; '.join(got['review'])}" if got["review"] else "")
        if head == "retract" and len(rest) in (2, 3):
            got = self.retract(*rest)
            return f"retracted {len(got['removed'])}" if got["removed"] else "nothing to retract"
        if head == "revoke" and len(rest) == 1:
            ev = self.revoke(rest[0])
            return "; ".join(ev) if ev else "nothing to revoke"
        if head == "show" and len(rest) == 1:
            return self.show(rest[0])
        if head == "capabilities" and not rest:
            return "; ".join(f"{n} {self.show(n)}" for n in sorted(self.state["capabilities"])) or "none"
        if head == "why" and len(rest) == 2:
            return self.explain(*rest)
        if (head == "what" and len(rest) == 3 and rest[0] == "is") or (head == "ask" and len(rest) == 2):
            s, w = rest[-2], rest[-1]
            return self.say(s, self.answer(s, w))
        q = self.match_question(parts)
        if q:
            return self.say(q[0], self.answer(*q))
        fact = self.read(raw)
        if fact:
            self.tell(*fact, source="sentence")
            return f"recorded {' '.join(fact)}"
        return "unparsed"


def main(argv) -> int:
    if len(argv) < 2:
        print("usage: python -m packetlm.engine STATE 'line' ['line' ...]")
        return 2
    t0 = time.process_time()
    flags = {"--no-library": ("use_library", False), "--no-geometry": ("geometry", False)}
    kw = dict(flags[a] for a in argv if a in flags)
    for a in argv:
        if a.startswith("--deepen="):
            kw["deepen"] = int(a.split("=", 1)[1])
    argv = [a for a in argv if a not in flags and not a.startswith("--deepen=")]
    eng = Engine.open(argv[0], **kw)
    replies = [eng.turn(line) for line in argv[1:]]
    eng.save()
    print(json.dumps({"load": eng.report, "replies": replies, "stats": eng.stats,
                      "cpu_s": round(time.process_time() - t0, 4)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
