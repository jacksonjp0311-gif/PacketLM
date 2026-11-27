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
  status: open-world rule of the engine. Every program of size <= MAX_SIZE (the full budget,
          as the engine's deepening horizon) not contradicted
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


def judge_set(out, v):
    """Full-set judgment, as engine.judge_set (PX: `!none` / `!several` statements)."""
    if v == "!none":
        return "supported" if not out else "contradicted"
    if v == "!several":
        return "supported" if len(out) >= 2 else ("contradicted" if len(out) == 1 else "undetermined")
    return judge1(one(out), v)


def judge_closed(out, v):
    """Closed-world judgment at a `complete` subject (as engine.judge_closed)."""
    if v == "!none":
        return "supported" if not out else "contradicted"
    if v == "!several":
        return "supported" if len(out) >= 2 else "contradicted"
    return "supported" if out == {v} else "contradicted"


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
        if v.startswith("!"):
            continue  # PX statements carry no answer entity
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
    def __init__(self, ctx, obs, domain, steps, guards, closed=frozenset()):
        self.ctx, self.obs, self.domain = ctx, obs, sorted(domain)
        self.closed = frozenset(closed)  # G49: subjects stated `complete` (closed-world judgment)
        self.steps, self.guards = steps, guards
        self.examined = 0

    def pred(self, prog, x):
        return one(run(self.ctx, prog, x))

    def judge(self, s, out, v):
        return judge_closed(out, v) if s in self.closed else judge_set(out, v)

    def marks(self, prog):
        return [self.judge(s, run(self.ctx, prog, s), v) for s, v in self.obs]

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
                    if self.judge(s, run(self.ctx, p, s), v) != "supported":
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


EXACT_BUDGET = 4_000_000  # clause-class combinations evaluated by scan_exact before it is declared incomplete


def _bits(b):
    while b:
        low = b & -b
        yield low.bit_length() - 1
        b ^= low


class Exact:
    """Exact pruned open-world scan (docs/G49.md). Same decision as `Inducer.scan` with no budget:
    the set of blocking *behaviours* and, for each, its canonical-first program.

    Why it is exact (each step is an equality, nothing is approximated):
    1. Every token denotes a map node -> set of nodes that distributes over union (rel/cap images,
       guards are filters), so a token sequence denotes a relation, and two sequences with the same
       relation on the universe U (closure of the domain and observed subjects under all step
       tokens) have the same relation after any extension. Prefixes are therefore merged by
       relation (plus the grammar flags has-step / has-guard), level by level.
    2. A program's outputs depend only on the relations of its clauses: one clause -> its relation;
       c1|c2 -> c1(x) if non-empty else c2(x); c1|b>self -> the depth-bounded recursion of `run`
       computed from c1 and b on U. Its scan verdict depends only on its outputs on the domain and
       the observed subjects (marks, support, differs, conflict), so it is decided once per
       distinct behaviour. Non-recursive clauses only matter on those start nodes (projection).
    3. The canonical-first program of a class is reachable from canonical-first prefixes (a later
       prefix with the same relation can be replaced by the earlier one, giving an earlier program),
       so the representative kept is the first program `Inducer.programs` would list.
    Proven against brute force on random small worlds: packetlm/scan_exact_proof.py (`python3 -m packetlm.scan_exact_proof`), g44 checks."""

    def __init__(self, ind):
        self.ind, ctx = ind, ind.ctx
        g = [f"is:{q}:{t}" for q, t in ind.guards] + [f"not:{q}:{t}" for q, t in ind.guards]
        st = [f"rel:{r}" for r in ind.steps[0]] + list(ind.steps[1])
        self.toks, self.nst = st + g, len(st)
        start = sorted(set(ind.domain) | {s for s, _ in ind.obs})
        U, idx, todo = list(start), {e: i for i, e in enumerate(start)}, list(start)
        img = {t: {} for t in st}
        while todo:
            y = todo.pop()
            for t in st:
                out = run(ctx, ((t,),), y)
                img[t][y] = out
                for z in out:
                    if z not in idx:
                        idx[z] = len(U)
                        U.append(z)
                        todo.append(z)
        self.U, self.idx = U, idx
        n = len(U)
        self.tokimg = []
        for t in self.toks:
            if t.startswith(("rel:", "cap:")):
                row = []
                for y in U:
                    b = 0
                    for z in img[t][y]:
                        b |= 1 << idx[z]
                    row.append(b)
            else:
                _, q, tt = t.split(":")
                keep = t.startswith("is:")
                row = [(1 << i) if ctx.has(y, q, tt) == keep else 0 for i, y in enumerate(U)]
            self.tokimg.append(row)
        self.S = [idx[e] for e in start]            # start nodes (domain + observed subjects)
        self.dom = [idx[e] for e in ind.domain]
        self.obs = [(idx[s], v) for s, v in ind.obs]
        self._img = {}
        self.combos = 0

    def image(self, ti, b):
        key = (ti, b)
        r = self._img.get(key)
        if r is None:
            row, r = self.tokimg[ti], 0
            for j in _bits(b):
                r |= row[j]
            self._img[key] = r
        return r

    def levels(self, full):
        """classes[L] = {(relation, has_step, has_guard): [rep_index_tuple, count]} for L = 1..MAX_CLAUSE.
        full: relation over all of U (needed under recursion); else over the start nodes only."""
        rows = range(len(self.U)) if full else self.S
        base = tuple(1 << i for i in rows) if full else tuple(1 << i for i in rows)
        cur = {(base, False, False): [(), 1]}
        out = []
        for _ in range(MAX_CLAUSE):
            nxt = {}
            for (rel, hs, hg), (rep, cnt) in cur.items():
                for ti in range(len(self.toks)):
                    r2 = tuple(self.image(ti, b) for b in rel)
                    key = (r2, hs or ti < self.nst, hg or ti >= self.nst)
                    e = nxt.get(key)
                    if e is None:
                        nxt[key] = [rep + (ti,), cnt]
                    else:
                        e[1] += cnt
                        if rep + (ti,) < e[0]:
                            e[0] = rep + (ti,)
            out.append(nxt)
            cur = nxt
        return out

    def recurse(self, r1, rb):
        """Outputs of c1|b>self on every node of U (same depth cap as `run`)."""
        n = len(self.U)
        prev = list(r1)  # depth MAX_DEPTH: self contributes nothing
        for _ in range(MAX_DEPTH):
            cur = [r1[x] if r1[x] else self._union(rb[x], prev) for x in range(n)]
            if cur == prev:
                break
            prev = cur
        return prev

    @staticmethod
    def _union(b, vec):
        r = 0
        for j in _bits(b):
            r |= vec[j]
        return r

    def run(self, cand, cand_pred, keep=BLOCK_KEEP):
        idx = self.idx
        pos = {u: k for k, u in enumerate(self.S)}
        want = {}
        for e, out in cand_pred.items():
            b = 0
            for z in out:
                b |= 1 << idx[z]
            want[idx[e]] = b
        obs_at = [(pos[i], v, self.U[i] in self.ind.closed) for i, v in self.obs]
        dom_at = [pos[i] for i in self.dom]
        want_at = [want[i] for i in self.dom]
        U = self.U
        verdict = {}
        best = {}  # behaviour -> (order key, program) of its canonical-first program
        total = [0]

        def one_b(b):
            return U[b.bit_length() - 1] if b and not b & (b - 1) else None

        def decide(beh):
            v = verdict.get(beh)
            if v is None:
                support, bad = 0, False
                for k, val, closed in obs_at:
                    out = beh[k]
                    if closed:
                        if val == "!none":
                            j = "supported" if not out else "contradicted"
                        elif val == "!several":
                            j = "supported" if out and out & (out - 1) else "contradicted"
                        else:
                            j = "supported" if val in self.idx and out == 1 << self.idx[val] else "contradicted"
                    elif val == "!none":
                        j = "supported" if not out else "contradicted"
                    elif val == "!several":
                        j = "supported" if out and out & (out - 1) else ("contradicted" if out else "undetermined")
                    else:
                        o = one_b(out)
                        j = "undetermined" if o is None else ("supported" if o == val else "contradicted")
                    if j == "contradicted":
                        bad = True
                        break
                    support += j == "supported"
                v = False
                if not bad:
                    differs = conflict = False
                    for k, w in zip(dom_at, want_at):
                        a, b = one_b(beh[k]), one_b(w)
                        if a != b:
                            differs = True
                            if a is not None and b is not None:
                                conflict = True
                                break
                    v = conflict or (support >= 1 and differs)
                verdict[beh] = v
            return v

        def note(beh, key, cnt):
            total[0] += cnt
            self.combos += 1
            if self.combos > EXACT_BUDGET:
                raise _Budget
            if decide(beh):
                b = best.get(beh)
                if b is None or key < b:
                    best[beh] = key

        try:
            lv = self.levels(full=False)
            # single clause: needs a step token
            for L in range(1, MAX_CLAUSE + 1):
                for (rel, hs, hg), (rep, cnt) in lv[L - 1].items():
                    if hs:
                        note(rel, (L, 0, rep), cnt)
            # c1|c2: c1 has a guard, c2 has a step (behaviours projected on the start nodes)
            proj = lambda L, f: _group(lv[L - 1], f)  # noqa: E731
            for a in range(1, MAX_CLAUSE + 1):
                g1 = proj(a, lambda hs, hg: hg)
                for b in range(1, MAX_CLAUSE + 1):
                    if a + b > MAX_SIZE:
                        continue
                    g2 = proj(b, lambda hs, hg: hs)
                    for r1, (rep1, c1) in g1.items():
                        for r2, (rep2, c2) in g2.items():
                            beh = tuple(x if x else y for x, y in zip(r1, r2))
                            note(beh, (a + b, 1, a, rep1, 0, rep2), c1 * c2)
            # c1|b>self (b: 1..2 tokens, any; size a + len(b) + 1)
            lvf = self.levels(full=True)
            for a in range(1, MAX_CLAUSE + 1):
                g1 = _group(lvf[a - 1], lambda hs, hg: hg)
                for bl in range(1, MAX_CLAUSE):
                    if a + bl + 1 > MAX_SIZE:
                        continue
                    gb = _group(lvf[bl - 1], lambda hs, hg: True)
                    for r1, (rep1, c1) in g1.items():
                        for rb, (repb, cb) in gb.items():
                            outs = self.recurse(r1, rb)
                            beh = tuple(outs[i] for i in self.S)
                            note(beh, (a + bl + 1, 1, a, rep1, 1, repb), c1 * cb)
        except _Budget:
            return {"blockers": [], "complete": False, "programs": total[0], "combos": self.combos,
                    "behaviours": len(verdict), "blocking_behaviours": len(best), "universe": len(U)}
        order = sorted(best.values())
        names = [fmt(self.decode(k)) for k in order]
        if cand is not None:
            names = [p for p in names if p != fmt(cand)]
        return {"blockers": names[:keep], "complete": True, "programs": total[0], "combos": self.combos,
                "behaviours": len(verdict), "blocking_behaviours": len(best), "universe": len(U)}

    def decode(self, key):
        t = self.toks
        if key[1] == 0:
            return (tuple(t[i] for i in key[2]),)
        _, _, a, r1, s, r2 = key
        c2 = tuple(t[i] for i in r2) + (("self",) if s else ())
        return (tuple(t[i] for i in r1), c2)


class _Budget(Exception):
    pass


def _group(level, ok):
    """Merge the classes of one level that pass the flag filter by relation: [min rep, total count]."""
    g = {}
    for (rel, hs, hg), (rep, cnt) in level.items():
        if not ok(hs, hg):
            continue
        e = g.get(rel)
        if e is None:
            g[rel] = [rep, cnt]
        else:
            e[1] += cnt
            if rep < e[0]:
                e[0] = rep
    return {k: tuple(v) for k, v in g.items()}


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
