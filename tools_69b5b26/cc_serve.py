"""Verifier counterfactual (unregistered): 'equal certificate' C. After C's own rule says `qualified`, the same
evidence must also pass B's rule in the base language (no library, same margin); the base search runs in-process
and is charged. If the base rule finds several tuples -> ambiguous (live = base groups, so investigate asks what B
would ask); if it finds blockers or a different tuple -> provisional. B and P (library off) are unchanged."""
import os, sys
sys.path.insert(0, os.getcwd())
from packetlm.hdc import engine as E, serve
NONE, SEVERAL = E.NONE, E.SEVERAL
orig = E.HEngine.acquire


def base_search(self, name):
    obs = self.obs.get(name, [])
    X, nx = self.domain(name)
    want = {X.index(s): v for s, v in obs}
    vi = [i for i, v in want.items() if v not in (NONE, SEVERAL)]
    i0 = vi[0]

    def match(t):
        for i, v in want.items():
            S = t[i]
            if v == NONE:
                if S: return False
            elif v == SEVERAL:
                if len(S) < 2: return False
            elif S != frozenset((v,)):
                return False
        return True
    start = tuple(frozenset((e,)) for e in X)
    seen, frontier, memo = {start}, [(start, [])], {}
    found, groups, blockers = None, [], []
    lib = self.library
    self.library = False
    try:
        for n in range(1, self.deepen + 1):
            new = []
            for t, seq in frontier:
                for p in self.offered(t[i0], name):
                    self.stats["evaluations"] += 1
                    t2 = tuple(self.apply(S, p, memo) for S in t)
                    if any(not t2[i] for i in vi) or t2 in seen:
                        continue
                    seen.add(t2); new.append((t2, seq + [p]))
            sup = [x for x in new if match(x[0])]
            frontier = new
            if found is None:
                if sup:
                    found, groups = n, sup
                    if len(sup) > 1: break
            else:
                blockers += sup
                if n >= found + self.margin: break
            if not frontier: break
    finally:
        self.library = lib
    return X, groups, blockers


def acq(self, name):
    r = orig(self, name)
    if not self.library or r["result"] != "qualified":
        return r
    X, live = self.live[name]
    real = live[0][0]
    _, groups, blockers = base_search(self, name)
    if len(groups) == 1 and groups[0][0] == real and not blockers:
        return r
    ver = self.version(name)
    ver["status"] = "provisional"
    self._reindex(name)
    if len(groups) > 1:
        self.live[name] = (X, groups)
        self.counters["cc_ambiguous"] = self.counters.get("cc_ambiguous", 0) + 1
        return {"result": "ambiguous"}
    self.live[name] = (X, live + [g for g in groups + blockers if g[0] != real])
    self.counters["cc_provisional"] = self.counters.get("cc_provisional", 0) + 1
    return {"result": "provisional", "seq": r["seq"]}


E.HEngine.acquire = acq
serve.HEngine = E.HEngine
if __name__ == "__main__":
    raise SystemExit(serve.main())
