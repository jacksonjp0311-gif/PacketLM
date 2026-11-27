"""Evidence-gated adaptive retention (docs/ARET.md). Archive, never delete.

The hot state is what every call loads, validates and saves, so its size is a per-call
cost (the utility problem). Adaptive retention moves a knowledge *component* that the
evidence says is rarely touched out of the hot state into an immutable, content-addressed
archive file, and restores it before any line that names one of its tokens is processed.

Component: union-find over hot knowledge. A fact joins its subject, relation, object and
the facts of its premises; a name (capability / observations / hypotheses / retired)
joins every relation and capability in its versions and hypotheses, and every entity in
its observations and retired examples. Components are closed under everything a reply
can read, so a line that names none of a component's tokens cannot read it.

Gate (declared before any run, deterministic; bytes are the cost proxy because load,
validation and save all scale with bytes):
    n_c = min(WINDOW, call - first_touch_c);  u_c = distinct calls in the last n_c that touched c
    q_c = (u_c + 1) / (n_c + 2)                 per-call touch probability (Laplace)
    keep  cost per call = b_c                   (bytes carried by every call)
    archive cost per call = q_c * (b_c + R0)    (restore when touched; R0 = per-file overhead)
    archive iff q_c * (b_c + R0) < b_c, n_c >= MIN_AGE, and c untouched in the last GUARD calls.
"""

from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path

WINDOW, MIN_AGE, GUARD, R0, RECENT = 64, 8, 1, 4096, 4
ARCHIVE_SCHEMA = "packetlm.archive/1"
NAMED = ("capabilities", "observations", "hypotheses", "retired")


class ArchiveError(Exception):
    pass


def empty() -> dict:
    return {"call": 0, "touch": {}, "archived": {}}


def log_event(folder: Path, ev: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / "events.jsonl", "a") as fh:  # append-only audit trail
        fh.write(json.dumps(ev) + "\n")


_REF = re.compile(r'(?<![^"+\s])(rel|cap|op):([^"+\s]+)')


def refs(obj):
    """Every relation / capability / operator token referenced anywhere inside obj
    (a regular-expression pass over its JSON; same result as `refs_walk`)."""
    for kind, body in _REF.findall(json.dumps(obj)):
        if kind == "rel":
            yield body
        elif kind == "cap":
            yield body.split("@")[0]
        else:
            yield from (t for t in body.split(":")[1:] if t)


def refs_walk(obj):
    """Reference definition of `refs` (recursive walk), used by the checks."""
    if isinstance(obj, str):
        for part in obj.replace("+", " ").split():
            if part.startswith("rel:"):
                yield part[4:]
            elif part.startswith("cap:"):
                yield part[4:].split("@")[0]
            elif part.startswith("op:"):
                yield from (t for t in part.split(":")[2:] if t)
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from refs_walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from refs_walk(v)


def components(state) -> tuple[dict, dict]:
    """Return (root -> {'facts': [i...], 'names': set, 'tokens': set}, token -> root)."""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for f in state["facts"]:
        union("t:" + f["s"], "t:" + f["r"])
        union("t:" + f["s"], "t:" + f["o"])
        for sp in f["supports"]:
            for p in sp.get("premises", []):
                for tok in p.split():
                    union("t:" + f["s"], "t:" + tok)
        if any(sp.get("program") for sp in f["supports"]):
            for tok in refs(f["supports"]):
                union("t:" + f["s"], "t:" + tok)
    for key in NAMED:
        for name, val in state[key].items():
            n = "t:" + name
            find(n)
            for tok in refs(val):
                union(n, "t:" + tok)
            if key == "capabilities":
                if val.get("express"):
                    union(n, "t:" + val["express"])
            elif key == "hypotheses":
                for subj in val.get("unanswered", []):
                    union(n, "t:" + subj)
            elif key == "observations":
                for s, o in val:
                    union(n, "t:" + s)
                    union(n, "t:" + o)
            elif key == "retired":
                for x in val:
                    union(n, "t:" + x["s"])
                    union(n, "t:" + x["o"])
    comps = {}
    for f in state["facts"]:
        comps.setdefault(find("t:" + f["s"]), {"facts": set(), "names": set(), "tokens": set()})["facts"].add(f["id"])
    for key in NAMED:
        for name in state[key]:
            comps.setdefault(find("t:" + name), {"facts": set(), "names": set(), "tokens": set()})["names"].add(name)
    tok_root = {}
    for x in list(parent):
        r = find(x)
        if r in comps:
            comps[r]["tokens"].add(x[2:])
            tok_root[x[2:]] = r
    return comps, tok_root


