"""G48: control structures acquired as programs in a small designed grammar (docs/G48.md).

DESIGNED (stated precisely; nothing else about control is supplied):
  token   := rel:R          step along relation R (set image)
           | cap:N@v        step through an executable capability
           | is:Q:T         guard: keep the nodes x with a fact x Q T
           | not:Q:T        guard: keep the nodes x without a fact x Q T
           | self           tail recursion: apply the whole program to every current node
  clause  := 1..3 tokens; `self` only as the last token of the last clause
  program := 1 clause, or 2 clauses whose first contains a guard ("|" separates clauses)
  meaning on one start node x (recursion depth <= MAX_DEPTH): try the clauses in order on {x};
          the first clause whose result is non-empty gives the answer set (ordered choice).
  size    := number of tokens (<= MAX_SIZE)
  guard proposals: (Q, T) shared by every observed answer, plus (Q, T) of an observed subject
          where T is class-like (at least 2 entities have Q T); at most MAX_GUARDS pairs.
  choice: smallest size with a supported program (all observations supported). Several
          supported programs with different predictions on the domain -> ambiguous.
  status: open-world rule of the engine. Every program of size <= the candidate's size (the
          horizon, as in the engine's deepening) not contradicted
          by the observations is an alternative. It blocks if it conflicts with the candidate
          (both defined and different somewhere in the domain) or has support >= 1 and differs
          anywhere. qualified only if the enumeration COMPLETES within SCAN_BUDGET programs with
          no blocker; otherwise provisional.
ACQUIRED: which tokens, guards, clause structure, recursion and therefore traversal depth.
The old hand-designed `until:R:Q:T` operator is not part of this grammar; until-like
behaviour is the acquired program `rel:R>is:Q:T|rel:R>self`.
"""

from __future__ import annotations
from itertools import product

MAX_DEPTH, MAX_SIZE, MAX_CLAUSE, MAX_GUARDS, BLOCK_KEEP = 8, 5, 3, 8, 16
SCAN_BUDGET = 200_000  # programs examined in the open-world scan before it is declared incomplete


def parse(text: str) -> tuple:
    body = text[5:] if text.startswith("prog:") else text
    return tuple(tuple(c.split(">")) for c in body.split("|"))


def fmt(prog) -> str:
    return "prog:" + "|".join(">".join(c) for c in prog)


def size(prog) -> int:
    return sum(len(c) for c in prog)


class Ctx:
    """Execution context: ref = {relation: {subject: set(objects)}}; cap(token, x) -> set."""

    def __init__(self, ref, cap=None):
        self.ref, self.cap, self.steps = ref, cap, 0

    def has(self, x, q, t):
        return t in self.ref.get(q, {}).get(x, ())


def run(ctx, prog, x, depth=0, memo=None) -> frozenset:
    memo = {} if memo is None else memo
    key = (x, depth)
    if key in memo:
        return memo[key]
    out = frozenset()
    for clause in prog:
        cur = {x}
        for tok in clause:
            ctx.steps += 1
            if tok == "self":
                nxt = set()
                if depth + 1 <= MAX_DEPTH:
                    for y in cur:
                        nxt |= run(ctx, prog, y, depth + 1, memo)
                cur = nxt
            elif tok.startswith("rel:"):
                m = ctx.ref.get(tok[4:], {})
                cur = set().union(*(m.get(y, ()) for y in cur)) if cur else set()
            elif tok.startswith("is:"):
                _, q, t = tok.split(":")
                cur = {y for y in cur if ctx.has(y, q, t)}
            elif tok.startswith("not:"):
                _, q, t = tok.split(":")
                cur = {y for y in cur if not ctx.has(y, q, t)}
            elif tok.startswith("cap:"):
                cur = set().union(*(ctx.cap(tok, y) for y in cur)) if cur else set()
            else:
                raise ValueError(f"bad program token {tok}")
            if not cur:
                break
        if cur:
            out = frozenset(cur)
            break
    memo[key] = out
    return out


def run_naive(ref, prog, x, cap=None, depth=0):
    """Independent second interpreter (no memo, explicit loops), used by the checks."""
    for clause in prog:
        front = [x]
        for tok in clause:
            new = []
            for y in front:
                if tok == "self":
                    if depth < MAX_DEPTH:
                        new += list(run_naive(ref, prog, y, cap, depth + 1))
                elif tok[:4] == "rel:":
                    new += list(ref.get(tok[4:], {}).get(y, ()))
                elif tok[:3] == "is:":
                    q, t = tok.split(":")[1:]
                    if t in ref.get(q, {}).get(y, ()):
                        new.append(y)
                elif tok[:4] == "not:":
                    q, t = tok.split(":")[1:]
                    if t not in ref.get(q, {}).get(y, ()):
                        new.append(y)
                else:
                    new += list(cap(tok, y))
            front = sorted(set(new))
        if front:
            return set(front)
    return set()


def one(s):
    return next(iter(s)) if len(s) == 1 else None


def judge1(pred, v):
    if pred is None:
        return "undetermined"
    return "supported" if pred == v else "contradicted"


