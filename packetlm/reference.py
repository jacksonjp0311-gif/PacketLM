"""Independent symbolic reference.

Plain dict-of-sets relational execution and hypothesis judgement.
It shares no code with engine.py, field.py or geom.py, so it can
check them and serve as the symbolic control. Not a mind.
"""

from __future__ import annotations
from itertools import product


def index(triples):
    idx = {}
    for s, r, o in triples:
        idx.setdefault(r, {}).setdefault(s, set()).add(o)
    return idx


LIMIT = 8


def first_with(idx, r, q, t, x):
    """Breadth-first along r from x: the nodes of the first level (1..LIMIT) holding q t."""
    visited, level = {x}, [x]
    for _ in range(LIMIT):
        level = sorted({o for y in level for o in idx.get(r, {}).get(y, ())} - visited)
        if not level:
            return set()
        found = {o for o in level if t in idx.get(q, {}).get(o, ())}
        if found:
            return found
        visited.update(level)
    return set()


def run(idx, rels, subject):
    cur = {subject}
    for r in rels:
        nxt = set()
        if r.startswith("until:"):
            _, rr, q, t = r.split(":")
            for x in cur:
                nxt |= first_with(idx, rr, q, t, x)
        else:
            for x in cur:
                nxt |= idx.get(r, {}).get(x, set())
        cur = nxt
        if not cur:
            break
    return cur


def mark(idx, rels, subject, expected):
    out = run(idx, rels, subject)
    if len(out) != 1:
        return "undetermined"
    return "supported" if expected in out else "contradicted"


def status(idx, rels, observations):
    marks = [mark(idx, rels, s, o) for s, o in observations]
    if "contradicted" in marks:
        return "contradicted"
    if marks and all(m == "supported" for m in marks):
        return "supported"
    return "undetermined"


def learn(triples, observations, max_len=2):
    """Reference learner: enumerate relation sequences, keep the unique supported one."""
    idx = index(triples)
    rels = sorted(idx)
    supported = []
    evaluated = 0
    for n in range(1, max_len + 1):
        for seq in product(rels, repeat=n):
            evaluated += 1
            if status(idx, seq, observations) == "supported":
                supported.append(list(seq))
    return (supported[0] if len(supported) == 1 else None), evaluated