def line_tokens(line: str, state) -> set:
    """Every token a line can make the engine read: its words, what the lexicon maps them
    to, and the meaning of any construction whose surface word appears in it."""
    words = set(line.replace(":", " ").replace(";", " ").replace("->", " ").replace("=", " ").lower().split())
    out = set(words)
    for w in words:
        if w in state["lexicon"]:
            out.add(state["lexicon"][w])
    for c in state["library"]:
        if c.get("word") in words or set(c.get("template") or []) & words:
            out.add(c.get("meaning"))
    return {t for t in out if isinstance(t, str)}


def touch(ret, tokens) -> None:
    call = ret["call"]
    for t in tokens:
        rec = ret["touch"].setdefault(t, [call])
        if rec[-1] != call or len(rec) == 1:
            rec.append(call)
        del rec[1:-RECENT]


def _comp_doc(state, comp) -> dict:
    return {"facts": [f for f in state["facts"] if f["id"] in comp["facts"]],
            **{key: {n: state[key][n] for n in sorted(comp["names"]) if n in state[key]} for key in NAMED}}


def decide(state, ret) -> list:
    """Components the gate archives now, with the numbers behind each decision."""
    comps, _ = components(state)
    call, out = ret["call"], []
    for root, comp in comps.items():
        recs = [ret["touch"][t] for t in comp["tokens"] if t in ret["touch"]]
        if not recs:
            continue  # never touched by a line (cannot date it): keep
        first = min(r[0] for r in recs)
        n = min(WINDOW, call - first)
        recent = {c for r in recs for c in r[1:] if c > call - n}
        if n < MIN_AGE or any(c > call - GUARD for r in recs for c in r[1:]):
            continue
        b = len(json.dumps(_comp_doc(state, comp)))
        q = (len(recent) + 1) / (n + 2)
        if q * (b + R0) < b:
            out.append((comp, {"bytes": b, "q": round(q, 4), "n": n, "u": len(recent)}))
    return out


def archive(state, ret, folder: Path, comp, why) -> str:
    doc = _comp_doc(state, comp)  # knowledge only: use records stay hot, so unchanged knowledge
    body = json.dumps({"schema": ARCHIVE_SCHEMA, "component": doc}, sort_keys=True).encode()
    sha = hashlib.sha256(body).hexdigest()
    folder.mkdir(parents=True, exist_ok=True)
    f = folder / f"{sha}.json"
    if not f.exists():  # re-archives to the same file; content-addressed, immutable, never deleted
        tmp = f.with_suffix(".tmp")
        tmp.write_bytes(body)
        tmp.replace(f)
    state["facts"] = [x for x in state["facts"] if x["id"] not in comp["facts"]]
    for key in NAMED:
        for n in comp["names"]:
            state[key].pop(n, None)
    ret["archived"][sha] = {"tokens": sorted(comp["tokens"]), "call": ret["call"], **why}
    log_event(folder, {"call": ret["call"], "archived": sha, "tokens": sorted(comp["tokens"]), **why})
    return sha


def restore(state, ret, folder: Path, sha) -> None:
    f = folder / f"{sha}.json"
    try:
        body = f.read_bytes()
    except OSError as exc:
        raise ArchiveError(f"archived component {sha[:12]} missing: {exc}")
    if hashlib.sha256(body).hexdigest() != sha:
        raise ArchiveError(f"archived component {sha[:12]} does not match its address")
    doc = json.loads(body)
    if doc.get("schema") != ARCHIVE_SCHEMA:
        raise ArchiveError(f"archived component {sha[:12]} has schema {doc.get('schema')}")
    comp = doc["component"]
    have = {x["id"] for x in state["facts"]}
    if any(x["id"] in have for x in comp["facts"]) or any(n in state[k] for k in NAMED for n in comp[k]):
        raise ArchiveError(f"archived component {sha[:12]} collides with hot knowledge")
    state["facts"].extend(comp["facts"])
    for key in NAMED:
        state[key].update(comp[key])
    del ret["archived"][sha]
    log_event(folder, {"call": ret["call"], "restored": sha})


def wanted(ret, tokens) -> list:
    return sorted(sha for sha, e in ret["archived"].items() if tokens & set(e["tokens"]))
