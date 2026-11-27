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
import copy
import hashlib
import bisect
import itertools
import json
import os
import re
import resource
import sys
import time
from collections import Counter
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


NONE, SEVERAL = "!none", "!several"  # PX teacher statements (docs/PX.md): not withheld, no / several values


def judge_set(out, ans):
    """Judge a full prediction set. A value answer is judged as before (open world: a missing
    value is undetermined). `!none` (the teacher states there is no value) contradicts any
    prediction with a value; `!several` contradicts a single value and is undetermined on
    nothing. Not executable (None) is always undetermined."""
    if out is None:
        return "undetermined"
    if ans == NONE:
        return "supported" if not out else "contradicted"
    if ans == SEVERAL:
        return "supported" if len(out) >= 2 else ("contradicted" if len(out) == 1 else "undetermined")
    return judge(next(iter(out)) if len(out) == 1 else None, ans)


def judge_closed(out, ans):
    """G49 `complete X` (docs/G49.md): the teacher states that every fact about every entity
    reachable from X is told. A program's output at X is then final, so an observation at X is
    judged closed-world: the prediction set must be exactly what was stated. Not executable (None)
    stays undetermined (a dependency, not a fact gap)."""
    if out is None:
        return "undetermined"
    if ans == NONE:
        return "supported" if not out else "contradicted"
    if ans == SEVERAL:
        return "supported" if len(out) >= 2 else "contradicted"
    return "supported" if out == {ans} else "contradicted"


def outcome(out):
    """The answer class a full prediction set stands for (PX investigate)."""
    if not out:
        return NONE
    return next(iter(out)) if len(out) == 1 else SEVERAL


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


def validate(doc, checksum_ok=False) -> dict:
    """Full nested validation. Schema 3 facts carry no packet (bind is derived on demand);
    a schema-2 document is accepted only for migration and its stored packets must bind.
    `checksum_ok`: the caller has already verified the checksum against the exact bytes the state
    was parsed from (see `_read_doc`); every other check still runs."""
    _need(isinstance(doc, dict) and doc.get("schema") in (SCHEMA, SCHEMA_V2), "schema mismatch")
    v2 = doc["schema"] == SCHEMA_V2
    state = doc.get("state")
    _need(isinstance(state, dict), "state missing")
    _need(checksum_ok or doc.get("checksum") == _checksum(state), "checksum mismatch")
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


def _valid_fast(doc, checksum_ok=False) -> bool:
    """G54 `--lean`: True exactly when `validate(doc, checksum_ok)` accepts a schema-3 document
    (the same checks, without a function call per check). On False the caller runs `validate`,
    which raises with its usual message. Equivalence is tested by fuzzing in g44 (g54 checks)."""
    if not (isinstance(doc, dict) and doc.get("schema") == SCHEMA):
        return False
    state = doc.get("state")
    if not isinstance(state, dict):
        return False
    if not (checksum_ok or doc.get("checksum") == _checksum(state)):
        return False
    for key, typ in (("turn", int), ("facts", list), ("log", list), ("library", list), ("lexicon", dict),
                     ("capabilities", dict), ("observations", dict), ("retired", dict), ("hypotheses", dict)):
        if not isinstance(state.get(key), typ):
            return False
    if "retention" in state:
        ret = state["retention"]
        if not (isinstance(ret, dict) and isinstance(ret.get("call"), int) and isinstance(ret.get("touch"), dict)
                and isinstance(ret.get("archived"), dict)):
            return False
        for sha, e in ret["archived"].items():
            if not (isinstance(e.get("tokens"), list) and len(sha) == 64):
                return False
    ids = set()
    for f in state["facts"]:
        g = f.get
        fid, fs, fr, fo, sup = g("id"), g("s"), g("r"), g("o"), g("supports")
        if not isinstance(fid, str) or not isinstance(fs, str) or not isinstance(fr, str) \
                or not isinstance(fo, str) or not isinstance(sup, list):
            return False
        if "bits" in f or "count" in f or fid != f"{fs} {fr} {fo}" or fid in ids or not sup:
            return False
        ids.add(fid)
        for sp in sup:
            if not (sp.get("kind") in ("told", "derived") and isinstance(sp.get("premises"), list)
                    and isinstance(sp.get("turn"), int)):
                return False
    for f in state["facts"]:
        for sp in f["supports"]:
            for q in sp["premises"]:
                if q not in ids:
                    return False
    for c in state["library"]:
        kind = c.get("kind", "svo")
        if kind == "svo":
            if not {"order", "rel_at", "word", "meaning"} <= set(c):
                return False
        elif not (kind == "question" and isinstance(c.get("template"), list) and "meaning" in c):
            return False
    for word, target in state["lexicon"].items():
        if not (isinstance(word, str) and isinstance(target, str)):
            return False
    for name, rs in state["retired"].items():
        if not all(isinstance(x, dict) and {"s", "o", "reason"} <= set(x) for x in rs):
            return False
    for name, obs in state["observations"].items():
        if not all(isinstance(o, list) and len(o) == 2 for o in obs):
            return False
    caps = state["capabilities"]
    for name, cap in caps.items():
        if not isinstance(cap.get("versions"), list):
            return False
        cur = cap.get("current")
        if not (cur is None or 1 <= cur <= len(cap["versions"])):
            return False
        for i, ver in enumerate(cap["versions"], 1):
            if not (ver.get("v") == i and ver.get("status") in VER_STATUS and ver.get("seq")):
                return False
            for d in _deps_of(ver["seq"]):
                dn, dv = _split_cap(d)
                if not (dn in caps and 1 <= dv <= len(caps[dn]["versions"])):
                    return False
    try:
        def visit(node, stack):
            if node in stack:
                raise StateError("cycle")
            name, v = _split_cap(node)
            for d in _deps_of(caps[name]["versions"][v - 1]["seq"]):
                visit(d, stack | {node})
        for name, cap in caps.items():
            for ver in cap["versions"]:
                visit(f"cap:{name}@{ver['v']}", set())
    except StateError:
        return False
    return True


def _valid_scoped(state, touched, byid, caps_scope=None, obs_scope=None) -> bool:
    """G57b change-scoped validation: `_valid_fast`'s checks with the per-fact checks run only on the
    facts this call appended or gave a new support (`touched`), premises resolved through the
    persistent index (`byid`, the ids of every fact). Sound only when the call removed nothing and
    every fact change went through `tell` (Memo.scope["ok"]); a full validation runs every
    FULL_VALIDATE_EVERY mutating calls and at every snapshot, and checks the index too."""
    if not isinstance(state, dict):
        return False
    for key, typ in (("turn", int), ("facts", list), ("log", list), ("library", list), ("lexicon", dict),
                     ("capabilities", dict), ("observations", dict), ("retired", dict), ("hypotheses", dict)):
        if not isinstance(state.get(key), typ):
            return False
    if "retention" in state:
        ret = state["retention"]
        if not (isinstance(ret, dict) and isinstance(ret.get("call"), int) and isinstance(ret.get("touch"), dict)
                and isinstance(ret.get("archived"), dict)):
            return False
        for sha, e in ret["archived"].items():
            if not (isinstance(e.get("tokens"), list) and len(sha) == 64):
                return False
    for f in touched:
        if byid.get(f.get("id")) is not f:
            return False
        g = f.get
        fid, fs, fr, fo, sup = g("id"), g("s"), g("r"), g("o"), g("supports")
        if not isinstance(fid, str) or not isinstance(fs, str) or not isinstance(fr, str) \
                or not isinstance(fo, str) or not isinstance(sup, list):
            return False
        if "bits" in f or "count" in f or fid != f"{fs} {fr} {fo}" or not sup:
            return False
        for sp in sup:
            if not (sp.get("kind") in ("told", "derived") and isinstance(sp.get("premises"), list)
                    and isinstance(sp.get("turn"), int)):
                return False
    for f in touched:
        for sp in f["supports"]:
            for q in sp["premises"]:
                if q not in byid:
                    return False
    for c in state["library"]:
        kind = c.get("kind", "svo")
        if kind == "svo":
            if not {"order", "rel_at", "word", "meaning"} <= set(c):
                return False
        elif not (kind == "question" and isinstance(c.get("template"), list) and "meaning" in c):
            return False
    for word, target in state["lexicon"].items():
        if not (isinstance(word, str) and isinstance(target, str)):
            return False
    for name, rs in state["retired"].items():
        if not all(isinstance(x, dict) and {"s", "o", "reason"} <= set(x) for x in rs):
            return False
    # G58 (`--routed`): the observation and capability checks only on what this call wrote
    # (`obs_scope`, `caps_scope`: names); versions are append-only and their seqs never change, so a
    # new dependency cycle must pass through a version written in this call. The periodic full
    # validation (FULL_VALIDATE_EVERY) covers the rest, as for facts.
    for name, obs in (state["observations"].items() if obs_scope is None
                      else ((n, state["observations"][n]) for n in obs_scope if n in state["observations"])):
        if not all(isinstance(o, list) and len(o) == 2 for o in obs):
            return False
    caps = state["capabilities"]
    if caps_scope is not None and any(n not in caps for n in caps_scope):
        return False
    for name, cap in (caps.items() if caps_scope is None else ((n, caps[n]) for n in caps_scope)):
        if not isinstance(cap.get("versions"), list):
            return False
        cur = cap.get("current")
        if not (cur is None or 1 <= cur <= len(cap["versions"])):
            return False
        for i, ver in enumerate(cap["versions"], 1):
            if not (ver.get("v") == i and ver.get("status") in VER_STATUS and ver.get("seq")):
                return False
            for d in _deps_of(ver["seq"]):
                dn, dv = _split_cap(d)
                if not (dn in caps and 1 <= dv <= len(caps[dn]["versions"])):
                    return False
    try:
        def visit(node, stack):
            if node in stack:
                raise StateError("cycle")
            name, v = _split_cap(node)
            for d in _deps_of(caps[name]["versions"][v - 1]["seq"]):
                visit(d, stack | {node})
        for name, cap in (caps.items() if caps_scope is None else ((n, caps[n]) for n in caps_scope)):
            for ver in cap["versions"]:
                visit(f"cap:{name}@{ver['v']}", frozenset())  # (scoped copy)
    except StateError:
        return False
    return True



# G58 audit (tests only, docs/G58.md §2d): when on, every routed shortcut is recomputed the
# unrouted way at each use and a difference is logged. Off in every registered run.
G58_AUDIT = {"on": False, "log": []}


def _g58_violation(kind, detail):
    G58_AUDIT["log"].append((kind, str(detail)[:200]))


FULL_VALIDATE_EVERY = 64  # G57b, registered: mutating calls between full validations (also at every snapshot)


def validate_lean(doc, checksum_ok=False) -> dict:
    if _valid_fast(doc, checksum_ok):
        return doc["state"]
    return validate(doc, checksum_ok)


def _lean_prefix(schema, checksum) -> bytes:
    return ('{"schema": ' + json.dumps(schema) + ', "checksum": ' + json.dumps(checksum) + ', "state": ').encode()


_DOC_PREFIX = re.compile(rb'\{"schema": ("[^"\\]*"), "checksum": ("[0-9a-f]{64}"), "state": ')
_DECODER = json.JSONDecoder()


def _read_doc(raw: bytes):
    """Parse a state document once; returns (doc, checksum_ok).

    checksum_ok is True exactly when the file is `prefix + T + "}"` (the layout every save writes),
    T parses as one JSON value that ends right before the closing brace (so nothing, such as a
    duplicate top-level key, follows it: verification Low 1 of 3e2783c), and sha256(T) equals the
    stored checksum. A G54/G56 lean save writes T as the state's insertion-order text and stores
    sha256(T); a non-lean save stores the canonical checksum, for which this test is usually False
    and `validate` recomputes it. Any other file is parsed by json.loads with checksum_ok False."""
    m = _DOC_PREFIX.match(raw)
    if m and raw.endswith(b"}"):
        try:
            text = raw.decode()
            state, end = _DECODER.raw_decode(text, m.end())  # the prefix is ASCII: byte = char offset
        except ValueError:
            state, end = None, -1
        if end == len(text) - 1:
            doc = {"schema": json.loads(m.group(1)), "checksum": json.loads(m.group(2)), "state": state}
            ok = hashlib.sha256(raw[m.end():-1]).hexdigest() == doc["checksum"]
            return doc, ok
    return json.loads(raw), False