def proposals(ref, obs):
    """Guard proposals (designed rule, see module doc)."""
    props = {}
    for q, m in ref.items():
        for x, ts in m.items():
            for t in ts:
                props.setdefault(x, set()).add((q, t))
    count = {}
    for x, ps in props.items():
        for p in ps:
            count[p] = count.get(p, 0) + 1
    shared = None
    for _, v in obs:
        shared = set(props.get(v, ())) if shared is None else shared & props.get(v, set())
    shared = sorted(shared or ())
    subj = sorted({p for s, _ in obs for p in props.get(s, ()) if count[p] >= 2} - set(shared))
    return (shared + subj)[:MAX_GUARDS]


def clauses(steps, guards, n, with_self=False):
    toks = steps + guards
    out = []
    for k in range(1, n + 1):
        body = k - 1 if with_self else k
        if body < (1 if with_self else 1):
            continue
        for c in product(toks, repeat=body):
            if any(c[i] == c[i + 1] and c[i][:3] in ("is:", "not") for i in range(len(c) - 1)):
                continue
            out.append(c + (("self",) if with_self else ()))
    return out


class Inducer:
    def __init__(self, ctx, obs, domain, steps, guards):
        self.ctx, self.obs, self.domain = ctx, obs, sorted(domain)
        self.steps, self.guards = steps, guards
        self.examined = 0

    def pred(self, prog, x):
        return one(run(self.ctx, prog, x))

    def marks(self, prog):
        return [judge1(self.pred(prog, s), v) for s, v in self.obs]

    def programs(self, k):
        """All programs of size k in canonical order (designed grammar)."""
        g = [f"is:{q}:{t}" for q, t in self.guards] + [f"not:{q}:{t}" for q, t in self.guards]
        st = [f"rel:{r}" for r in self.steps[0]] + list(self.steps[1])
        if k <= MAX_CLAUSE:
            for c in product(st + g, repeat=k):
                if any(x.startswith(("rel:", "cap:")) for x in c):
                    yield (c,)
        for a in range(1, min(MAX_CLAUSE, k - 1) + 1):
            b = k - a
            if b < 1 or b > MAX_CLAUSE:
                continue
            for c1 in product(st + g, repeat=a):
                if not any(x.startswith(("is:", "not:")) for x in c1):
                    continue
                for c2 in product(st + g, repeat=b):
                    if not any(x.startswith(("rel:", "cap:")) for x in c2):
                        continue
                    yield (c1, c2)
                if b >= 2:
                    for c2 in product(st + g, repeat=b - 1):
                        yield (c1, c2 + ("self",))

    def search(self):
        """Smallest size with a supported program; all supported programs of that size."""
        for k in range(1, MAX_SIZE + 1):
            sup = []
            for p in self.programs(k):
                self.examined += 1
                ok = True
                for s, v in self.obs:
                    if judge1(self.pred(p, s), v) != "supported":
                        ok = False
                        break
                if ok:
                    sup.append(p)
            if sup:
                return k, sup
        return None, []

    def predictions(self, prog):
        return {e: run(self.ctx, prog, e) for e in self.domain}

    def scan(self, cand, cand_pred, horizon=MAX_SIZE):
        """Open-world blockers up to `horizon` tokens (bounded; incomplete if the budget runs out)."""
        blockers, examined = [], 0
        for k in range(1, horizon + 1):
            for p in self.programs(k):
                if p == cand:
                    continue
                examined += 1
                if examined > SCAN_BUDGET:
                    return blockers, False, examined
                m = self.marks(p)
                if "contradicted" in m:
                    continue
                support = m.count("supported")
                differs = conflict = False
                for e in self.domain:
                    a, b = one(run(self.ctx, p, e)), one(cand_pred[e])
                    if a != b:
                        differs = True
                        if a is not None and b is not None:
                            conflict = True
                            break
                if conflict or (support >= 1 and differs):
                    blockers.append(fmt(p))
                    if len(blockers) >= BLOCK_KEEP:
                        return blockers, False, examined
        return blockers, True, examined


def trace(prog, x, find, cap_paths, depth=0):
    """Fact paths of a program run (provenance). Same ordered choice as `run`: the first clause
    with any path gives the paths. find(s, r, o=None) -> facts; cap_paths(tok, x) -> [(end, ids)].
    A `not:` guard contributes no premise (it rests on an absence)."""
    for clause in prog:
        paths = [(x, [])]
        for tok in clause:
            nxt = []
            for cur, prem in paths:
                if tok == "self":
                    if depth + 1 <= MAX_DEPTH:
                        nxt += [(e, prem + p) for e, p in trace(prog, cur, find, cap_paths, depth + 1)]
                elif tok.startswith("rel:"):
                    nxt += [(f["o"], prem + [f["id"]]) for f in find(cur, tok[4:])]
                elif tok.startswith("is:"):
                    _, q, t = tok.split(":")
                    fs = find(cur, q, t)
                    if fs:
                        nxt.append((cur, prem + [fs[0]["id"]]))
                elif tok.startswith("not:"):
                    _, q, t = tok.split(":")
                    if not find(cur, q, t):
                        nxt.append((cur, prem))
                else:
                    nxt += [(e, prem + p) for e, p in cap_paths(tok, cur)]
            paths = nxt[:256]
            if not paths:
                break
        if paths:
            return paths
    return []


def deps(text):
    """Capability tokens used inside a program string."""
    return [t for c in parse(text) for t in c if t.startswith("cap:")]
