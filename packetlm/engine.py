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
import resource
import sys
import time
from itertools import product
from pathlib import Path
from .field import bind, partial, pack, bits_for
from .packets import Packet
from .roles import induce, select
from . import reference
from . import retention as ret_mod
from . import programs as progs

SCHEMA = "packetlm.engine/3"  # packets are derived by bind, never stored
SCHEMA_V2 = "packetlm.engine/2"  # stored per-fact packets; accepted only to migrate, fully checked
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


MAX_ITER = 8


def _deps_of(seq):
    out = []
    for s in seq:
        if s.startswith("cap:"):
            out.append(s)
        elif s.startswith("prog:"):
            out += progs.deps(s)  # capabilities used inside an acquired G48 program
    return out


def _split_cap(step):
    name, v = step[4:].rsplit("@", 1)
    return name, int(v)


def validate(doc) -> dict:
    """Full nested validation. Schema 3 facts carry no packet (bind is derived on demand);
    a schema-2 document is accepted only for migration and its stored packets must bind."""
    _need(isinstance(doc, dict) and doc.get("schema") in (SCHEMA, SCHEMA_V2), "schema mismatch")
    v2 = doc["schema"] == SCHEMA_V2
    state = doc.get("state")
    _need(isinstance(state, dict), "state missing")
    _need(doc.get("checksum") == _checksum(state), "checksum mismatch")
    types = {"turn": int, "facts": list, "log": list, "library": list, "lexicon": dict,
             "capabilities": dict, "observations": dict, "retired": dict, "hypotheses": dict}
    for key, typ in types.items():
        _need(isinstance(state.get(key), typ), f"bad field {key}")
    if "retention" in state:
        ret = state["retention"]
        _need(isinstance(ret, dict) and isinstance(ret.get("call"), int) and isinstance(ret.get("touch"), dict)
              and isinstance(ret.get("archived"), dict), "bad retention record")
        for sha, e in ret["archived"].items():
            _need(isinstance(e.get("tokens"), list) and len(sha) == 64, f"bad archive entry {sha[:12]}")
    ids = set()
    for f in state["facts"]:
        keys = {"id": str, "s": str, "r": str, "o": str, "supports": list}
        if v2:
            keys.update({"bits": str, "count": int})
        for key, typ in keys.items():
            _need(isinstance(f.get(key), typ), f"bad fact key {key}")
        if not v2:
            _need("bits" not in f and "count" not in f, f"schema 3 stores no packet; bind is derived: {f.get('id')}")
        _need(f["id"] == f"{f['s']} {f['r']} {f['o']}", f"bad fact id {f['id']}")
        _need(f["id"] not in ids, f"duplicate fact {f['id']}")
        ids.add(f["id"])
        if v2:
            pkt = bind(f["s"], f["r"], f["o"])
            _need(pkt.bits.hex() == f["bits"] and pkt.count == f["count"], f"packet does not bind {f['id']}")
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
    def __init__(self, path, state=None, report=None, geometry=True, use_library=True, deepen=None, activation=True,
                 operators=False, retention="static", programs=False):
        self.path = Path(path)
        self.state = state if state is not None else empty_state()
        self.report = report or {"loaded": "new"}
        self.geometry = geometry
        self.use_library = use_library
        self.deepen = deepen  # None: fixed depth 2. int: iterative deepening up to this length
        # activation: candidate programs whose image of the observed subjects becomes empty
        # predict nothing on any observation (undetermined, zero support). They are not
        # evaluated one by one; they are kept as a counted complement ("pruned"). Exact.
        self.activation = activation
        # operators: also hypothesise bounded, predicate-terminated iteration steps
        # `op:until:R:Q:T` (follow R, 1..MAX_ITER steps, stop at the first node x with
        # x Q T). R, Q and T are proposed from the data (T from properties shared by the
        # observed answers), not supplied per domain.
        self.operators = operators
        # programs: G48 acquisition over the designed program grammar of packetlm/programs.py
        # (guards, ordered choice, tail recursion); the structure itself is acquired.
        self.programs = programs
        self.stats = {"evaluations": 0, "executions": 0, "row_ops": 0, "asks": 0}
        self._cache = None
        self._known_bytes = None  # sha256 of the primary bytes this process validated or wrote
        # retention: "static" keeps everything hot; "adaptive" archives rarely touched
        # knowledge components (docs/ARET.md) and restores them before any line naming them.
        _need(retention in ("static", "adaptive"), f"bad retention {retention}")
        self.retention = retention
        self._archive_dir = self.path.with_name(self.path.name + ".archive")
        self._archived_tok = None
        ret = self.state.get("retention")
        if ret and retention == "static" and ret["archived"]:
            for sha in sorted(ret["archived"]):
                ret_mod.restore(self.state, ret, self._archive_dir, sha)
            self.report["restored_all"] = "static retention: every archived component restored"
        if retention == "adaptive":
            self.state.setdefault("retention", ret_mod.empty())["call"] += 1

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
                raw = p.read_bytes()
                doc = json.loads(raw)
                state = validate(doc)
            except (ValueError, StateError) as exc:
                errors[label] = str(exc)
                continue
            report = {"loaded": label}
            if label == "backup":
                report["recovered"] = True
                report["primary_error"] = errors["primary"]
            if doc["schema"] == SCHEMA_V2:  # explicit, reported migration; the v2 file becomes the backup on save
                for f in state["facts"]:
                    del f["bits"], f["count"]
                report["migrated"] = f"{SCHEMA_V2} -> {SCHEMA}: {len(state['facts'])} stored packets checked and dropped"
            eng = cls(path, state, report, **kw)
            if label == "primary" and doc["schema"] == SCHEMA:
                eng._known_bytes = hashlib.sha256(raw).hexdigest()
            return eng
        raise StateError(f"no valid state: {errors}")

    def save(self) -> None:
        if self.retention == "adaptive":
            for comp, why in ret_mod.decide(self.state, self.state["retention"]):
                ret_mod.archive(self.state, self.state["retention"], self._archive_dir, comp, why)
                self.stats["archived"] = self.stats.get("archived", 0) + 1
                self._dirty()
                self._archived_tok = None
        validate({"schema": SCHEMA, "checksum": _checksum(self.state), "state": self.state})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            try:
                cur = self.path.read_bytes()
                if hashlib.sha256(cur).hexdigest() != self._known_bytes:  # bytes this process did not validate
                    validate(json.loads(cur))
                _write_atomic(self.path.with_name(self.path.name + ".bak"), cur)
            except (ValueError, StateError):
                pass  # never back up a corrupt primary over a good backup
        doc = {"schema": SCHEMA, "checksum": _checksum(self.state), "state": self.state}
        data = json.dumps(doc).encode()
        _write_atomic(self.path, data)
        self._known_bytes = hashlib.sha256(data).hexdigest()
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
            out = {}
            for s_, r_, _ in triples:
                out.setdefault(s_, set()).add(r_)
            self._cache = {"names": names, "pos": pos, "decode": decode, "rows": {}, "out": out,
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
        fact = {"id": f"{s} {r} {o}", "s": s, "r": r, "o": o, "supports": [support]}
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
        against the procedure. After the knowledge change the capability is
        requalified on the evidence that remains (`_requalify`); the qualification it
        earned earlier stays in `qualified_at` and `history`."""
        ids = set(ids)
        events = []
        self._retired_names = getattr(self, "_retired_names", set())
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
                    self._retired_names.add(name)
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
        out["review"] = retired + self.review() + self._requalify_retired()
        return out

    def _requalify_retired(self) -> list[str]:
        names, self._retired_names = sorted(getattr(self, "_retired_names", set())), set()
        events = []
        for n in names:
            events += self._requalify(n)
        return events

    def _requalify(self, name) -> list[str]:
        """Current evidential status of the current version, from the examples still active."""
        ver = self.version(name)
        if not ver or ver["status"] not in EXEC_OK:
            return []
        obs = self.state["observations"].get(name, [])
        if not obs:
            return self._set_status(name, ver["v"], "provisional", "evidence retired: no active examples")
        h = self.evaluate(ver["seq"], obs)
        if h["status"] == "contradicted":
            return self._set_status(name, ver["v"], "suspended", "contradicted by its observations")
        if h["status"] != "supported":
            return self._set_status(name, ver["v"], "provisional", "evidence retired: active examples do not all support it")
        horizon = self.deepen or ver.get("evidence", {}).get("horizon") or len(ver["seq"])
        scan = self._scan(name, ver["seq"], horizon)
        blocking = scan.pop("blocking")
        rec = self.state["hypotheses"].setdefault(name, {"live": []})
        rec.update({"candidate": ver["seq"], "blocking": blocking, "scan": scan})
        status = "provisional" if blocking else "qualified"
        return self._set_status(name, ver["v"], status,
                                f"requalified on {len(obs)} active examples after evidence retirement ({scan['blocking_n']} blocking)")

    def correct(self, s, r, o) -> dict:
        ids = [f["id"] for f in self._find(s, r) if f["o"] != o]
        retired = self._retire(ids, f"correct {s} {r} {o}") if ids else []
        out = self._drop(ids, f"correct {s} {r} {o}") if ids else {"removed": [], "proofs_dropped": 0}
        self.tell(s, r, o, source="correction")
        out["review"] = retired + self.review() + self._requalify_retired()
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
            if "packets" not in idx:  # derived on demand, never stored (schema 3)
                idx["packets"] = [bits_for(f["s"], 0) ^ bits_for(f["r"], 1) ^ bits_for(f["o"], 2)  # == bind(...) as int
                                  for f in self.state["facts"]]
            for p in idx["packets"]:
                if 2 * (qi & p).bit_count() - p.bit_count() <= 0:  # Packet.score
                    continue
                got = idx["decode"].get(pack(p ^ qi).bits)
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
            elif step.startswith("op:"):
                out.append(step[3:])
            elif step.startswith("prog:"):
                for d in progs.deps(step):
                    dn, dv = _split_cap(d)
                    ver = self.version(dn, dv)
                    if not ver or ver["status"] not in PINNED_OK:
                        return None
                out.append(step)
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
                if f"cap:{name}@{v}" in _deps_of(ver["seq"]):
                    out.append((n, ver["v"]))
        return out

    def _set_status(self, name, v, status, reason):
        ver = self.version(name, v)
        if ver["status"] == status:
            return []
        ver["status"] = status
        if status == "qualified":
            ver.setdefault("qualified_at", []).append(self.state["turn"])  # historical, kept apart from current status
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
        base = self.expand(seq) if any(s.startswith(("rel:", "cap:", "op:", "prog:")) for s in seq) else list(seq)
        if base is None:
            return None
        idx = self._idx()
        if subject not in idx["pos"]:
            return set()
        if any(b.startswith("prog:") for b in base):  # G48 programs run symbolically
            front = {subject}
            for b in base:
                if b.startswith("prog:"):
                    nxt = set()
                    for y in front:
                        nxt |= self._run_prog(b, y)
                    front = nxt
                else:
                    front = self._step_set(front, b)
                if not front:
                    return set()
            return front
        if not self.geometry:
            return reference.run(idx["ref"], base, subject)
        g = _geom()
        row = 1 << idx["pos"][subject]
        for rel in base:
            row = self._step_row(row, rel)
            if not row:
                return set()
        return {idx["names"][i] for i in g.bits(row)}

    def _prog_ctx(self):
        idx = self._idx()
        if "prog_ctx" not in idx:
            ref = {q: m for q, m in idx["ref"].items() if not q.startswith("cap:")}
            idx["prog_ctx"] = progs.Ctx(ref, cap=lambda tok, z: self.execute([tok], z) or set())
        return idx["prog_ctx"]

    def _component(self, seeds):
        """Entities connected to `seeds` by told facts in either direction (exact BFS)."""
        idx = self._idx()
        if "adj" not in idx:
            adj = {}
            for f in self.state["facts"]:
                if f["r"].startswith("cap:"):
                    continue
                adj.setdefault(f["s"], set()).add(f["o"])
                adj.setdefault(f["o"], set()).add(f["s"])
            idx["adj"] = adj
        adj, seen, todo = idx["adj"], set(seeds), list(seeds)
        while todo:
            for y in adj.get(todo.pop(), ()):
                if y not in seen:
                    seen.add(y)
                    todo.append(y)
        return seen

    def _run_prog(self, text, x):
        ctx = self._prog_ctx()
        before = ctx.steps
        out = progs.run(ctx, progs.parse(text), x)
        self.stats["row_ops"] += ctx.steps - before
        return set(out)

    def _mask(self, q, t):
        """Bit row of the entities x with a fact x q t (the predicate of an until step)."""
        idx = self._idx()
        key = ("mask", q, t)
        if key not in idx["rows"]:
            m = 0
            for x in idx["ref"].get(q, {}):
                if t in idx["ref"][q][x]:
                    m |= 1 << idx["pos"][x]
            idx["rows"][key] = m
        return idx["rows"][key]

    def _step_row(self, row, token):
        """One base step on a bit row. Plain relation: one composition. until:R:Q:T: for each
        start node, compose with R until a node in the predicate mask appears (first level
        only), at most MAX_ITER compositions, never revisiting nodes."""
        g = _geom()
        if not token.startswith("until:"):
            self.stats["row_ops"] += 1
            return g.compose([row], self._rows(token))[0]
        _, r, q, t = token.split(":")
        rows, mask, out = self._rows(r), self._mask(q, t), 0
        for i in g.bits(row):
            cur = seen = 1 << i
            for _ in range(MAX_ITER):
                nxt = g.compose([cur], rows)[0] & ~seen
                self.stats["row_ops"] += 1
                if not nxt:
                    break
                if nxt & mask:
                    out |= nxt & mask
                    break
                seen |= nxt
                cur = nxt
        return out

    def _step_set(self, front, token):
        """The same step on python sets (geometry disabled, scans, reference agreement)."""
        ref = self._idx()["ref"]
        if not token.startswith("until:"):
            m = ref.get(token, {})
            out = set()
            for x in front:
                out |= m.get(x, set())
            return out
        _, r, q, t = token.split(":")
        m, qm, out = ref.get(r, {}), ref.get(q, {}), set()
        for x in front:
            cur, seen = {x}, {x}
            for _ in range(MAX_ITER):
                nxt = set()
                for y in cur:
                    nxt |= m.get(y, set())
                nxt -= seen
                if not nxt:
                    break
                hits = {y for y in nxt if t in qm.get(y, ())}
                if hits:
                    out |= hits
                    break
                seen |= nxt
                cur = nxt
        return out

    def _rows(self, rel):
        idx = self._idx()
        if rel not in idx["rows"]:
            n = len(idx["names"])
            idx["rows"][rel] = _geom().rows_from([(idx["pos"][s], r, idx["pos"][o]) for s, r, o in idx["triples"] if r == rel], n, rel)
        return idx["rows"][rel]

    def _image(self, front, prim):
        """Activation: where a set of subjects goes under one program step.
        Geometric: one bit-row composition per base relation. Disabled: python sets."""
        base = self.expand([prim])
        if base is None:
            return None
        for rel in base:
            if self.geometry:
                front = self._step_row(front, rel)
            else:
                front = self._step_set(front, rel) if front else set()
                self.stats["row_ops"] += 1
            if not front:
                return front
        return front

    def _first_rel(self, prim):
        base = self.expand([prim])
        if not base:
            return None
        return base[0].split(":")[1] if base[0].startswith("until:") else base[0]

    def _activated(self, prims, n, start):
        """Programs of length n whose image of the start set never empties; returns (seqs, pruned)."""
        out, pruned, P = [], 0, len(prims)

        first = {p: self._first_rel(p) for p in prims}
        idx = self._idx()

        def walk(prefix, front):
            nonlocal pruned
            if len(prefix) == n:
                out.append(tuple(prefix))
                return
            ents = [idx["names"][i] for i in _geom().bits(front)] if self.geometry else front
            here = set().union(*(idx["out"].get(x, set()) for x in ents)) if ents else set()
            for p in prims:
                if first[p] not in here:  # relevance index: no edge leaves the frontier (exact)
                    pruned += P ** (n - len(prefix) - 1)
                    continue
                nxt = self._image(front, p)
                if not nxt:
                    pruned += P ** (n - len(prefix) - 1)
                    continue
                walk(prefix + [p], nxt)
        walk([], start)
        return out, pruned

    def proofs(self, base, subject):
        """All fact paths for a base program (symbolic enumeration, used for provenance)."""
        paths = [(subject, [])]
        for rel in base:
            nxt = []
            for cur, prem in paths:
                if rel.startswith("until:"):
                    nxt += self._until_paths(cur, prem, rel)
                    continue
                if rel.startswith("prog:"):
                    nxt += [(e, prem + p) for e, p in progs.trace(
                        progs.parse(rel), cur, self._find,
                        lambda tok, z: self.proofs(self.expand([tok]) or [], z))]
                    continue
                for f in self._find(cur, rel):
                    nxt.append((f["o"], prem + [f["id"]]))
            paths = nxt[:256]
        return paths

    def _until_paths(self, start, prem, token):
        """Fact paths of one until step: the R facts climbed and the predicate fact at the stop."""
        _, r, q, t = token.split(":")
        level, seen = [(start, prem)], {start}
        for _ in range(MAX_ITER):
            nxt = []
            for y, pr in level:
                for f in self._find(y, r):
                    if f["o"] not in seen:
                        nxt.append((f["o"], pr + [f["id"]]))
            if not nxt:
                return []
            hits = [(o, pr + [self._find(o, q, t)[0]["id"]]) for o, pr in nxt if self._find(o, q, t)]
            if hits:
                return hits
            seen |= {o for o, _ in nxt}
            level = nxt
        return []

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
        if self.operators:
            prims += self._operator_prims(name)
        return prims

    def _operator_prims(self, name):
        """until:R:Q:T steps. Predicates (Q, T) are the properties every observed answer
        shares; R ranges over the told relations other than Q."""
        ref = self._idx()["ref"]
        vals = {v for _, v in self.state["observations"].get(name, [])}
        common = None
        for v in vals:
            props = {(q, t) for q in ref if not q.startswith("cap:") for t in ref[q].get(v, ())}
            common = props if common is None else common & props
        rels = self.relations()
        return [f"op:until:{r}:{q}:{t}" for q, t in sorted(common or ()) for r in rels if r != q]

    def hypotheses(self, name, max_len=2, min_len=1, seen=None):
        obs = self.state["observations"].get(name, [])
        out, evaluated, contradicted = [], 0, 0
        self._pruned = 0
        seen = set() if seen is None else seen
        prims = self.primitives(name)
        pos = self._idx()["pos"]
        subjects = [s for s, _ in obs if s in pos]
        if self.geometry:
            start = 0
            for s in subjects:
                start |= 1 << pos[s]
        else:
            start = set(subjects)
        for n in range(min_len, max_len + 1):
            if self.activation:
                seqs, pr = self._activated(prims, n, start)
                self._pruned += pr
            else:
                seqs = product(prims, repeat=n)
            for seq in seqs:
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

    def _domain(self, seq):
        """Entities a program can be defined on: subjects of its first base step (exact)."""
        base = self.expand(seq) if any(x.startswith(("rel:", "cap:", "op:", "prog:")) for x in seq) else list(seq)
        if not base:
            return set()
        if base[0].startswith("prog:"):
            return set(self.entities())  # a program may begin with a guard: every entity
        first = base[0].split(":")[1] if base[0].startswith("until:") else base[0]
        return set(self._idx()["ref"].get(first, {}))

    def _predictions(self, seq):
        dom = self._domain(seq)
        out = {}
        for e in self.entities():
            if e not in dom:
                out[e] = None
                continue
            r = self.execute(seq, e)
            out[e] = next(iter(r)) if r and len(r) == 1 else None
        return out

    def _differs(self, seq, preds) -> bool:
        """Extensional difference from a prediction table; stops at the first entity that differs.
        Only entities where either side can be defined are checked (exact)."""
        dom = self._domain(seq)
        for e, v in preds.items():
            if v is None and e not in dom:
                continue
            r = self.execute(seq, e)
            if (next(iter(r)) if r and len(r) == 1 else None) != v:
                return True
        return False

    def acquire(self, name, max_len=None) -> dict:
        if self.programs and max_len is None:
            return self._acquire_programs(name)
        if max_len is None and self.deepen:
            live, evaluated, contradicted, seen = [], 0, 0, set()
            pruned = 0
            for n in range(1, self.deepen + 1):
                lv, ev, co = self.hypotheses(name, n, n, seen)
                live += lv
                evaluated += ev
                contradicted += co
                pruned += self._pruned
                if any(h["status"] == "supported" for h in live):
                    break  # deeper levels cannot remove a supported program
            searched = n
        else:
            searched = max_len or 2
            live, evaluated, contradicted = self.hypotheses(name, searched)
            pruned = self._pruned
        supported = [h for h in live if h["status"] == "supported"]
        record = {"turn": self.state["turn"], "evaluated": evaluated, "contradicted": contradicted, "searched_len": searched,
                  "pruned": pruned,
                  "live": live, "observations": len(self.state["observations"].get(name, []))}
        prior = self.state["hypotheses"].get(name, {})
        if prior.get("unanswered"):
            record["unanswered"] = prior["unanswered"]  # questions the oracle could not answer stay recorded
        self.state["hypotheses"][name] = record
        result = {"name": name, "evaluated": evaluated, "pruned": pruned, "live": len(live),
                  "zero_support": sum(1 for h in live if h["support"] == 0)}
        if len(supported) != 1:
            result["result"] = "ambiguous" if supported else "none"
            result["supported"] = [h["seq"] for h in supported]
            cur = self.version(name)
            if cur and cur["status"] == "qualified" and supported:
                self._set_status(name, cur["v"], "provisional", "several supported programs")
            return result
        cand = supported[0]
        horizon = self.deepen if (max_len is None and self.deepen) else searched
        scan = self._scan(name, cand["seq"], horizon)
        blocking = scan.pop("blocking")
        status = "provisional" if blocking else "qualified"
        record["candidate"] = cand["seq"]
        record["blocking"] = blocking
        record["scan"] = scan
        record["selection"] = "shortest supported program; qualified only if no alternative within the horizon blocks"
        evaluated += scan["evaluated"]
        record["evaluated"] = evaluated
        result["evaluated"] = evaluated
        result.update({"result": status, "seq": cand["seq"], "blocking": blocking, "scan": scan})
        result["version"], result["events"] = self._adopt(name, cand, status, blocking, scan)
        return result

    def _acquire_programs(self, name) -> dict:
        """G48: smallest supported program in the designed grammar (packetlm/programs.py).
        Supported programs that predict differently anywhere -> ambiguous (one representative
        per prediction class is kept for investigate). Otherwise the canonical first program
        is the candidate; the open-world scan up to its size decides qualified/provisional."""
        obs = [tuple(o) for o in self.state["observations"].get(name, [])]
        ctx = self._prog_ctx()
        # relevance (designed, docs/G48.md): the vocabulary and the domain are the connected
        # component(s) of the observed subjects and answers over told facts
        comp = self._component({x for o in obs for x in o})
        rels = sorted({r for r in self.relations() if any(x in comp for x in ctx.ref.get(r, {}))})
        caps = [p for p in self.primitives(name) if p.startswith("cap:")
                and any(s_ in comp for s_, _ in self.state["observations"].get(_split_cap(p)[0], []))]
        sub = {q: {x: ts for x, ts in m.items() if x in comp} for q, m in ctx.ref.items()}
        guards = progs.proposals(sub, obs)
        dom = sorted(e for e in self.entities() if e in comp)
        ind = progs.Inducer(ctx, obs, dom, (rels, caps), guards)
        ev0 = self.stats["evaluations"]
        k, sup = ind.search()
        classes = {}
        for p in sup:
            key = tuple(progs.one(progs.run(ctx, p, e)) for e in ind.domain)
            classes.setdefault(key, p)
        reps = list(classes.values())
        live = [{"seq": [progs.fmt(p)], "status": "supported", "support": len(obs)} for p in reps]
        record = {"turn": self.state["turn"], "evaluated": ind.examined, "contradicted": 0, "searched_len": k,
                  "pruned": 0, "live": live, "observations": len(obs), "grammar": "G48",
                  "supported_programs": len(sup), "guards": [list(g) for g in guards]}
        unanswered = self.state["hypotheses"].get(name, {}).get("unanswered")
        if unanswered:
            record["unanswered"] = unanswered  # questions the teacher could not answer stay recorded
        self.state["hypotheses"][name] = record
        self.stats["evaluations"] = ev0 + ind.examined
        result = {"name": name, "evaluated": ind.examined, "pruned": 0, "live": len(live), "zero_support": 0}
        if len(reps) != 1:
            result["result"] = "ambiguous" if reps else "none"
            result["supported"] = [h["seq"] for h in live]
            cur = self.version(name)
            if cur and cur["status"] == "qualified" and reps:
                self._set_status(name, cur["v"], "provisional", "several supported programs")
            return result
        cand = reps[0]
        cand_pred = {e: progs.run(ctx, cand, e) for e in ind.domain}
        blockers, complete, examined = ind.scan(cand, cand_pred, horizon=progs.size(cand))
        status = "qualified" if complete and not blockers else "provisional"
        scan = {"horizon": progs.size(cand), "domain": len(dom), "scanned": examined, "complete": complete,
                "budget": progs.SCAN_BUDGET, "blocking_n": len(blockers), "compatible": 0, "pruned_compatible": 0,
                "assumption": "G48 open world: every non-contradicted program up to the candidate's size is an "
                              "alternative; qualified only if that enumeration completes within the budget "
                              "with no blocker."}
        blocking = [[b] for b in blockers]
        h = {"seq": [progs.fmt(cand)], "status": "supported", "support": len(obs)}
        record.update({"candidate": h["seq"], "blocking": blocking, "scan": scan,
                       "selection": "smallest supported G48 program; qualified only if the open-world scan completes "
                                    "with no blocker"})
        record["evaluated"] = ind.examined + examined
        result.update({"result": status, "seq": h["seq"], "blocking": blocking, "scan": scan,
                       "evaluated": record["evaluated"]})
        result["version"], result["events"] = self._adopt(name, h, status, blocking, scan)
        return result

    ASSUMPTION = ("open world over current knowledge, horizon H: every non-contradicted program of length <= H is "
                  "an alternative, whatever its support. It blocks if it gives a defined value different from the "
                  "candidate's on some entity (conflict), or if it has support and differs anywhere (G44 rule). "
                  "A program whose image of the candidate's domain is empty cannot conflict there; it is counted "
                  "as compatible on current knowledge, not eliminated. New facts can create conflicts: "
                  "`requalify NAME` re-runs the check.")

    BLOCK_KEEP = 64

    def _scan(self, name, cand_seq, horizon) -> dict:
        """Check every program up to the horizon against the candidate (prefix-shared walk).
        Pruning here is computational: a pruned subtree is shown compatible on current knowledge
        (empty image of the candidate's domain), not shown false. Symbolic row lookups."""
        ref = self._idx()["ref"]
        obs = self.state["observations"].get(name, [])
        mine = self._predictions(cand_seq)
        cand_base = tuple(self.expand(cand_seq))
        D = [e for e, v in mine.items() if v is not None]
        want = [mine[e] for e in D]
        pos = {e: i for i, e in enumerate(D)}
        obs_at = [(pos[s_], v) for s_, v in obs if s_ in pos]
        prims = [(p, self.expand([p])) for p in self.primitives(name)]
        prims = [(p, b) for p, b in prims if b is not None]
        P = len(prims)
        out = {"horizon": horizon, "domain": len(D), "scanned": 0, "evaluated": 0, "contradicted": 0,
               "compatible": 0, "pruned_compatible": 0, "blocking_n": 0, "conflicts": 0, "assumption": self.ASSUMPTION}
        blocking = []

        def step(front, base):
            new = []
            for cur in front:
                for r in base:
                    if not cur:
                        break
                    cur = self._step_set(cur, r)
                new.append(cur)
            return new

        # breadth-first over distinct base sequences: programs with the same base have the
        # same extension, and the first visit is at the smallest primitive depth, so a later
        # duplicate's subtree is contained in the first one's (exact). The walk stops once
        # BLOCK_KEEP blockers are found: the status (any blocker -> provisional) is decided,
        # and the counts are then lower bounds (`truncated`).
        out.update({"duplicates": 0, "truncated": False})
        level, seen = [([], [{e} for e in D], ())], {()}
        first = {p: (pb[0].split(":")[1] if pb[0].startswith("until:") else pb[0]) for p, pb in prims}
        outrel = self._idx()["out"]
        for depth in range(1, horizon + 1):
            nxt_level = []
            for prefix, front, bseq in level:
                here = set()
                for f in front:
                    for x in f:
                        here |= outrel.get(x, set())
                for p, pb in prims:
                    key = bseq + tuple(pb)
                    if first[p] not in here:  # relevance index: nothing leaves the frontier (exact)
                        if key not in seen:
                            seen.add(key)
                            out["pruned_compatible"] += 1
                        continue
                    if key in seen:
                        out["duplicates"] += 1
                        continue
                    seen.add(key)
                    nf = step(front, pb)
                    if not any(nf):
                        out["pruned_compatible"] += 1  # a distinct-base node, standing for its whole subtree
                        continue
                    seq = prefix + [p]
                    out["scanned"] += 1
                    if key != cand_base:
                        vals = [next(iter(f)) if len(f) == 1 else None for f in nf]
                        out["evaluated"] += len(obs_at)
                        if any(vals[i] is not None and vals[i] != v for i, v in obs_at):
                            out["contradicted"] += 1
                        else:
                            support = sum(vals[i] == v for i, v in obs_at)
                            conflict = any(x is not None and x != w for x, w in zip(vals, want))
                            if conflict or (support >= 1 and self._differs(seq, mine)):
                                out["blocking_n"] += 1
                                out["conflicts"] += conflict
                                blocking.append(seq)
                                if len(blocking) >= self.BLOCK_KEEP:
                                    out["truncated"] = True
                                    return {**out, "blocking": blocking}
                            else:
                                out["compatible"] += 1
                    if depth < horizon:
                        nxt_level.append((seq, nf, key))
            level = nxt_level
        return {**out, "blocking": blocking}

    def _adopt(self, name, h, status, blocking, scan=None):
        cap = self.state["capabilities"].setdefault(name, {"current": None, "versions": [], "express": None})
        cur = self.version(name)
        evidence = {"observations": len(self.state["observations"].get(name, [])),
                    "support": h["support"], "blocking": len(blocking), "turn": self._tick()}
        if scan:
            evidence.update({"horizon": scan["horizon"], "blocking_total": scan["blocking_n"],
                             "compatible": scan["compatible"], "pruned_compatible": scan["pruned_compatible"]})
        if cur and self.expand(cur["seq"]) == self.expand(h["seq"]) and cur["status"] in EXEC_OK + ("suspended",):
            cur["evidence"] = evidence
            return cur["v"], self._set_status(name, cur["v"], status, "requalified")
        events = []
        if cur and cur["status"] in EXEC_OK:
            events += self._set_status(name, cur["v"], "superseded", f"replaced by v{len(cap['versions']) + 1}")
        ver = {"v": len(cap["versions"]) + 1, "seq": h["seq"], "base": self.expand(h["seq"]),
               "status": status, "evidence": evidence,
               "history": [{"turn": evidence["turn"], "status": status, "reason": "acquired"}]}
        if status == "qualified":
            ver["qualified_at"] = [evidence["turn"]]
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
        for extra in ([rec["candidate"]] if rec.get("candidate") else []) + rec.get("blocking", []):
            if extra not in live:
                live.append(extra)  # open-world blockers can be resolved by a question too
        if len(live) <= 1:
            return {"result": "settled"}
        done = {s for s, _ in self.state["observations"].get(name, [])} | set(rec.get("unanswered", []))
        preds = {tuple(h): self._predictions(h) for h in live}
        best, best_score = None, 0
        for e in self.entities():
            if e in done:
                continue
            if self.programs:
                # G48 (docs/G48.md, seed-33 mechanism): an answer v removes every hypothesis that
                # does not predict v, including those that predict nothing there, because a
                # supported program must support every observation. Worst case over defined v.
                allp = [p[e] for p in preds.values()]
                known = [v for v in allp if v is not None]
                if not known or len(set(allp)) < 2:
                    continue
                score = min(len(allp) - known.count(v) for v in set(known))
                if score > best_score:
                    best, best_score = e, score
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
        retired = len(self.state["retired"].get(name, []))
        active = len(self.state["observations"].get(name, []))
        return "; ".join(f"v{v['v']} {'+'.join(v['seq'])} {v['status']}" for v in cap["versions"]) + \
            (f"; current v{cap['current']}" if cap["current"] else "") + f"; examples {active} active, {retired} retired"

    # ---------- turns: one controlled-language interface for people and tests ----------

    def _retain(self, line: str) -> None:
        """Adaptive retention: restore every archived component this line can read, then
        record the touch. `capabilities` (a listing of everything) restores everything."""
        ret = self.state["retention"]
        toks = ret_mod.line_tokens(line, self.state)
        if ret["archived"]:
            if self._archived_tok is None:
                self._archived_tok = {t: sha for sha, e in ret["archived"].items() for t in e["tokens"]}
            want = set(ret["archived"]) if line.strip().lower() == "capabilities" else \
                {self._archived_tok[t] for t in toks if t in self._archived_tok}
            for sha in sorted(want):
                ret_mod.restore(self.state, ret, self._archive_dir, sha)
                self.stats["restored"] = self.stats.get("restored", 0) + 1
            if want:
                self._dirty()
                self._archived_tok = None
        ret_mod.touch(ret, toks)

    def turn(self, line: str) -> str:
        if self.retention == "adaptive":
            self._retain(line)
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
            if not got["removed"]:
                return "nothing to retract"
            return f"retracted {len(got['removed'])}" + (f"; {'; '.join(got['review'])}" if got["review"] else "")
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
    flags = {"--no-library": ("use_library", False), "--no-geometry": ("geometry", False),
             "--no-activation": ("activation", False), "--operators": ("operators", True),
             "--adaptive-retention": ("retention", "adaptive"), "--programs": ("programs", True)}
    kw = dict(flags[a] for a in argv if a in flags)
    for a in argv:
        if a.startswith("--deepen="):
            kw["deepen"] = int(a.split("=", 1)[1])
    argv = [a for a in argv if a not in flags and not a.startswith("--deepen=")]
    eng = Engine.open(argv[0], **kw)
    replies = [eng.turn(line) for line in argv[1:]]
    eng.save()
    print(json.dumps({"load": eng.report, "replies": replies, "stats": eng.stats,
                      "cpu_s": round(time.process_time() - t0, 4),
                      # whole-process CPU incl. interpreter startup and imports (verification M4)
                      "cpu_total_s": round(sum(resource.getrusage(resource.RUSAGE_SELF)[:2]), 4)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