def _write_atomic(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


SMALL_PACKET = 38  # G57b: packets below this popcount are always recall candidates (Memo.recall_candidates)
# G59 (`--partitioned`, docs/G59.md §2): packets below this popcount are always candidates of the
# partitioned recall; every code's bits are split into PAIR_GROUPS groups (consecutive in bit
# order) and each pair of bits inside a group is indexed
SMALL_PART = 42
PAIR_GROUPS = 4
_CODE_BITS = {}


def _code_bits(code):
    """(int, ascending bit positions) of bits_for(token, role) for a code (role, token); memoized
    (a pure function of the code)."""
    got = _CODE_BITS.get(code)
    if got is None:
        x = bits_for(code[1], code[0])
        got = _CODE_BITS[code] = (x, _geom().bits(x))
    return got


def _code_pairs(pos):
    """The indexed bit pairs of a code: pairs inside each of PAIR_GROUPS consecutive groups of its
    ascending bit positions (a code has <= 16 bits, so groups of 4)."""
    g = -(-len(pos) // PAIR_GROUPS) if pos else 1
    out = []
    for k in range(0, len(pos), g):
        grp = pos[k:k + g]
        for i in range(len(grp)):
            for j in range(i + 1, len(grp)):
                out.append(grp[i] * 4096 + grp[j])
    return out


def _fresh_index(facts) -> dict:
    """The reference build of `Engine._idx`'s core structures (for the G57b guard)."""
    names, pos, triples = [], {}, []
    for f in facts:
        for t in (f["s"], f["o"]):
            if t not in pos:
                pos[t] = len(names)
                names.append(t)
        triples.append((f["s"], f["r"], f["o"]))
    out = {}
    for s_, r_, _ in triples:
        out.setdefault(s_, set()).add(r_)
    return {"names": names, "pos": pos, "out": out, "triples": triples, "ref": reference.index(triples),
            "byid": {f["id"]: f for f in facts}}


class SparseRows(dict):
    """G57b: a relation's bit rows as {entity position: row}; missing positions are empty rows, as
    in the dense list `geom.rows_from` returns (`geom.compose` only indexes set positions)."""

    def __missing__(self, key):
        return 0


class Memo:
    """G57 (`--indexed`): exact caches that outlive one call when a long-lived server keeps them
    (packetlm/serve.py), and are fresh per process otherwise. They hold no state and never change a
    reply (docs/G57.md §2).

    - `base`: the multiset of fact triples the caches reflect. `sync` (run whenever the engine builds
      its fact index) applies the difference to the current triples, so the caches always agree
      with the index that the per-call engine itself would use.
    - `stamp[r]`: bumped whenever a triple with relation r is added or removed.
    - `recall[(s, r)]`: the triples whose packets pass the geometric recall test for the query
      (s, r), i.e. 2|q&p| - |p| > 0. Recall is decided by exactly these packets, so a new or removed
      triple changes the entry only if its own packet passes; each is tested once.
    - `answers[(s, word)]`: (fingerprint, answer) for re-asks inside read-only calls."""

    def __init__(self):
        self.base = Counter()
        self.last = []
        self.stamp = {}
        self.tick = 0
        self.recall = {}
        self.answers = {}
        self.pk = {}
        self.pkl = []  # (packet, popcount) of each triple in `last`, in order
        self.uf = None  # union-find over non-cap fact edges; None = rebuild on next use
        # G57b (`--incremental`): the fact index kept across calls, maintained by the engine's own
        # fact-changing paths (`tell` appends and supports); any removal discards it (rebuilt on
        # next use). `scope` records what the current call changed, for change-scoped validation.
        self.ix = None
        self.scope = None
        self.ix_checks = 0
        self.counts = Counter()  # G57b: how often each path ran (tests show every path is exercised)
        # G58 (`--routed`): `rv[name]` = the fingerprint of everything `evaluate` read the last time
        # `review` found the capability's current version not contradicted; `clo[(n, v, seq)]` the
        # dependency closure of a version (a version's seq never changes, and it is part of the key)
        self.rv = {}
        self.rvx = None  # G58: the last review's generation, tick, closed set and relation -> names map
        self.rv_obs = set()  # G58: capabilities whose observations changed since the last review
        self.rv_dirty = set()  # G58: (name, v) whose status changed, and names with a new version, since then
        self.clo = {}
        # `lib_gen` is bumped by every write that can change what `primitives` offers (a status change,
        # a new version); `lib` caches the offered capabilities and the routing tables per generation
        self.lib_gen = 0
        self.pin_gen = 0  # G58: bumped when a version enters or leaves PINNED_OK (what `expand` checks)
        self.pfirst = {}  # G58: primitive -> (pin_gen, base, first relation)
        self.lib = {}
        self.pb = {}  # G58: (name, v, seq) -> the version's expanded base, valid while every status is PINNED_OK
        # G58 capability index (`Engine._cx`): the offered capabilities in name order, by first base
        # relation, and by dependency; `cx_dirty` = names whose record changed since the last sync
        self.cx = None
        self.cx_dirty = set()
        # G58 seeds index (`Engine._sx`, for `_flush_growth`): entity -> names whose current version's
        # domain or observed subjects hold it; and the union-find classes' members, when tracked
        self.sx = None
        self.sx_dirty = set()
        self.track_members = False
        self.members = None
        # G59 (`--partitioned`): the persistent index also keeps the code-pair index, and the seeds
        # index is kept in step at the end of every call
        self.partitioned = False

    def packet_of(self, t):
        p = self.pk.get(t)
        if p is None:
            p = self.pk[t] = self.packet(t)
        return p

    def _find(self, x):
        uf = self.uf
        root = x
        while uf[root] != root:
            root = uf[root]
        while uf[x] != root:
            uf[x], x = root, uf[x]
        return root

    def _union(self, a, b):
        uf = self.uf
        uf.setdefault(a, a)
        uf.setdefault(b, b)
        ra, rb = self._find(a), self._find(b)
        if ra != rb:
            new, old = min(ra, rb), max(ra, rb)
            uf[old] = new
            m = self.members
            if m is not None:  # G58: class members, merged small into large
                x, y = m.pop(old, None) or [old], m.get(new) or [new]
                if len(x) > len(y):
                    x, y = y, x
                y.extend(x)
                m[new] = y

    # ---------- G57b: persistent fact index ----------

    CORE = ("names", "pos", "decode", "out", "triples", "ref", "byid")

    def ix_valid(self, state) -> bool:
        ix = self.ix
        return ix is not None and state["facts"] is ix["facts_ref"] and len(state["facts"]) == ix["n_facts"] \
            and state.get("fact_epoch", 0) == ix["epoch"]

    def ix_adopt(self, state, cache) -> None:
        """Take a freshly built per-call index (the reference build) as the persistent one, and add
        the G57b structures to it. O(state), once per rebuild."""
        self.counts["ix_rebuilds"] += 1
        ix = {k: cache[k] for k in self.CORE}
        if ix["decode"] is None:
            ix["decode"] = {pack(bits_for(t, 2)).bits: t for t in ix["names"]}
        ix.update(facts_ref=state["facts"], n_facts=len(state["facts"]), epoch=state.get("fact_epoch", 0),
                  by_rel={}, by_s={}, by_o={}, by_sr={}, told_rel=Counter(), prow={}, codes=set(), codebits={}, small=[])
        if self.partitioned:
            ix.update(pairs={}, small_part=[])
        self.ix = ix
        for f in state["facts"]:
            self._ix_add(f)

    def _ix_add(self, f) -> None:
        ix = self.ix
        t = (f["s"], f["r"], f["o"])
        ix["by_rel"].setdefault(t[1], []).append(t)
        ix["by_s"].setdefault(t[0], []).append(t)
        ix["by_o"].setdefault(t[2], []).append(t)
        ix["by_sr"].setdefault((t[0], t[1]), []).append(f)
        if not t[1].startswith("cap:") and any(sp["kind"] == "told" for sp in f["supports"]):
            ix["told_rel"][t[1]] += 1
        ix["prow"].pop(t[1], None)
        pairs = ix.get("pairs")
        for code in ((0, t[0]), (1, t[1]), (2, t[2])):
            if code not in ix["codes"]:
                ix["codes"].add(code)
                _, pos = _code_bits(code)
                for b in pos:
                    ix["codebits"].setdefault(b, []).append(code)
                if pairs is not None:  # G59: the code's group pairs
                    for k in _code_pairs(pos):
                        pairs.setdefault(k, []).append(code)
        pc = self.packet_of(t).bit_count()
        if pc < SMALL_PACKET:
            ix["small"].append(t)
        if pairs is not None and pc < SMALL_PART:
            ix["small_part"].append(t)

    def ix_append(self, f, state) -> None:
        """`tell` appended f (the index was valid just before): the reference build's structures
        in the same insertion order, the G57b structures, and the memo's recall/stamps/components."""
        ix = self.ix
        self.counts["ix_appends"] += 1
        t = (f["s"], f["r"], f["o"])
        if f["id"] in ix["byid"] and self.scope is not None:
            self.scope["ok"] = False  # a duplicate id: leave it to the full validator
        for x in (t[0], t[2]):
            if x not in ix["pos"]:
                ix["pos"][x] = len(ix["names"])
                ix["names"].append(x)
                ix["decode"][pack(bits_for(x, 2)).bits] = x
        ix["triples"].append(t)
        ix["out"].setdefault(t[0], set()).add(t[1])
        ix["ref"].setdefault(t[1], {}).setdefault(t[0], set()).add(t[2])
        ix["byid"][f["id"]] = f
        self._ix_add(f)
        ix["n_facts"], ix["epoch"] = len(state["facts"]), state.get("fact_epoch", 0)
        self._added(t)

    def ix_support(self, f, was_told) -> None:
        if not was_told and not f["r"].startswith("cap:") and any(sp["kind"] == "told" for sp in f["supports"]):
            self.ix["told_rel"][f["r"]] += 1

    def _added(self, t) -> None:
        """Memo.sync for one appended triple, without a pass over the others."""
        self.tick += 1
        self.stamp.pop(t[1], None)  # G59: stamps kept in increasing order (moved to the end when bumped)
        self.stamp[t[1]] = self.tick
        p = self.packet_of(t)
        for (s_, r_), ent in self.recall.items():
            if self.passes(bits_for(s_, 0) ^ bits_for(r_, 1), p):
                ent[t] += 1
        if self.uf is not None and not t[1].startswith("cap:"):
            self._union(t[0], t[2])
        self.pkl.append((p, p.bit_count()))
        self.base[t] += 1
        self.last.append(t)

    def recall_candidates(self, s, r):
        """G57b: an exact candidate set for the recall test 2|q&p| > |p|, q = b(s,0) ^ b(r,1).
        q's bits lie in b_s | b_r, so |q&p| <= |b_s&p| + |b_r|; passing needs |q&p| >= |p|//2 + 1,
        hence |b_s&p| >= |p|//2 + 1 - |b_r|. p lies in the union of its three codes (s' role 0,
        r' role 1, o' role 2), so one code X has |b_s&X| >= ceil((|p|//2 + 1 - |b_r|) / 3), which is
        >= 2 whenever |p| >= 2|b_r| + 6 (all packets with |p| >= SMALL_PACKET = 38, as |b_r| <= 16).
        Candidates: the triples of every code sharing >= 2 bits with b_s, plus every packet with
        |p| < 38. Each candidate is then tested exactly; every other triple fails the test."""
        ix = self.ix
        self.counts["candidate_queries"] += 1
        cnt = Counter()
        for b in _geom().bits(bits_for(s, 0)):
            cnt.update(ix["codebits"].get(b, ()))
        cand = set(ix["small"])
        for (role, tok), c in cnt.items():
            if c >= 2:
                cand.update((ix["by_s"], ix["by_rel"], ix["by_o"])[role].get(tok, ()))
        return cand

    def part_threshold(self, qi):
        """G59: k such that every triple that can ever add a name to the recall of q (|p| >= SMALL_PART)
        has two of its three codes X with |X & q| >= k (docs/G59.md §2a); None if k < PAIR_GROUPS + 1
        (the pigeonhole over a code's groups then does not hold: the G57b filter is used)."""
        m = -(-(SMALL_PART + qi.bit_count() - 16) // 2)
        k = -(-(m - 16) // 2)
        return k if k >= PAIR_GROUPS + 1 else None

    def recall_partitioned(self, s, r, qi, k):
        """G59 (`--partitioned`, docs/G59.md §2a): a candidate set for the recall of (s, r) that holds
        every triple that can add a name now or later, built from the codes near q only.
        A triple t adds a name x to the recall iff it passes and p ^ q = c_x (x's role-2 code, <= 16
        bits). Then |p ^ q| <= 16, so m = |p & q| >= (|p| + |q| - 16) / 2. p lies in the union of t's
        three codes, each of <= 16 bits, so the two largest overlaps |X & q| sum to >= m - 16 with the
        largest <= 16: two codes have |X & q| >= k = ceil((m_min - 16) / 2). A code X with |X & q| >= k
        >= PAIR_GROUPS + 1 has two of those bits in one of its groups, i.e. one of its indexed pairs
        is a pair of q's bits. Candidates: every triple with two codes in H = {indexed codes hit by a
        pair of q with |X & q| >= k}, plus every packet with |p| < SMALL_PART."""
        ix = self.ix
        self.counts["partitioned_queries"] += 1
        pairs, Q = ix["pairs"], _geom().bits(qi)
        hit = set()
        for i in range(len(Q)):
            base = Q[i] * 4096
            for j in range(i + 1, len(Q)):
                got = pairs.get(base + Q[j])
                if got:
                    hit.update(got)
        H = {X for X in hit if (_code_bits(X)[0] & qi).bit_count() >= k}
        self.counts["partitioned_hits"] += len(hit)
        roles = ({}, {}, {})
        for role, tok in H:
            roles[role][tok] = True
        cand = set(ix["small_part"])
        by_s, by_rel, by_o, by_sr = ix["by_s"], ix["by_rel"], ix["by_o"], ix["by_sr"]
        for s0 in roles[0]:
            for r1 in roles[1]:
                for f in by_sr.get((s0, r1), ()):
                    cand.add((f["s"], f["r"], f["o"]))
            for o2 in roles[2]:
                a, b = by_s.get(s0, ()), by_o.get(o2, ())
                cand.update(t for t in (a if len(a) <= len(b) else b) if t[0] == s0 and t[2] == o2)
        for r1 in roles[1]:
            for o2 in roles[2]:
                a, b = by_rel.get(r1, ()), by_o.get(o2, ())
                cand.update(t for t in (a if len(a) <= len(b) else b) if t[1] == r1 and t[2] == o2)
        if G58_AUDIT["on"]:  # every triple that passes with |p ^ q| <= 16 is a candidate
            for t in self.base:
                p = self.packet_of(t)
                if 2 * (qi & p).bit_count() > p.bit_count() and (p ^ qi).bit_count() <= 16 and t not in cand:
                    _g58_violation("recall_partitioned_missed", (s, r, t))
        return cand

    def ix_check(self, state, fresh) -> None:
        """Guard: the persistent index equals a fresh build -- the reference structures (names, pos,
        out, triples, ref, byid) and, since G58 (Low 1 of verify-8994490), every G57b structure:
        by_rel, by_s, by_o, by_sr (fact identity), told_rel, the candidate filter's codes, codebits and
        small packets, decode, and each cached prediction row."""
        self.ix_checks += 1
        ix = self.ix
        same = all(ix[k] == fresh[k] for k in ("names", "pos", "out", "triples", "ref")) \
            and list(ix["byid"]) == list(fresh["byid"]) and all(ix["byid"][k] is fresh["byid"][k] for k in fresh["byid"])
        told = Counter(f["r"] for f in state["facts"]
                       if not f["r"].startswith("cap:") and any(sp["kind"] == "told" for sp in f["supports"]))
        _need(same and +ix["told_rel"] == told, "incremental fact index diverged from the facts")
        by_rel, by_s, by_o, by_sr, codes, small, small_part = {}, {}, {}, {}, set(), Counter(), Counter()
        pairs = ix.get("pairs")
        for f in state["facts"]:
            t = (f["s"], f["r"], f["o"])
            by_rel.setdefault(t[1], []).append(t)
            by_s.setdefault(t[0], []).append(t)
            by_o.setdefault(t[2], []).append(t)
            by_sr.setdefault((t[0], t[1]), []).append(f)
            codes.add((0, t[0]))
            codes.add((1, t[1]))
            codes.add((2, t[2]))
            pc = self.packet(t).bit_count()
            if pc < SMALL_PACKET:
                small[t] += 1
            if pc < SMALL_PART:
                small_part[t] += 1
        ok = ix["by_rel"] == by_rel and ix["by_s"] == by_s and ix["by_o"] == by_o \
            and set(ix["by_sr"]) == set(by_sr) \
            and all(len(ix["by_sr"][k]) == len(v) and all(a is b for a, b in zip(ix["by_sr"][k], v)) for k, v in by_sr.items()) \
            and ix["codes"] == codes and Counter(ix["small"]) == small \
            and ix["decode"] == {pack(bits_for(t, 2)).bits: t for t in fresh["names"]}
        if ok:
            # G59: codebits (and the pair index) equal fresh builds, checked without rebuilding them:
            # every listed entry is valid, no list repeats an entry, and the number of entries equals
            # the number of valid ones (so the listed sets are exactly the valid sets)
            xi = {X: bits_for(X[1], X[0]) for X in codes}
            n = 0
            for b, lst in ix["codebits"].items():
                n += len(lst)
                if len(set(lst)) != len(lst) or not all(X in xi and xi[X] >> b & 1 for X in lst):
                    ok = False
                    break
            ok = ok and n == sum(x.bit_count() for x in xi.values())
            if ok and pairs is not None:
                ok = Counter(ix["small_part"]) == small_part
                # each code's valid pair keys, from its fresh bits (the same grouping as `_code_pairs`)
                bits = _geom().bits
                ks = {X: frozenset(_code_pairs(bits(x))) for X, x in xi.items()}
                want, n = sum(len(v) for v in ks.values()), 0
                for key, lst in pairs.items():
                    n += len(lst)
                    if not ok or len(set(lst)) != len(lst):
                        ok = False
                        break
                    for X in lst:
                        v = ks.get(X)
                        if v is None or key not in v:
                            ok = False
                            break
                ok = ok and n == want
        if ok:
            pos = fresh["pos"]
            for rel, rows in ix["prow"].items():
                want = SparseRows()
                for s_, _, o_ in by_rel.get(rel, ()):
                    want[pos[s_]] = want[pos[s_]] | (1 << pos[o_])
                if dict(rows) != dict(want):
                    ok = False
                    break
        _need(ok, "incremental fact index diverged from the facts (G57b structures)")

    def region_hits(self, seeds, grown) -> bool:
        """`grown & _component(seeds)` is non-empty, decided from components kept across calls:
        the BFS region is the seeds plus every entity joined to a seed by non-cap fact edges, i.e.
        the seeds plus the union-find classes of the seeds that have edges."""
        if self.uf is None:
            self.uf = {}
            self.members = {} if self.track_members else None
            for t in self.base:
                if not t[1].startswith("cap:"):
                    self._union(t[0], t[2])
        roots = {self._find(x) for x in seeds if x in self.uf}
        return any(g in seeds or (g in self.uf and self._find(g) in roots) for g in grown)

    @staticmethod
    def packet(t):
        return bits_for(t[0], 0) ^ bits_for(t[1], 1) ^ bits_for(t[2], 2)

    @staticmethod
    def passes(qi, p):
        x = qi & p
        return bool(x) and 2 * x.bit_count() - p.bit_count() > 0

    def sync(self, triples) -> None:
        last = self.last
        if len(triples) >= len(last) and triples[:len(last)] == last:
            if len(triples) == len(last):
                return
            new = triples[len(last):]
            added, removed = Counter(new), Counter()  # facts appended (the common case)
            cur = self.base + added
            self.pkl += [(p, p.bit_count()) for p in map(self.packet_of, new)]
        else:
            cur = Counter(triples)
            self.pkl = [(p, p.bit_count()) for p in map(self.packet_of, triples)]
            if cur == self.base:
                self.last = list(triples)
                return
            added, removed = cur - self.base, self.base - cur
        self.last = list(triples)
        self.tick += 1
        for t in list(added) + list(removed):
            self.stamp.pop(t[1], None)  # G59: stamps kept in increasing order
            self.stamp[t[1]] = self.tick
        for (s_, r_), ent in self.recall.items():
            qi = bits_for(s_, 0) ^ bits_for(r_, 1)
            for t, c in removed.items():
                if t in ent:
                    ent[t] -= c
                    if ent[t] <= 0:
                        del ent[t]
            for t, c in added.items():
                if self.passes(qi, self.packet_of(t)):
                    ent[t] += c
        if self.uf is not None:
            if any(not t[1].startswith("cap:") for t in removed):
                self.uf = None  # an edge may be gone: rebuild the classes on next use
                self.members = None
            else:
                for t in added:
                    if not t[1].startswith("cap:"):
                        self._union(t[0], t[2])
        self.base = cur


class Engine:
    def __init__(self, path, state=None, report=None, geometry=True, use_library=True, deepen=None, activation=True,
                 operators=False, retention="static", programs=False, answers=False, qualified_library=False,
                 bounded=False, lean=False, closed_guards=None, indexed=False, memo=None, incremental=False,
                 routed=False, partitioned=False):
        self.path = Path(path)
        self.qualified_library = qualified_library  # G51: library offers only qualified capabilities
        # G55 (option 3): guard budget under `complete`, independent of the observations; None = MAX_GUARDS
        self.closed_guards = progs.MAX_GUARDS if closed_guards is None else closed_guards
        self.lean = lean  # G54: exact per-call cost bounds (persistence, geometric recall)
        # G57: relation-indexed rows, incremental exact recall, gated re-asks (docs/G57.md)
        self.indexed = indexed
        self.memo = (memo if memo is not None else Memo()) if indexed else None
        # G57b: the persistent fact index (needs the memo); static retention only
        self.incremental = bool(incremental and indexed and retention == "static")
        self._ents_tracked = False
        # G58 (`--routed`, docs/G58.md): exact capability routing -- review re-evaluates only the
        # capabilities whose evaluation inputs changed, cached version closures, and activation
        # visits only the primitives that leave the frontier. Needs the memo; base engine only.
        self.routed = bool(routed and indexed and geometry and not programs and not operators
                           and retention == "static")
        # G59 (`--partitioned`, docs/G59.md): exact recall from the codes near the query (a code-pair
        # index), and the seeds index kept in step at the end of every call. Needs `--routed` and
        # `--incremental`.
        self.partitioned = bool(partitioned and self.routed and self.incremental)
        if self.partitioned and not self.memo.partitioned:
            self.memo.partitioned = True
            self.memo.ix = None  # rebuilt with the pair index on next use
        self.readonly_call = False  # set by serve.py for a call whose lines are all questions
        self._cap_fp = {}
        self.bounded = bounded  # G53: exact cost bounds (memoized scan images; no re-scan of settled versions)
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
        # answers: the teacher may state `-> !none` / `-> !several` (docs/PX.md); investigate then
        # scores every answer class, including those two
        self.answers = answers
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
                doc, ok = _read_doc(raw)
                state = validate_lean(doc, ok) if kw.get("lean") else validate(doc, ok)
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

    def finish(self) -> None:
        """End-of-call work that changes the state (pending growth re-scans, adaptive archiving).
        `save` runs it first; the G56 long-lived protocol (packetlm/serve.py) runs it after every
        call and persists by journal instead of a full write."""
        if getattr(self, "_grown", None):
            self._flush_growth()
        if self.partitioned and self.memo.sx_dirty or self.partitioned and self.memo.sx is None:
            self._sx()  # G59: the seeds index in step with this call's writes (paid by the call that wrote)
        if self.retention == "adaptive":
            for comp, why in ret_mod.decide(self.state, self.state["retention"]):
                ret_mod.archive(self.state, self.state["retention"], self._archive_dir, comp, why)
                self.stats["archived"] = self.stats.get("archived", 0) + 1
                self._dirty()
                self._archived_tok = None

    def save(self) -> None:
        self.finish()
        if self.lean:
            return self._save_lean()
        validate({"schema": SCHEMA, "checksum": _checksum(self.state), "state": self.state})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            try:
                cur = self.path.read_bytes()
                if hashlib.sha256(cur).hexdigest() != self._known_bytes:  # bytes this process did not validate
                    validate(*_read_doc(cur))
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

    def _save_lean(self) -> None:
        """G54: the same guarantees as `save` -- full validation before writing, the previous good
        primary kept as the backup, atomic replace, fsync -- with the state serialized once. The
        checksum is sha256 of the written state text (insertion order since verification M1 of
        3e2783c; `_read_doc` checks it for lean and non-lean engines alike). The backup is a hard link to the previous
        primary's inode (the primary is then replaced by a new inode), not a byte copy."""
        # insertion-order text, as a non-lean save writes it: dict order is observable in replies
        # (verification M1 of 3e2783c), so the saved order must be the in-memory order
        text = json.dumps(self.state).encode()
        chk = hashlib.sha256(text).hexdigest()
        validate_lean({"schema": SCHEMA, "checksum": chk, "state": self.state}, checksum_ok=True)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        bak = self.path.with_name(self.path.name + ".bak")
        if self.path.exists():
            try:
                cur = self.path.read_bytes()
                if hashlib.sha256(cur).hexdigest() != self._known_bytes:  # bytes this process did not validate
                    validate_lean(*_read_doc(cur))
                tmpb = self.path.with_name(self.path.name + ".bak.tmp")
                if tmpb.exists():
                    tmpb.unlink()
                try:
                    os.link(self.path, tmpb)
                    os.replace(tmpb, bak)
                except OSError:
                    _write_atomic(bak, cur)
            except (ValueError, StateError):
                pass  # never back up a corrupt primary over a good backup
        data = _lean_prefix(SCHEMA, chk) + text + b"}"
        _write_atomic(self.path, data)
        self._known_bytes = hashlib.sha256(data).hexdigest()
        try:
            dfd = os.open(self.path.parent, os.O_RDONLY)
            os.fsync(dfd)
            os.close(dfd)
        except OSError:
            pass

    # ---------- indexes ----------

    def _ix_live(self) -> bool:
        return self.incremental and self.memo.ix_valid(self.state)

    def _idx(self):
        if self._cache is None and self.incremental and self.memo.ix_valid(self.state):
            ix = self.memo.ix  # G57b: the persistent index; per-call caches start empty
            self._cache = {k: ix[k] for k in Memo.CORE}
            self._cache.update(rows={}, persistent=True)
            return self._cache
        if self._cache is None:
            names, pos, decode, triples = [], {}, ({} if not self.lean else None), []
            for f in self.state["facts"]:
                for t in (f["s"], f["o"]):
                    if t not in pos:
                        pos[t] = len(names)
                        names.append(t)
                        if decode is not None:
                            decode[pack(bits_for(t, 2)).bits] = t
                triples.append((f["s"], f["r"], f["o"]))
            out = {}
            for s_, r_, _ in triples:
                out.setdefault(s_, set()).add(r_)
            self._cache = {"names": names, "pos": pos, "decode": decode, "rows": {}, "out": out,
                           "triples": triples, "ref": reference.index(triples),
                           "byid": {f["id"]: f for f in self.state["facts"]}}
            if self.memo is not None:
                self.memo.sync(triples)
            if self.incremental:
                if self.memo.scope is not None:
                    self.memo.scope["ok"] = False  # rebuilt: this call's changes were not all tracked
                self.memo.ix_adopt(self.state, self._cache)
                self._cache = {k: self.memo.ix[k] for k in Memo.CORE}
                self._cache.update(rows={}, persistent=True)
        return self._cache

    def _dirty(self):
        self._cache = None

    def entities(self) -> list[str]:
        return list(self._idx()["names"])

    def relations(self) -> list[str]:
        """Primitive relation identities: told facts only, never cap:* conclusions."""
        if self._ix_live():  # G57b: counts kept by the index
            return sorted(r for r, c in self.memo.ix["told_rel"].items() if c > 0)
        return sorted({f["r"] for f in self.state["facts"]
                       if not f["r"].startswith("cap:") and any(sp["kind"] == "told" for sp in f["supports"])})

    # ---------- semantic memory ----------

    def _tick(self) -> int:
        self.state["turn"] += 1
        return self.state["turn"]

    def _find(self, s, r, o=None):
        if self._ix_live():  # G57b: the facts of (s, r) in fact order
            return [f for f in self.memo.ix["by_sr"].get((s, r), ()) if o is None or f["o"] == o]
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
                live = self._ix_live()
                was_told = any(sp["kind"] == "told" for sp in fact["supports"])
                fact["supports"].append(support)
                if live:
                    self.memo.ix_support(fact, was_told)
                if self.incremental and self.memo.scope is not None:
                    self.memo.scope["touched"].append(fact)
            return fact
        fact = {"id": f"{s} {r} {o}", "s": s, "r": r, "o": o, "supports": [support]}
        if kind == "told" and not r.startswith("cap:") and self.state.get("complete"):
            self._fc_violated(s, f"new fact {s} {r} {o}")
        live = self._ix_live()
        if live and getattr(self, "_ents", None) is None:
            # G57b: the reference's entity set here is exactly the index's entities (facts at first
            # use plus every fact told since, with no removal in between: a removal rebuilds)
            was_known = s in self.memo.ix["pos"]
            self._ents_tracked = True
        else:
            ents = self._known_entities()
            was_known = s in ents  # S1 of cdb4828: known before this fact?
            ents.update((s, o))
        self.state["facts"].append(fact)
        self.state["fact_epoch"] = self.state.get("fact_epoch", 0) + 1  # G53: any fact change
        if live:
            self.memo.ix_append(fact, self.state)
        if self.incremental and self.memo.scope is not None:
            self.memo.scope["touched"].append(fact)
        if kind == "told" and not r.startswith("cap:"):
            self._grow(s, was_known)
        self._dirty()
        return fact

    def _drop(self, ids, reason, programs=()) -> dict:
        """Truth maintenance: remove facts, then any proof that used them or a dropped program.
        A conclusion stays while one independent proof remains."""
        removed = set(ids)
        if self.incremental and self.memo is not None and self.memo.ix_valid(self.state):
            # Low 1 of verify-8994490: a removal discards the persistent index; it is checked first
            # (before any support or fact changes), so a divergence fails the call instead of being
            # healed by the rebuild
            self.memo.counts["ix_checks_before_removal"] += 1
            self.memo.ix_check(self.state, _fresh_index(self.state["facts"]))
        if self.incremental:
            if self._ents_tracked and getattr(self, "_ents", None) is None:
                # the set the reference built at its first use, plus every fact told since
                self._ents = {x for f in self.state["facts"] for x in (f["s"], f["o"])}
            if self.memo.scope is not None:
                self.memo.scope["ok"] = False  # supports and facts may change anywhere
        if self.state.get("complete"):
            byid = {f["id"]: f for f in self.state["facts"]}
            for i in sorted(removed):
                f = byid.get(i)
                if f and not f["r"].startswith("cap:") and any(sp["kind"] == "told" for sp in f["supports"]):
                    self._fc_violated(f["s"], f"removed fact {i}")
        byid = {f["id"]: f for f in self.state["facts"]}
        for i in removed:
            f = byid.get(i)
            if f and not f["r"].startswith("cap:") and any(sp["kind"] == "told" for sp in f["supports"]):
                self._grow(f["s"])
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
        if removed:
            self.state["fact_epoch"] = self.state.get("fact_epoch", 0) + 1  # G53: any fact change
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
        if self.memo is not None:
            self.memo.rvx = None  # G58: observations rewritten; the next review is a full pass
            self.memo.sx = None
            if self.memo.scope is not None:
                self.memo.scope["obs_all"] = True
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
        ver["domain"] = scan.pop("domain_set")
        if self.memo is not None:
            self.memo.sx_dirty.add(name)  # G58
        rec = self.state["hypotheses"].setdefault(name, {"live": []})
        rec.update({"candidate": ver["seq"], "blocking": blocking, "scan": scan})
        status = "provisional" if blocking or self._deps_unqualified(ver["seq"]) else "qualified"
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
            if self.memo is not None:
                return self._ask_indexed(idx, s, r, qi)
            if "packets" not in idx:  # derived on demand, never stored (schema 3)
                idx["packets"] = [bits_for(f["s"], 0) ^ bits_for(f["r"], 1) ^ bits_for(f["o"], 2)  # == bind(...) as int
                                  for f in self.state["facts"]]
            if self.lean:
                return self._ask_lean(idx, qi)
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

    def _ask_lean(self, idx, qi) -> dict:
        """G54: the same geometric recall, computed exactly with less work. Packet.score is
        2|q&p| - |p|. If q&p is empty the score is -|p| <= 0, so the packet is skipped exactly as
        before without counting; |p| is counted once per packet per process. The decode table is
        built only when some packet scores above 0. The candidate order, the de-duplication and the
        final sort are unchanged."""
        if "pcount" not in idx:
            idx["pcount"] = [p.bit_count() for p in idx["packets"]]
        found = []
        for p, pc in zip(idx["packets"], idx["pcount"]):
            x = qi & p
            if not x or 2 * x.bit_count() - pc <= 0:
                continue
            got = self._decode().get(pack(p ^ qi).bits)
            if got and got not in found:
                found.append(got)
        found = sorted(found)
        if not found:
            return {"status": "unknown", "value": None}
        if len(found) > 1:
            return {"status": "ambiguous", "value": None, "candidates": found}
        return {"status": "known", "value": found[0]}

    def _ask_indexed(self, idx, s, r, qi) -> dict:
        """G57: the geometric recall of `ask` from the memo. The reference decides recall by the
        packets that pass 2|q&p| - |p| > 0 and decodes each residue p ^ q against this index's
        names; the memo holds exactly the passing triples for (s, r) (a full pass over this index's
        packets the first time, maintained by `Memo.sync` after that), and decoding is unchanged.
        The reference de-duplicates and sorts, so the order of the passing packets does not matter."""
        ent = self.memo.recall.get((s, r))
        if ent is None:
            # the reference's test, 2|q&p| - |p| > 0, over this index's triples (memo.pkl is aligned
            # with them: sync ran when this index was built)
            if idx.get("persistent"):  # G57b: the exact candidate set, then the same test
                pk, base = self.memo.packet_of, self.memo.base
                ent = Counter()
                k = self.memo.part_threshold(qi) if self.partitioned and "pairs" in self.memo.ix else None
                cands = self.memo.recall_partitioned(s, r, qi, k) if k is not None else self.memo.recall_candidates(s, r)
                for t in cands:
                    p = pk(t)
                    if 2 * (qi & p).bit_count() > p.bit_count():
                        ent[t] += base[t]
            else:
                _need(len(self.memo.pkl) == len(idx["triples"]), "memo packets out of step with the index")
                ent = Counter(t for t, (p, c) in zip(idx["triples"], self.memo.pkl) if 2 * (qi & p).bit_count() > c)
            self.memo.recall[(s, r)] = ent
        found = []
        if ent:
            dec = self._decode()
            for t in ent:
                got = dec.get(pack(self.memo.packet_of(t) ^ qi).bits)
                if got and got not in found:
                    found.append(got)
        found = sorted(found)
        if not found:
            return {"status": "unknown", "value": None}
        if len(found) > 1:
            return {"status": "ambiguous", "value": None, "candidates": found}
        return {"status": "known", "value": found[0]}

    def _decode(self):
        idx = self._idx()
        if idx["decode"] is None:
            idx["decode"] = {pack(bits_for(t, 2)).bits: t for t in idx["names"]}
        return idx["decode"]

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

    def _deps_unqualified(self, seq):
        out = []
        for d in _deps_of(seq):
            dn, dv = _split_cap(d)
            dver = self.version(dn, dv)
            if not dver or dver["status"] != "qualified":
                out.append(d)
        return out

    def _set_status(self, name, v, status, reason):
        ver = self.version(name, v)
        if ver["status"] == status:
            return []
        old_status, ver["status"] = ver["status"], status
        if self.memo is not None:
            self.memo.lib_gen += 1  # G58: what `primitives` offers may change
            if (old_status in PINNED_OK) != (status in PINNED_OK):
                self.memo.pin_gen += 1
            self.memo.rv_dirty.add((name, v))
            self.memo.cx_dirty.add(name)
            self.memo.sx_dirty.add(name)
            if self.memo.scope is not None:
                self.memo.scope.setdefault("caps", set()).add(name)
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
            elif status == "provisional" and dep["status"] == "qualified":
                events += self._set_status(dn, dv, "provisional", f"dependency {name}@{v} provisional")
            elif status == "superseded":
                dep.setdefault("history", []).append({"turn": self.state["turn"], "status": dep["status"],
                                                      "reason": f"still pinned to {name}@{v}; requalify to adopt the new version"})
                events.append(f"{dn}@{dv} stays pinned to {name}@{v}")
        return events

    def review(self) -> list[str]:
        """Re-check every executable capability against its own observations."""
        if self.routed:
            return self._review_routed()
        events = []
        for name, cap in self.state["capabilities"].items():
            ver = self.version(name)
            if not ver or ver["status"] not in EXEC_OK:
                continue
            h = self.evaluate(ver["seq"], self.state["observations"].get(name, []))
            if h["status"] == "contradicted":
                events += self._set_status(name, ver["v"], "suspended", "contradicted by its observations")
        return events

    def _review_routed(self) -> list[str]:
        """G58 (docs/G58.md §2a): `review` with the same evaluations' outcomes and the same events in
        the same order. A capability is re-evaluated only if its fingerprint (`_review_fp`: everything
        `evaluate` reads) may differ from the one of its last non-contradicted evaluation.
        Fast pass (the closed set is the same and the capability records object is the same as at the
        last review): only the candidates -- capabilities whose observations changed, that read a
        relation with triples added or removed since then (stamps), whose own status or versions
        changed, or whose closure holds a version whose status changed -- are visited, in capability
        order; every other one has an unchanged fingerprint. If a status changes during the pass,
        every later capability is visited with its full fingerprint. Otherwise (full pass) every
        capability's fingerprint is computed and compared."""
        events = []
        memo, caps, rv = self.memo, self.state["capabilities"], self.memo.rv
        pos = self._idx()["pos"]  # syncs the memo stamps
        gen0 = memo.lib_gen
        closed = frozenset(self.state.get("complete", {}))
        X = memo.rvx
        fast = None
        if X is not None and X["caps"] == id(caps):
            fast = set(memo.rv_obs)
            for x in X["closed"] ^ closed:  # closed-world judgment changed at these subjects
                fast |= X["subj"].get(x, set())
            # entities that became known or unknown (the fingerprint's `known` flag); the persistent
            # index only appends to its entity map, so the same map with the same length is the same set
            if pos is X["pos"]:
                new = [x for x in itertools.islice(pos, X["npos"], None)]
                X["ents"].update(new)
            else:
                cur = set(pos)
                new, X["ents"] = cur ^ X["ents"], cur
            for x in new:
                fast |= X["subj"].get(x, set())
            X["pos"], X["npos"] = pos, len(pos)
            for r in reversed(memo.stamp):  # G59: in increasing stamp order, so stop at the first old one
                if memo.stamp[r] <= X["tick"]:
                    break
                fast |= X["rel"].get(r, set())
            for dn, dv in memo.rv_dirty:  # the capability itself, and every one whose closure holds it
                fast.add(dn)
                fast |= X["dep"].get((dn, dv), set()) if dv is not None else X["depn"].get(dn, set())
            order = X["order"]
            if len(caps) > len(order):
                for n in list(caps)[len(order):]:
                    order[n] = len(order)
                    fast.add(n)
        covered = True
        seen = {}  # name -> (base, deps, observed subjects) of each capability visited
        visited = set()

        def visit(name, full_fp=True):
            nonlocal covered
            visited.add(name)
            ver = self.version(name)
            if not ver or ver["status"] not in EXEC_OK:
                return
            obs = self.state["observations"].get(name, [])
            fp = self._review_fp(name, ver, obs)
            if fp is not None and rv.get(name) == fp:
                memo.counts["g58_review_skipped"] += 1
                seen[name] = (fp[4], fp[3], [o[0] for o in obs])
                return
            h = self.evaluate(ver["seq"], obs)
            if h["status"] == "contradicted":
                # rv keeps the fingerprint of the last non-contradicted evaluation: `evaluate` is a
                # function of the fingerprint, so a later equal fingerprint is again not contradicted
                events.extend(self._set_status(name, ver["v"], "suspended", "contradicted by its observations"))
            elif fp is not None:
                rv[name] = fp
                seen[name] = (fp[4], fp[3], [o[0] for o in obs])
            else:
                covered = False

        if fast is not None:
            todo = sorted((order[n], n) for n in fast if n in caps)
            memo.counts["g58_review_fast"] += 1
            memo.counts["g58_review_unseen"] += len(caps) - len(todo)
            last = -1
            for k, n in todo:
                if memo.lib_gen != gen0:
                    break
                visit(n)
                last = k
            if memo.lib_gen != gen0:
                # a status changed during the pass: every later capability with its full fingerprint
                done = {n for k, n in todo if k <= last}
                for n in list(caps)[last + 1:]:
                    if n not in done:
                        visit(n)
                memo.rvx = None
            elif covered and all(b for b, _, _ in seen.values()):
                for n, (b, ds, subj) in seen.items():  # maps grow (stale entries only add candidates)
                    for r in b:
                        X["rel"].setdefault(r, set()).add(n)
                    for dn, dv, _ in ds:
                        X["dep"].setdefault((dn, dv), set()).add(n)
                        X["depn"].setdefault(dn, set()).add(n)
                    for x in subj:
                        X["subj"].setdefault(x, set()).add(n)
                X["tick"], X["closed"] = memo.tick, closed
            else:
                memo.rvx = None
        else:
            memo.counts["g58_review_full"] += 1
            for n in list(caps):
                visit(n)
            all_seen = all(n in seen for n in caps if (self.version(n) or {}).get("status") in EXEC_OK)
            if memo.lib_gen == gen0 and covered and all_seen and all(b for b, _, _ in seen.values()):
                rel, dep, depn, subj = {}, {}, {}, {}
                for n, (b, ds, ss) in seen.items():
                    for r in b:
                        rel.setdefault(r, set()).add(n)
                    for dn, dv, _ in ds:
                        dep.setdefault((dn, dv), set()).add(n)
                        depn.setdefault(dn, set()).add(n)
                    for x in ss:
                        subj.setdefault(x, set()).add(n)
                memo.rvx = {"caps": id(caps), "closed": closed, "tick": memo.tick, "rel": rel, "dep": dep,
                            "depn": depn, "subj": subj, "order": {n: i for i, n in enumerate(caps)},
                            "pos": pos, "npos": len(pos), "ents": set(pos)}
            else:
                memo.rvx = None
        if G58_AUDIT["on"]:  # every capability not visited has the fingerprint of its last evaluation
            for n in caps:
                ver = self.version(n)
                if n in visited or not ver or ver["status"] not in EXEC_OK:
                    continue
                obs = self.state["observations"].get(n, [])
                fp = self._review_fp(n, ver, obs)
                if fp is None or rv.get(n) != fp:
                    _g58_violation("review_skipped_changed", n)
            for n in list(caps):  # the outcome: no capability left EXEC_OK is contradicted
                ver = self.version(n)
                if ver and ver["status"] in EXEC_OK and \
                        self.evaluate(ver["seq"], self.state["observations"].get(n, []))["status"] == "contradicted":
                    _g58_violation("review_missed_contradiction", n)
        memo.rv_obs, memo.rv_dirty = set(), set()
        return events

    def _review_fp(self, name, ver, obs):
        """G58: everything `evaluate(ver.seq, obs)` reads (docs/G58.md §2a), or None when not covered:
        - the version (number, status, seq) and, for every capability version it reaches through
          `cap:` steps, its status (`expand` returns None unless each is PINNED_OK; seqs are fixed);
        - the expanded base relations and the change stamp of each (`execute` reads only the triples
          of those relations, through the index, synced here);
        - each observation (subject, value), whether the subject is a known entity (`execute` returns
          the empty set otherwise) and whether it is closed (`complete`: closed-world judgment)."""
        seq = ver["seq"]
        if any(x.startswith(("prog:", "op:")) for x in seq):
            return None
        idx = self._idx()  # syncs the memo stamps with the current facts
        clo = self._closure_cached(name, ver)
        deps = tuple(sorted((dn, dv, (self.version(dn, dv) or {}).get("status")) for dn, dv in clo))
        base = self._expand_fast(seq)
        stamp = self.memo.stamp
        pos, closed = idx["pos"], self.state.get("complete", {})
        return (ver["v"], ver["status"], tuple(seq), deps, tuple(base) if base is not None else None,
                tuple(stamp.get(r, 0) for r in base) if base is not None else None,
                tuple((s_, v_, s_ in pos, s_ in closed) for s_, v_ in obs))

    def _expand_fast(self, seq):
        out = self._expand_fast0(seq)
        if G58_AUDIT["on"]:
            fresh = self.expand(list(seq))
            if (None if out is None else list(out)) != (None if fresh is None else list(fresh)):
                _g58_violation("expand", seq)
        return out

    def _expand_fast0(self, seq):
        """G58: `expand(seq)` for rel:/op:/cap: steps, with each capability version's base cached
        (its seq never changes; the cache key holds it). A cached base is used only when the version
        and every version in its closure are PINNED_OK, the condition under which `expand` returns
        it; otherwise `expand` itself runs. prog: steps always go to `expand`."""
        out = []
        for step in seq:
            if step.startswith("rel:"):
                out.append(step[4:])
            elif step.startswith("op:"):
                out.append(step[3:])
            elif step.startswith("prog:"):
                return self.expand(seq)
            else:
                name, v = _split_cap(step)
                ver = self.version(name, v)
                if not ver or ver["status"] not in PINNED_OK:
                    return None
                key = (name, ver["v"], tuple(ver["seq"]))
                b = self.memo.pb.get(key)
                if b is not None and all((self.version(dn, dv) or {}).get("status") in PINNED_OK
                                         for dn, dv in self._closure_cached(name, ver)):
                    out += b
                    self.memo.counts["g58_base_cached"] += 1
                    continue
                sub = self.expand([step])
                if sub is None:
                    return None
                self.memo.pb[key] = tuple(sub)
                out += sub
        return out

    def _closure_cached(self, name, ver):
        key = (name, ver["v"], tuple(ver["seq"]))
        c = self.memo.clo.get(key)
        if c is None:
            c = self.memo.clo[key] = frozenset(self._closure(name, ver["v"]))
        if G58_AUDIT["on"] and c != frozenset(self._closure(name, ver["v"])):
            _g58_violation("closure", key)
        return c

    # ---------- execution ----------

    def execute(self, seq, subject):
        """Run a program. Geometric: bit-row composition (geom.compose). Disabled: symbolic sets."""
        self.stats["executions"] += 1
        if not any(s.startswith(("rel:", "cap:", "op:", "prog:")) for s in seq):
            base = list(seq)
        else:
            base = self._expand_fast(seq) if self.routed else self.expand(seq)
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
        if idx.get("persistent"):  # G57b: kept across calls, dropped when rel changes; built from rel's triples only
            prow = self.memo.ix["prow"]
            if rel not in prow:
                pos, rows = idx["pos"], SparseRows()
                for s_, _, o_ in self.memo.ix["by_rel"].get(rel, ()):
                    rows[pos[s_]] = rows[pos[s_]] | (1 << pos[o_])
                prow[rel] = rows
            return prow[rel]
        if rel not in idx["rows"]:
            n = len(idx["names"])
            if self.indexed:  # G57: the same triples in the same order, grouped by relation once per index
                if "by_rel" not in idx:
                    by = {}
                    for t in idx["triples"]:
                        by.setdefault(t[1], []).append(t)
                    idx["by_rel"] = by
                sel = idx["by_rel"].get(rel, [])
            else:
                sel = [t for t in idx["triples"] if t[1] == rel]
            idx["rows"][rel] = _geom().rows_from([(idx["pos"][s], r, idx["pos"][o]) for s, r, o in sel], n, rel)
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
        base = self._expand_fast([prim]) if self.routed else self.expand([prim])
        if not base:
            return None
        return base[0].split(":")[1] if base[0].startswith("until:") else base[0]

    def _activated(self, prims, n, start, name=None):
        """Programs of length n whose image of the start set never empties; returns (seqs, pruned)."""
        out, pruned, P = [], 0, len(prims)

        idx = self._idx()
        by_first = {}
        rels = None
        if self.routed and name is not None and not self.operators:
            # G58: `prims` is `primitives(name)`: each node's visit list from the capability index
            rels = self._cx_router(name, {r: k for k, r in enumerate(self.relations())})
            first = None
        elif self.routed:
            # G58: primitives indexed by their first base relation; a node visits only those that
            # leave its frontier, in the original order. Each skipped one adds P^(n-len-1) to
            # `pruned`, exactly as the loop below would (same count, same programs, same order).
            _, _, by_first = self._routing(prims)
            first = None
        else:
            first = {p: self._first_rel(p) for p in prims}

        def walk(prefix, front):
            nonlocal pruned
            if len(prefix) == n:
                out.append(tuple(prefix))
                return
            ents = [idx["names"][i] for i in _geom().bits(front)] if self.geometry else front
            here = set().union(*(idx["out"].get(x, set()) for x in ents)) if ents else set()
            visit = prims
            if rels is not None:
                visit = [p for p, _, _ in rels(here)]
                pruned += (P - len(visit)) * P ** (n - len(prefix) - 1)
                if G58_AUDIT["on"]:
                    _, _, bf = self._routing(prims)
                    if [prims[i] for i in sorted(i for r in here for i in bf.get(r, ()))] != visit:
                        _g58_violation("activated_visit", (name, sorted(here)))
            elif self.routed:
                ii = sorted(i for r in here for i in by_first.get(r, ()))
                pruned += (P - len(ii)) * P ** (n - len(prefix) - 1)
                visit = [prims[i] for i in ii]
            for p in visit:
                if first is not None and first[p] not in here:  # relevance index: no edge leaves the frontier (exact)
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
        if self.memo is not None:
            self.memo.rv_obs.add(name)  # G58
            self.memo.sx_dirty.add(name)
            if self.memo.scope is not None:
                self.memo.scope.setdefault("obs", set()).add(name)
        if [subject, value] not in obs:
            obs.append([subject, value])
        self._tick()
        return self.review()

    def evaluate(self, seq, observations) -> dict:
        marks = []
        for s, v in observations:
            self.stats["evaluations"] += 1
            out = self.execute(seq, s)
            marks.append(self._judge(s, out, v))
        if "contradicted" in marks:
            status = "contradicted"
        elif marks and all(m == "supported" for m in marks):
            status = "supported"
        else:
            status = "undetermined"
        return {"seq": list(seq), "status": status, "support": marks.count("supported")}

    def _lib_key(self, name):
        caps = self.state["capabilities"]
        return (self.memo.lib_gen, id(caps), len(caps), name, self.use_library, self.qualified_library)

    def _routing(self, prims):
        """G58: the routing tables for a primitive list (cached per library generation and list):
        each primitive's base (`expand([p])`), its first base relation, and the indices by first
        relation. A cached base is checked as `_expand_fast` does (statuses PINNED_OK)."""
        caps = self.state["capabilities"]
        key = (self.memo.lib_gen, id(caps), len(caps), tuple(prims))
        c = self.memo.lib.get(("route", key))
        if c is None:
            if len(self.memo.lib) > 4096:
                self.memo.lib.clear()
            # each primitive's base and first relation, kept while no version entered or left
            # PINNED_OK (`expand` of a fixed seq depends on nothing else)
            pf, pg = self.memo.pfirst, self.memo.pin_gen
            bases, first = [], []
            for p in prims:
                e = pf.get(p)
                if e is None or e[0] != pg:
                    b = self._expand_fast([p])
                    e = pf[p] = (pg, b, None if not b else (b[0].split(":")[1] if b[0].startswith("until:") else b[0]))
                bases.append(e[1])
                first.append(e[2])
            by_first = {}
            for i, f in enumerate(first):
                by_first.setdefault(f, []).append(i)
            c = self.memo.lib[("route", key)] = (bases, first, by_first)
            self.memo.counts["g58_route_built"] += 1
        else:
            self.memo.counts["g58_route_cached"] += 1
        if G58_AUDIT["on"]:
            fresh = [self.expand([p]) for p in prims]
            if [None if b is None else list(b) for b in c[0]] != [None if b is None else list(b) for b in fresh]:
                _g58_violation("routing_bases", prims)
        return c

    def _scan_table(self, names):
        """G58: `_scan`'s primitive table (bounded): (primitive, base tuple) for those that expand,
        each one's first base relation, and the indices by first relation -- the same values the
        scan builds, cached per library generation and primitive list."""
        caps = self.state["capabilities"]
        key = ("scan", self.memo.lib_gen, id(caps), len(caps), tuple(names))
        c = self.memo.lib.get(key)
        if c is None:
            if len(self.memo.lib) > 4096:
                self.memo.lib.clear()
            bases, _, _ = self._routing(names)
            prims = [(p, tuple(b)) for p, b in zip(names, bases) if b is not None]
            first = {p: (pb[0].split(":")[1] if pb[0].startswith("until:") else pb[0]) for p, pb in prims}
            by_first = {}
            for i, (p, pb) in enumerate(prims):
                by_first.setdefault(first[p], []).append(i)
            c = self.memo.lib[key] = (prims, first, by_first)
        return c

    def primitives(self, name):
        prims = [f"rel:{r}" for r in self.relations()]
        if self.routed and not self.operators:
            caps = self._cx_offered(name)
            if G58_AUDIT["on"]:
                fresh = []
                if self.use_library:
                    for n in sorted(self.state["capabilities"]):
                        ver = self.version(n)
                        if n == name or not ver or ver["status"] not in EXEC_OK:
                            continue
                        if self.qualified_library and ver["status"] != "qualified":
                            continue
                        if any(dn == name for dn, _ in self._closure(n, ver["v"])):
                            continue
                        fresh.append(f"cap:{n}@{ver['v']}")
                if fresh != list(caps):
                    _g58_violation("offered", name)
            return prims + caps
        if self.use_library:
            for n in sorted(self.state["capabilities"]):
                ver = self.version(n)
                if n == name or not ver or ver["status"] not in EXEC_OK:
                    continue
                if self.qualified_library and ver["status"] != "qualified":
                    continue  # G51 arm Q: only qualified capabilities feed later acquisition
                clo = self._closure_cached(n, ver) if self.routed else self._closure(n, ver["v"])
                if any(dn == name for dn, _ in clo):
                    continue  # would create a cycle
                prims.append(f"cap:{n}@{ver['v']}")
        if self.operators:
            prims += self._operator_prims(name)
        return prims

    # ---------- G58: capability index ----------

    def _cx_entry(self, n):
        """(offered, primitive, base, first relation, closure names) of a capability's current version:
        offered = what `_offered`'s loop tests apart from the name itself and cycles."""
        ver = self.version(n)
        if not ver:
            return (False, None, None, None, frozenset())
        offer = self.use_library and ver["status"] in EXEC_OK and \
            (not self.qualified_library or ver["status"] == "qualified")
        clo = frozenset(dn for dn, _ in self._closure_cached(n, ver))
        p = f"cap:{n}@{ver['v']}"
        base = self.expand([p]) if offer else None
        first = None if not base else (base[0].split(":")[1] if base[0].startswith("until:") else base[0])
        return (offer, p, tuple(base) if base is not None else None, first, clo)

    def _cx(self):
        """G58 (docs/G58.md §2b): the capability index, synced with the capability records. Rebuilt
        when the records object or the library flags change; otherwise only the names written since
        the last sync (`cx_dirty`: status changes and new versions) and every capability whose
        closure holds one of them (its base depends on their statuses) are recomputed."""
        m, caps = self.memo, self.state["capabilities"]
        X = m.cx
        flags = (self.use_library, self.qualified_library)
        if X is None or X["caps"] is not caps or X["flags"] != flags:
            X = m.cx = {"caps": caps, "flags": flags, "ent": {}, "order": [], "order_p": [], "by_first": {},
                        "rdep": {}}
            todo = list(caps)
            m.counts["g58_cx_rebuilt"] += 1
        else:
            todo = set(m.cx_dirty)
            for n in m.cx_dirty:
                todo |= X["rdep"].get(n, set())
            todo |= {n for n in caps if n not in X["ent"]} if len(X["ent"]) < len(caps) else set()
        m.cx_dirty = set()
        ent, order, order_p, by_first, rdep = X["ent"], X["order"], X["order_p"], X["by_first"], X["rdep"]
        for n in sorted(todo):
            old = ent.get(n)
            if old is not None and old[0]:
                i = bisect.bisect_left(order, n)
                del order[i], order_p[i]
                if old[3] is not None:
                    lst = by_first[old[3]]
                    del lst[bisect.bisect_left(lst, n)]
                for dn in old[4]:
                    rdep[dn].discard(n)
            new = ent[n] = self._cx_entry(n) if n in caps else (False, None, None, None, frozenset())
            if new[0]:
                i = bisect.bisect_left(order, n)
                order.insert(i, n)
                order_p.insert(i, new[1])
                if new[3] is not None:
                    bisect.insort(by_first.setdefault(new[3], []), n)
                for dn in new[4]:
                    rdep.setdefault(dn, set()).add(n)
        if G58_AUDIT["on"]:  # every entry equals a fresh one
            for n in caps:
                if ent.get(n) != self._cx_entry(n):
                    _g58_violation("cx_entry", n)
        return X

    def _cx_offered(self, name):
        """`_offered(name)` from the index: every offered capability but the name itself and those
        whose closure holds it (a cycle), in name order."""
        X = self._cx()
        excl = {n for n in X["rdep"].get(name, ()) if X["ent"][n][0]}
        if X["ent"].get(name, (False,))[0]:
            excl.add(name)
        order, order_p = X["order"], X["order_p"]
        if not excl:
            return list(order_p)
        out, j = [], 0
        for i in sorted(bisect.bisect_left(order, n) for n in excl):
            out += order_p[j:i]
            j = i + 1
        out += order_p[j:]
        return out

    def _cx_router(self, name, rels):
        """The primitives of `primitives(name)` whose base is defined and starts with a relation in
        a set `here`, in `primitives` order (relation primitives in relation order, then capabilities
        in name order), as a function of `here` -> [(primitive, base tuple, first relation)]. For one
        scan or activation walk (no record changes during it): per-relation lists and per-set results
        are kept for its duration."""
        X = self._cx()
        ent, by_first = X["ent"], X["by_first"]
        excl = X["rdep"].get(name, ())
        per_rel, per_set = {}, {}

        def rel_items(r):
            got = per_rel.get(r)
            if got is None:
                got = []
                k = rels.get(r)
                if k is not None:
                    got.append(((0, k, ""), f"rel:{r}", (r,), r))
                for n in by_first.get(r, ()):
                    if n != name and n not in excl:
                        e = ent[n]
                        got.append(((1, 0, n), e[1], e[2], r))
                per_rel[r] = got
            return got

        def visit(here):
            key = frozenset(here)
            got = per_set.get(key)
            if got is None:
                items = []
                for r in key:
                    items += rel_items(r)
                if len(key) > 1:
                    items.sort(key=lambda t: t[0])
                got = per_set[key] = [t[1:] for t in items]
            return got
        return visit

    def _operator_prims(self, name):
        """until:R:Q:T steps. Predicates (Q, T) are the properties every observed answer
        shares; R ranges over the told relations other than Q."""
        ref = self._idx()["ref"]
        vals = {v for _, v in self.state["observations"].get(name, []) if v not in (NONE, SEVERAL)}  # L3 of e944840
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
                seqs, pr = self._activated(prims, n, start, name=name if self.routed else None)
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

    def _predictions(self, seq, also=None):
        dom = self._domain(seq)
        out = {}
        if also is not None:  # G57b sparse table: entities in dom or `also`, in entity order
            pos = self._idx()["pos"]
            ents = sorted({e for e in dom if e in pos} | {e for e in also if e in pos}, key=pos.__getitem__)
        else:
            ents = self.entities()
        for e in ents:
            if e not in dom:
                out[e] = None
                continue
            r = self.execute(seq, e)
            out[e] = next(iter(r)) if r and len(r) == 1 else None
        return out

    def _outcomes(self, seq):
        """Answer class per entity (value, !none, !several) for PX investigate."""
        return {e: outcome(self.execute(seq, e)) for e in self.entities()}

    def _differs(self, seq, preds, sparse=False) -> bool:
        """Extensional difference from a prediction table; stops at the first entity that differs.
        Only entities where either side can be defined are checked (exact). G57b `sparse`: the
        table omits entities predicted None; they are visited too when in this program's domain,
        in entity order (the same visits as the full table)."""
        dom = self._domain(seq)
        items = preds.items()
        if sparse:
            pos = self._idx()["pos"]
            items = [(e, preds.get(e)) for e in sorted(set(preds) | {e for e in dom if e in pos}, key=pos.__getitem__)]
        for e, v in items:
            if v is None and e not in dom:
                continue
            r = self.execute(seq, e)
            if (next(iter(r)) if r and len(r) == 1 else None) != v:
                return True
        return False

    def acquire(self, name, max_len=None) -> dict:
        obs0 = self.state["observations"].get(name, [])
        if obs0 and not any(v not in (NONE, SEVERAL) for _, v in obs0):
            # verification P1 of e944840: statements only rule programs out; with no value example
            # nothing has been shown, so nothing is adopted (an empty-supported program would answer)
            return {"name": name, "result": "none", "reason": "no value example", "evaluated": 0,
                    "pruned": 0, "live": 0, "zero_support": 0}
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
            # verification N1b of 3e2783c: as in programs mode (N1 of 050bebd), a base re-acquisition
            # that does not return the current version (none found, or several) caps it at provisional
            if cur and cur["status"] == "qualified":
                self._set_status(name, cur["v"], "provisional",
                                 "several supported programs" if supported else "re-acquisition found no candidate")
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
        result["version"], result["events"] = self._adopt(name, cand, status, blocking, scan,
                                                          domain=scan.pop("domain_set", None))
        result["result"] = self.version(name)["status"]  # L1 of cdb4828: may be capped by a dependency
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
        # verification H1 of b2bb9b8: closed-world judgments refute the less-defined alternatives
        # that mask a data-dependent guard space, so with a `complete` observation the guard space
        # must be every (Q, T) pair on the component (observation-independent). Guards on pairs
        # absent from the component are constant there and can be removed without growing a
        # program, so the scan then covers every grammar program up to MAX_SIZE. If the pairs exceed
        # MAX_GUARDS the space stays data-dependent and qualification is capped at provisional.
        # `not:` on a pair absent from the component is the identity filter; one absent pair
        # (`absent absent`, unless told) keeps such programs expressible (verifier soundness seed 21).
        gap = []
        if any(s_ in self._closed() for s_, _ in obs):
            allp = sorted({(q, t) for q, m in sub.items() for ts in m.values() for t in ts})
            nil = next(("absent", f"absent{i}" if i else "absent") for i in range(len(allp) + 1)
                       if ("absent", f"absent{i}" if i else "absent") not in allp)
            allp.append(nil)
            gap = [g for g in allp if g not in guards]
            if gap and len(allp) <= self.closed_guards:
                guards, gap = guards + gap, []
        dom = sorted(e for e in self.entities() if e in comp)
        ind = progs.Inducer(ctx, obs, dom, (rels, caps), guards, closed=self._closed())
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
            # verification N1 of 050bebd: a re-acquisition that does not return the current version
            # (none found, or several) leaves it without a scan on current knowledge: not qualified
            if cur and cur["status"] == "qualified":
                self._set_status(name, cur["v"], "provisional",
                                 "several supported programs" if reps else "re-acquisition found no candidate")
            return result
        cand = reps[0]
        cand_pred = {e: progs.run(ctx, cand, e) for e in ind.domain}
        # full horizon (MAX_SIZE), as the base engine's deepening budget (audit 283f526 P0;
        # verification N2 of 82dd0a2: the candidate-size horizon was the removed short horizon)
        horizon = progs.MAX_SIZE
        # G49: exact pruned scan (programs.Exact, proven against brute force); same open-world rule,
        # every program up to MAX_SIZE is decided, grouped by behaviour (docs/G49.md)
        ex = progs.Exact(ind).run(cand, cand_pred)
        blockers, complete, examined = ex["blockers"], ex["complete"], ex["programs"]
        status = "qualified" if complete and not blockers and not gap else "provisional"
        scan = {"horizon": horizon, "domain": len(dom), "guard_gap": len(gap), "scanned": examined, "complete": complete,
                "method": "exact", "budget": progs.EXACT_BUDGET, "combos": ex["combos"],
                "behaviours": ex["behaviours"], "blocking_behaviours": ex["blocking_behaviours"],
                "universe": ex["universe"],
                "blocking_n": len(blockers), "compatible": 0, "pruned_compatible": 0,
                "assumption": "G48 open world: every non-contradicted program up to MAX_SIZE tokens is an "
                              "alternative; qualified only if every program is decided (exact scan "
                              "completes) with no blocker."}
        blocking = [[b] for b in blockers]
        h = {"seq": [progs.fmt(cand)], "status": "supported", "support": len(obs)}
        record.update({"candidate": h["seq"], "blocking": blocking, "scan": scan,
                       "selection": "smallest supported G48 program; qualified only if the open-world scan completes "
                                    "with no blocker"})
        record["evaluated"] = ind.examined + ex["combos"]
        result.update({"result": status, "seq": h["seq"], "blocking": blocking, "scan": scan,
                       "evaluated": record["evaluated"]})
        result["version"], result["events"] = self._adopt(name, h, status, blocking, scan, domain=dom)
        result["result"] = self.version(name)["status"]  # L1 of cdb4828: may be capped by a dependency
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
        neg = {s_ for s_, v in obs if v in (NONE, SEVERAL)}  # PX: negative statements are checked too
        sparse = self._ix_live()
        # G57b: with the persistent index, only the entries the scan reads (domain and negative
        # subjects), in entity order; the omitted ones are None (see _differs)
        mine = self._predictions(cand_seq, also=neg) if sparse else self._predictions(cand_seq)
        cand_base = tuple(self.expand(cand_seq))
        D = [e for e, v in mine.items() if v is not None or e in neg]
        want = [mine[e] for e in D]
        pos = {e: i for i, e in enumerate(D)}
        obs_at = [(pos[s_], v) for s_, v in obs if s_ in pos]
        closed_at = {pos[x] for x in self._closed() if x in pos}  # G49: closed-world at `complete` subjects
        jf = lambda i, o, v: judge_closed(o, v) if i in closed_at else judge_set(o, v)  # noqa: E731
        scan_tab = None
        if self.routed and self.bounded:
            # G58: no primitive table; each node's visit list comes from the capability index
            scan_tab = self._cx_router(name, {r: k for k, r in enumerate(self.relations())})
            prims = None
        else:
            prims = [(p, self.expand([p])) for p in self.primitives(name)]
            prims = [(p, tuple(b) if self.bounded else b) for p, b in prims if b is not None]
        out = {"horizon": horizon, "domain": len(D), "domain_set": sorted(D), "scanned": 0, "evaluated": 0, "contradicted": 0,
               "compatible": 0, "pruned_compatible": 0, "blocking_n": 0, "conflicts": 0, "assumption": self.ASSUMPTION}
        blocking = []

        img = {}

        def step(front, base):
            if self.bounded:
                # G53: the image of a set under a primitive is the union of its nodes' images
                # (relation steps and until steps both act node by node), so per-(primitive, node)
                # images are cached for the whole scan. Exact: same fronts as the uncached walk.
                # Fronts are sparse ({domain index: non-empty set}); a missing index is empty.
                new = {}
                for i, cur in front.items():
                    out = set()
                    for x in cur:
                        k = (base, x)
                        r = img.get(k)
                        if r is None:
                            r = {x}
                            for t in base:
                                if not r:
                                    break
                                r = self._step_set(r, t)
                            img[k] = r
                        out |= r
                    if out:
                        new[i] = out
                return new
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
        level, seen = [([], ({i: {e} for i, e in enumerate(D)} if self.bounded else [{e} for e in D]), ())], {()}
        E0 = set()
        outrel = self._idx()["out"]
        if scan_tab is not None:
            first, by_first = {}, None
            out["pruned_counting"] = "visited nodes only (--bounded)"
        else:
            first = {p: (pb[0].split(":")[1] if pb[0].startswith("until:") else pb[0]) for p, pb in prims}
            by_first = {}
        if self.bounded and scan_tab is None:
            # G53: primitives indexed by their first base relation; a node visits only those that
            # leave its frontier, in the original primitive order. The skipped ones are exactly the
            # relevance-pruned ones (empty image whatever the path), so no decision changes; only
            # the pruned_compatible count is no longer kept for them.
            for i, (p, pb) in enumerate(prims):
                by_first.setdefault(first[p], []).append(i)
            out["pruned_counting"] = "visited nodes only (--bounded)"
        for depth in range(1, horizon + 1):
            nxt_level = []
            for prefix, front, bseq in level:
                here = set()
                for f in (front.values() if self.bounded else front):
                    for x in f:
                        here |= outrel.get(x, set())
                if scan_tab is not None:
                    vv = scan_tab(here)
                    for p, _, f in vv:
                        first[p] = f
                    visit = [(p, pb) for p, pb, _ in vv]
                    if G58_AUDIT["on"]:
                        ref_tab = self._scan_table(self.primitives(name))
                        ref = [ref_tab[0][i] for i in sorted(i for r in here for i in ref_tab[2].get(r, ()))]
                        if ref != visit:
                            _g58_violation("scan_visit", (name, sorted(here)))
                elif self.bounded:
                    visit = [prims[i] for i in sorted(i for r in here for i in by_first.get(r, ()))]
                else:
                    visit = prims
                for p, pb in visit:
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
                    if not (nf if self.bounded else any(nf)):
                        out["pruned_compatible"] += 1  # a distinct-base node, standing for its whole subtree
                        continue
                    seq = prefix + [p]
                    out["scanned"] += 1
                    if key != cand_base:
                        out["evaluated"] += len(obs_at)
                        if self.bounded:
                            at = lambda i: nf.get(i, E0)  # noqa: E731
                        else:
                            at = nf.__getitem__
                        if any(jf(i, at(i), v) == "contradicted" for i, v in obs_at):
                            out["contradicted"] += 1
                        else:
                            support = sum(jf(i, at(i), v) == "supported" for i, v in obs_at)
                            if self.bounded:
                                conflict = any(len(f) == 1 and next(iter(f)) != want[i] for i, f in nf.items())
                            else:
                                vals = [next(iter(f)) if len(f) == 1 else None for f in nf]
                                conflict = any(x is not None and x != w for x, w in zip(vals, want))
                            if conflict or (support >= 1 and self._differs(seq, mine, sparse)):
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

    def _adopt(self, name, h, status, blocking, scan=None, domain=None):
        if status == "qualified" and self._deps_unqualified(h["seq"]):
            # verification L1 of cdb4828: a qualified capability cannot rest on a dependency that
            # is not itself qualified; its closed or open judgment is only relative to that version
            status = "provisional"
        cap = self.state["capabilities"].setdefault(name, {"current": None, "versions": [], "express": None})
        if self.memo is not None:
            self.memo.sx_dirty.add(name)  # G58: its domain or current version may change here
            if self.memo.scope is not None:
                self.memo.scope.setdefault("caps", set()).add(name)  # G58: this record is written here
        cur = self.version(name)
        evidence = {"observations": len(self.state["observations"].get(name, [])),
                    "support": h["support"], "blocking": len(blocking), "turn": self._tick()}
        evidence["basis"] = self._basis(name)  # G53: what the decision was made on
        if scan:
            evidence.update({"horizon": scan["horizon"], "blocking_total": scan["blocking_n"],
                             "compatible": scan["compatible"], "pruned_compatible": scan["pruned_compatible"]})
        if cur and self.expand(cur["seq"]) == self.expand(h["seq"]) and cur["status"] in EXEC_OK + ("suspended",):
            cur["evidence"] = evidence
            if domain is not None:
                cur["domain"] = list(domain)
            return cur["v"], self._set_status(name, cur["v"], status, "requalified")
        events = []
        if cur and cur["status"] in EXEC_OK:
            events += self._set_status(name, cur["v"], "superseded", f"replaced by v{len(cap['versions']) + 1}")
        ver = {"v": len(cap["versions"]) + 1, "seq": h["seq"], "base": self.expand(h["seq"]),
               "status": status, "evidence": evidence,
               "history": [{"turn": evidence["turn"], "status": status, "reason": "acquired"}]}
        if status == "qualified":
            ver["qualified_at"] = [evidence["turn"]]
        if domain is not None:
            ver["domain"] = list(domain)  # verification M2 of b2bb9b8: the scope "qualified" was decided on
        cap["versions"].append(ver)
        cap["current"] = ver["v"]
        if self.memo is not None:
            self.memo.lib_gen += 1  # G58
            self.memo.rv_dirty.add((name, None))
            self.memo.cx_dirty.add(name)
            if self.memo.scope is not None:
                self.memo.scope.setdefault("caps", set()).add(name)
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
        preds = {tuple(h): (self._outcomes(h) if self.answers else self._predictions(h)) for h in live}
        best, best_score = None, 0
        # programs mode: ties broken by entity name, not by fact storage order, which adaptive
        # retention changes when it restores a component (G48 H6 failure, docs/G48.md).
        # G50 (docs/G50.md, G49 D1 failure): among equally splitting subjects, the one with the
        # smallest closure (entities reachable along told facts) first, then the name. A smaller
        # closure means fewer facts the answer can depend on; it is order-independent.
        size = self._closure_sizes() if self.programs else {}
        tie = (lambda e: (size.get(e, 0), e)) if self.programs else None  # noqa: E731
        for e in self._question_pool(name):
            if e in done:
                continue
            if self.answers:
                # PX: every answer class can be stated (value, !none, !several); an answer removes every
                # hypothesis of another class from the supported set. Worst case over the classes.
                allp = [p[e] for p in preds.values()]
                if len(set(allp)) < 2:
                    continue
                score = min(len(allp) - allp.count(c) for c in set(allp))
                if score > best_score or (tie and score == best_score and score and tie(e) < tie(best)):
                    best, best_score = e, score
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
                if score > best_score or (score == best_score and score and tie(e) < tie(best)):
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

    def _question_pool(self, name):
        """Entities investigate may ask about. Programs mode: only the relevance component of the
        observations (the domain the acquisition uses; G48R H6 failure: questions about other,
        possibly archived, worlds), in name order (G48 H6 failure: fact storage order)."""
        if not self.programs:
            return self.entities()
        comp = self._component({x for o in self.state["observations"].get(name, []) for x in o})
        return sorted(e for e in self.entities() if e in comp)

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
        if self._gated():
            fp = self._answer_fp(s, target)
            hit = self.memo.answers.get((s, word))
            if hit and hit[0] == fp:
                self.stats["gated"] = self.stats.get("gated", 0) + 1
                return copy.deepcopy(hit[1])
            out = self._answer_exec(s, target)
            self.memo.answers[(s, word)] = (fp, copy.deepcopy(out))
            return out
        return self._answer_exec(s, target)

    def _gated(self) -> bool:
        """G57 (a): re-asks are answered from the memo only inside a read-only call (every line a
        question, so nothing in the state changes during it) and only in the configuration whose
        dependencies `_answer_fp` covers: base relations and capabilities, geometric execution,
        static retention, no programs or operators."""
        return self.readonly_call and self.memo is not None and self.geometry and not self.programs \
            and not self.operators and self.retention == "static"

    def _cap_hash(self, name):
        if name not in self._cap_fp:  # once per read-only call: nothing changes during it
            self._cap_fp[name] = hashlib.sha256(json.dumps(self.state["capabilities"].get(name),
                                                           sort_keys=True).encode()).hexdigest()
        return self._cap_fp[name]

    def _answer_fp(self, s, target):
        """Everything the capability path of `answer` (and `say` after it) reads, besides recall,
        which is unknown here and decided exactly by the memo:
        - the records of `target` and of every capability its versions reach through `cap:` steps
          (status, seq, pinned versions, domain, express);
        - the expanded base relations and the change stamp of each (`execute` reads only the
          triples of those relations, through the index);
        - whether s is a known entity (`execute` returns the empty set otherwise);
        - the construction library (`say`)."""
        caps, todo = set(), [target]
        while todo:
            n = todo.pop()
            if n in caps:
                continue
            caps.add(n)
            for ver in (self.state["capabilities"].get(n) or {}).get("versions", []):
                for d in _deps_of(ver["seq"]):
                    todo.append(_split_cap(d)[0])
        ver = self.version(target)
        base = self.expand(ver["seq"]) if ver and ver["status"] in EXEC_OK else None
        rels = tuple(base) if base is not None else None
        stamps = tuple(self.memo.stamp.get(r, 0) for r in base) if base is not None else None
        if "lib" not in self._cap_fp:
            self._cap_fp["lib"] = hashlib.sha256(json.dumps(self.state["library"], sort_keys=True).encode()).hexdigest()
        return (target, tuple(sorted((n, self._cap_hash(n)) for n in caps)), rels, stamps,
                s in self._idx()["pos"], self._cap_fp["lib"])

    def _answer_exec(self, s, target) -> dict:
        ver = self.version(target)
        if ver and ver["status"] in EXEC_OK:
            out = self.execute(ver["seq"], s)
            if out and len(out) == 1:
                # verification M2 of b2bb9b8: qualified only inside the domain the scan decided;
                # elsewhere (entities outside it, or told later) the answer is provisional
                outside = ver["status"] == "qualified" and "domain" in ver and s not in self._dom_set(target, ver)
                return {"status": "known", "value": next(iter(out)), "relation": target,
                        "via": f"cap:{target}@{ver['v']}", "provisional": ver["status"] == "provisional" or outside,
                        **({"scope": "outside acquisition domain"} if outside else {})}
            if out:
                return {"status": "ambiguous", "value": None, "candidates": sorted(out), "relation": target,
                        "via": f"cap:{target}@{ver['v']}"}
        if ver and ver["status"] not in EXEC_OK:
            return {"status": "unknown", "value": None, "relation": target, "note": f"{target}@{ver['v']} {ver['status']}"}
        return {"status": "unknown", "value": None, "relation": target}

    def _dom_set(self, name, ver):
        # keyed on the domain's content (Info 2 of verify-35bda6b: an id() key can return a stale set
        # after CPython reuses a replaced list's address); a list compare is cheaper than the set build
        key = (name, ver["v"])
        c = getattr(self, "_dom_cache", {})
        if c.get("key") != key or c.get("domain") != ver["domain"]:
            c = {"key": key, "domain": list(ver["domain"]), "set": set(ver["domain"])}
            self._dom_cache = c
        return c["set"]

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

    def _known_entities(self):
        if getattr(self, "_ents", None) is None:
            self._ents = {x for f in self.state["facts"] for x in (f["s"], f["o"])}
        return self._ents

    def _grow(self, s, was_known=True):
        # A told fact changes program values only at its subject's outgoing edges. If the subject
        # was not a known entity before the fact, no value at any previously known entity changes,
        # so no earlier scan decision rests on it (answers there stay scoped by M2 of b2bb9b8).
        if was_known:
            self._grown = getattr(self, "_grown", set()) | {s}

    def _flush_growth(self):
        """verification S1 of cdb4828: a qualified version's uniqueness was decided on the facts
        of its region (the component of its recorded domain and observed subjects) as they were.
        When told facts with a subject in that region are added or removed, the version is
        re-acquired, which re-runs the scan on current facts. Batched: pending growth is handled
        before the next line that is not a `fact` line, and before saving."""
        grown, self._grown = getattr(self, "_grown", set()), set()
        if not grown:
            return
        if self.routed and self.memo is not None:
            return self._flush_growth_routed(grown)
        for n in sorted(self.state["capabilities"]):
            ver = self.version(n)
            obs = self.state["observations"].get(n, [])
            if not ver or ver["status"] != "qualified" or not obs:
                continue
            seeds = set(ver.get("domain", [])) | {s_ for s_, _ in obs}
            if self.memo is not None:  # G57 (b): component classes kept across calls
                self._idx()
                hit = self.memo.region_hits(seeds, grown)
            else:
                hit = bool(grown & self._component(seeds))
            if hit:
                self.stats["grown_requalified"] = self.stats.get("grown_requalified", 0) + 1
                self.acquire(n)

    def _sx(self):
        """G58: entity -> names whose current version's domain or observed subjects hold it, synced
        with `sx_dirty` (domain, version and observation writes); rebuilt when the records change
        object or the observations are rewritten."""
        m, caps = self.memo, self.state["capabilities"]
        S = m.sx
        if S is None or S["caps"] is not caps or S["obs"] is not self.state["observations"]:
            S = m.sx = {"caps": caps, "obs": self.state["observations"], "seeds": {}, "by_ent": {}}
            todo = set(caps)
        else:
            todo = set(m.sx_dirty)
            if len(S["seeds"]) < len(caps):
                todo |= {n for n in caps if n not in S["seeds"]}
        m.sx_dirty = set()
        seeds, by_ent = S["seeds"], S["by_ent"]
        for n in todo:
            for x in seeds.get(n, ()):
                by_ent[x].discard(n)
            ver = self.version(n) if n in caps else None
            new = (set(ver.get("domain", [])) | {s_ for s_, _ in self.state["observations"].get(n, [])}) if ver else set()
            seeds[n] = new
            for x in new:
                by_ent.setdefault(x, set()).add(n)
        if G58_AUDIT["on"]:  # every capability's seeds equal fresh ones
            for n in caps:
                ver = self.version(n)
                fresh = (set(ver.get("domain", [])) | {s_ for s_, _ in self.state["observations"].get(n, [])}) if ver else set()
                if seeds.get(n) != fresh or any(n not in by_ent.get(x, ()) for x in fresh):
                    _g58_violation("sx_seeds", n)
        return S

    def _flush_growth_routed(self, grown):
        """G58 (docs/G58.md §2c): `_flush_growth` visiting only capabilities whose region can hold a
        grown entity. A region is the seeds plus the union-find classes of the seeds, so a version
        hits only if some grown entity is a seed or shares a class with one: the candidates are the
        names indexed at the grown entities and at every member of their classes. They are taken in
        name order with the same test as the full loop; after each re-acquisition the candidates are
        recomputed (records may change) and only names after it are taken, as the loop would."""
        m = self.memo
        if not m.track_members:
            m.track_members, m.uf, m.members = True, None, None  # classes rebuilt with members

        def cands():
            self._idx()
            m.region_hits(set(), set())  # builds the classes (with members) if needed
            S = self._sx()
            by_ent, c = S["by_ent"], set()
            for g in grown:
                c |= by_ent.get(g, set())
                if g in m.uf:
                    r = m._find(g)
                    for x in m.members.get(r) or [r]:
                        c |= by_ent.get(x, set())
            return c

        last = None
        while True:
            todo = sorted(n for n in cands() if last is None or n > last)
            if G58_AUDIT["on"]:
                for n in sorted(self.state["capabilities"]):
                    ver, obs = self.version(n), self.state["observations"].get(n, [])
                    if (last is None or n > last) and n not in todo and ver and ver["status"] == "qualified" and obs \
                            and m.region_hits(set(ver.get("domain", [])) | {s_ for s_, _ in obs}, grown):
                        _g58_violation("flush_missed", n)
            m.counts["g58_flush_routed"] += 1
            m.counts["g58_flush_unseen"] += len(self.state["capabilities"]) - len(todo)
            hit_at = None
            for n in todo:
                ver = self.version(n)
                obs = self.state["observations"].get(n, [])
                if not ver or ver["status"] != "qualified" or not obs:
                    continue
                if m.region_hits(set(ver.get("domain", [])) | {s_ for s_, _ in obs}, grown):
                    hit_at = n
                    break
            if hit_at is None:
                return
            self.stats["grown_requalified"] = self.stats.get("grown_requalified", 0) + 1
            self.acquire(hit_at)
            last = hit_at

    def turn(self, line: str) -> str:
        if getattr(self, "_grown", None) and not line.strip().lower().startswith("fact "):
            self._flush_growth()
        reply = self._turn(line)
        if getattr(self, "_fc_names", None):
            self._fc_requalify()
        return reply

    # ---------- G49: scoped closed-world statements (`complete X`, docs/G49.md) ----------

    def _closed(self) -> set:
        return set(self.state.get("complete", {}))

    def _judge(self, s, out, v):
        return judge_closed(out, v) if s in self.state.get("complete", {}) else judge_set(out, v)

    def _closure_sizes(self) -> dict:
        """Number of entities reachable from each entity along told facts (itself included);
        exact, computed once per index (G50 tie-break)."""
        idx = self._idx()
        if "closure_sizes" not in idx:
            adj = {}
            for f in self.state["facts"]:
                if not f["r"].startswith("cap:") and any(sp["kind"] == "told" for sp in f["supports"]):
                    adj.setdefault(f["s"], set()).add(f["o"])
            sizes = {}
            for x in idx["names"]:
                seen, todo = {x}, [x]
                while todo:
                    for z in adj.get(todo.pop(), ()):
                        if z not in seen:
                            seen.add(z)
                            todo.append(z)
                sizes[x] = len(seen)
            idx["closure_sizes"] = sizes
        return idx["closure_sizes"]

    def _reach(self, x) -> list:
        """Entities reachable from x along told facts (outgoing), x included: every fact a program
        run from x can read has its subject here."""
        if self.routed and self._ix_live():
            # G58: the same told, non-cap out-edges, read per visited node from the persistent index
            ix = self.memo.ix
            self.memo.counts["g58_reach_indexed"] += 1
            seen, todo = {x}, [x]
            while todo:
                y = todo.pop()
                for r in ix["out"].get(y, ()):
                    if r.startswith("cap:"):
                        continue
                    for f in ix["by_sr"].get((y, r), ()):
                        z = f["o"]
                        if z not in seen and any(sp["kind"] == "told" for sp in f["supports"]):
                            seen.add(z)
                            todo.append(z)
            if G58_AUDIT["on"]:
                self.routed = False
                try:
                    if self._reach(x) != sorted(seen):
                        _g58_violation("reach", x)
                finally:
                    self.routed = True
            return sorted(seen)
        adj = {}
        for f in self.state["facts"]:
            if not f["r"].startswith("cap:") and any(sp["kind"] == "told" for sp in f["supports"]):
                adj.setdefault(f["s"], set()).add(f["o"])
        seen, todo = {x}, [x]
        while todo:
            for z in adj.get(todo.pop(), ()):
                if z not in seen:
                    seen.add(z)
                    todo.append(z)
        return sorted(seen)

    def complete(self, x) -> str:
        if self.retention == "adaptive":
            return "complete is not supported with adaptive retention"
        clo = self._reach(x)
        self.state.setdefault("complete", {})[x] = {"turn": self._tick(), "closure": clo}
        self._dirty()
        self._fc_touch({n for n, obs in self.state["observations"].items() if any(s_ == x for s_, _ in obs)})
        return f"complete {x} ({len(clo)} entities)"

    def _basis(self, name):
        """G53: digest of everything an acquisition decision depends on apart from the closed
        set: the facts (epoch), the offered primitives, the observations and the horizon."""
        key = json.dumps([self.state.get("fact_epoch", 0), self.primitives(name),
                          self.state["observations"].get(name, []), self.deepen, self.use_library])
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def _fc_touch(self, names):
        self._fc_names = getattr(self, "_fc_names", set()) | set(names)

    def _fc_violated(self, s, why):
        """A told fact added or removed with its subject inside a stated closure falsifies that
        statement: it is retracted (kept in complete_log) and the capabilities observed there are
        re-acquired on open-world judgment."""
        cm = self.state.get("complete", {})
        hit = [x for x, e in cm.items() if s in e["closure"]]
        for x in hit:
            e = cm.pop(x)
            self.state.setdefault("complete_log", []).append(
                {"x": x, "stated": e["turn"], "retracted": self.state["turn"], "reason": why})
            self._fc_touch({n for n, obs in self.state["observations"].items() if any(s_ == x for s_, _ in obs)})

    def _fc_requalify(self):
        names, self._fc_names = sorted(self._fc_names), set()
        for n in names:
            obs = self.state["observations"].get(n)
            if obs:
                # verification M1 of b2bb9b8: review the current version under the new judgment
                # first (as `observe` does); a contradicted version is suspended whatever `acquire` finds
                ver = self.version(n)
                h = self.evaluate(ver["seq"], obs) if ver and ver["status"] in EXEC_OK else None
                if h and h["status"] == "contradicted":
                    self._set_status(n, ver["v"], "suspended", "contradicted by its observations (complete)")
                if (self.bounded and not self.programs and h
                        and h["status"] == "supported" and ver["status"] == "qualified"
                        and ver.get("evidence", {}).get("basis") == self._basis(n)):
                    # G53 (base engine): a new `complete` statement only adds closed judgments, which
                    # shrink both the supported set and the non-contradicted alternatives. A qualified
                    # version still supported stays the unique shortest supported program with no
                    # blocker, so re-acquiring cannot change it (exact) -- provided nothing else the
                    # decision rests on (facts, offered primitives, observations) changed since it
                    # was made (`basis`). A retraction always follows a told-fact change, so it always
                    # changes the basis and is never skipped. Programs mode is excluded:
                    # there `complete` also changes the guard space (H1 rule of b2bb9b8).
                    self.stats["fc_skipped"] = self.stats.get("fc_skipped", 0) + 1
                    continue
                self.acquire(n)

    def _turn(self, line: str) -> str:
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
        if head == "complete" and len(rest) >= 1:
            return "; ".join(self.complete(x) for x in rest)
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


def parse_cli(argv):
    """Engine keyword arguments from CLI flags; returns (kw, remaining args). Shared with serve.py."""
    flags = {"--no-library": ("use_library", False), "--no-geometry": ("geometry", False),
             "--no-activation": ("activation", False), "--operators": ("operators", True),
             "--adaptive-retention": ("retention", "adaptive"), "--programs": ("programs", True), "--answers": ("answers", True),
             "--qualified-library": ("qualified_library", True),
             "--bounded": ("bounded", True), "--lean": ("lean", True), "--indexed": ("indexed", True), "--incremental": ("incremental", True),
             "--routed": ("routed", True), "--partitioned": ("partitioned", True)}
    kw = dict(flags[a] for a in argv if a in flags)
    for a in argv:
        if a.startswith("--deepen="):
            kw["deepen"] = int(a.split("=", 1)[1])
        if a.startswith("--closed-guards="):
            kw["closed_guards"] = int(a.split("=", 1)[1])
    argv = [a for a in argv if a not in flags and not a.startswith(("--deepen=", "--closed-guards="))]
    return kw, argv


def main(argv) -> int:
    if len(argv) < 2:
        print("usage: python -m packetlm.engine STATE 'line' ['line' ...]")
        return 2
    t0 = time.process_time()
    kw, argv = parse_cli(argv)
    # verification Low 2 of d6cbcf3: a long-lived server's journal with records holds calls the
    # snapshot does not; this per-process engine would read the older snapshot. Refuse instead.
    jp = Path(argv[0] + ".journal")
    if jp.exists() and len(jp.read_bytes().splitlines()) > 1:
        print(json.dumps({"error": "unclosed packetlm.serve journal: open this path with packetlm.serve to recover it"}))
        return 3
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
