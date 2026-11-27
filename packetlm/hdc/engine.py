"""G60H engine: concepts, relations and learned capabilities as fixed-width sparse block hypervectors
(docs/G60H.md §2). Same controlled language as packetlm/engine.py for the lines the G46/G50/PX
teacher sends; a different representation and search.

Representation (codes.py: K blocks of L, every operation O(K)):
- fact memory: heteroassociative, key = bind(code(s), rho(code(r))) -> value codes (a set for a
  multi-valued relation). A step (s, r) costs one bind and one lookup, whatever is stored.
- entity signature: S_e = OR of onehot(code(r)) over e's relations (bundle); decoded by cleanup.
- capability: H_c = OR_k onehot(rho^k(code(step_k))) (a composed hypervector of its primitive
  sequence); applied by decoding position by position (cleanup over the primitive codebook) and
  executing the steps. The decoded sequence is checked against the exact journal copy; a mismatch is
  a decode error (counted, the exact copy is used, the check is charged).
- capability index: F_r = OR of onehot(code(c)) over qualified capabilities whose first base relation
  is r; the primitives offered at an entity are decode(S_e) + decode(F_r) for r in decode(S_e).
Search (identical for every arm; `--no-library` only removes capabilities from the offered set):
  iterative deepening over primitive sequences, as a dynamic program over tuples of entity sets on
  X = the observed subjects + Omega (up to OMEGA subjects of s1's relations, in the order told); equal
  tuples are equal functions on X and are expanded once; a tuple empty at a value-observed subject is
  pruned. Supported = matches every observation (value, !none, !several). At the first depth n with
  support: several distinct tuples -> `ambiguous`; one -> candidate, searched one level further (n+1):
  a new supported tuple there blocks (-> `provisional`), else `qualified`. Answers are qualified only on
  X (the decided domain); elsewhere [provisional].
"""
from __future__ import annotations
from . import codes as C

OMEGA = 16
NONE, SEVERAL = "!none", "!several"


class HEngine:
    def __init__(self, library=True, deepen=5):
        self.library, self.deepen = library, deepen
        self.ent = C.Codebook()      # entities
        self.prim = C.Codebook()     # relations and capabilities (the primitive codebook)
        self.rel = C.Codebook()      # relations only (signature cleanup)
        self.capcb = C.Codebook()    # capabilities only (index cleanup)
        self.facts = {}              # bound key -> list of value codes (fact memory)
        self.sig = {}                # entity -> signature bundle
        self.rsub = {}               # relation -> subjects in the order told (Omega source)
        self.rsubset = {}
        self.order = []              # exact journal copy of the facts (s, r, o) for snapshot/validation
        self.obs, self.unans = {}, {}
        self.caps = {}               # name -> {"current": v, "versions": [{"v","seq","status","domain"}]}
        self.hvec, self.capidx, self.capidx_list = {}, {}, {}
        self.hyp, self.live = {}, {}
        self.decoded = {}            # (cap, v) -> decoded steps (derived; process memo)
        self.counters = {"decode_errors": 0, "decodes": 0, "sig_decodes": 0, "collisions": 0}
        self.new_stats()

    def new_stats(self):
        self.stats = {"evaluations": 0, "executions": 0, "row_ops": 0, "asks": 0, "cleanup_checks": 0}
        self.touched = []

    # ---------- memory ----------
    def _key(self, s, r):
        return C.bind(self.ent.add(s), C.rho(self.prim.add(r)))

    def tell(self, s, r, o):
        self.rel.add(r)
        self.prim.add(r)
        k = self._key(s, r)
        oc = self.ent.add(o)
        vals = self.facts.setdefault(k, [])
        if oc not in vals:
            vals.append(oc)
            self.order.append((s, r, o))
        self.sig[s] = self.sig.get(s, 0) | self.rel.hot[r]
        if s not in self.rsubset.setdefault(r, set()):
            self.rsubset[r].add(s)
            self.rsub.setdefault(r, []).append(s)
        self.touched.append((k, s, r))

    def correct(self, s, r, o):
        k = self._key(s, r)
        old = self.facts.get(k, [])
        removed = [self.ent.name[c] for c in old if self.ent.name[c] != o]
        self.order = [t for t in self.order if not (t[0] == s and t[1] == r)]
        self.facts[k] = []
        self.tell(s, r, o)
        return removed

    def step(self, e, r):
        """One relation step: bind, look up, clean up the value codes (O(K))."""
        self.stats["row_ops"] += 1
        c = self.ent.code.get(e)
        pc = self.prim.code.get(r)
        if c is None or pc is None:
            return ()
        vals = self.facts.get(C.bind(c, C.rho(pc)))
        return tuple(self.ent.name[v] for v in vals) if vals else ()

    def rels_of(self, e):
        S = self.sig.get(e)
        if not S:
            return []
        self.counters["sig_decodes"] += 1
        got = self.rel.decode(S, 0, self.stats)
        return got

    # ---------- capabilities as composed hypervectors ----------
    def _encode_cap(self, seq):
        H = 0
        for k, p in enumerate(seq):
            H |= C.onehot(C.rho(self.prim.add(p.split(":", 1)[1].split("@")[0]), k))
        return H

    def steps(self, name):
        ver = self.version(name)
        key = (name, ver["v"])
        got = self.decoded.get(key)
        if got is not None:
            return got
        H = self.hvec[key]
        dec = []
        for k in range(len(ver["seq"])):
            items = self.prim.decode(H, k, self.stats)
            dec.append(items[0] if len(items) == 1 else None)
        exact = [p.split(":", 1)[1].split("@")[0] for p in ver["seq"]]
        self.counters["decodes"] += 1
        if dec != exact:  # verification against the exact copy (charged); fall back to it
            self.counters["decode_errors"] += 1
            dec = exact
        self.decoded[key] = dec
        return dec

    def version(self, name):
        cap = self.caps.get(name)
        return cap["versions"][cap["current"] - 1] if cap and cap.get("current") else None

    def base(self, name):
        out = []
        for p in self.version(name)["seq"]:
            out += [p[4:]] if p.startswith("rel:") else self.base(p[4:].rsplit("@", 1)[0])
        return out

    def apply(self, ents, prim, memo):
        """Primitive (relation or capability name) applied to a set of entities."""
        key = (ents, prim)
        got = memo.get(key)
        if got is not None:
            return got
        if prim in self.rel.code:
            out = set()
            for e in ents:
                self.stats["executions"] += 1
                out.update(self.step(e, prim))
        else:
            cur = ents
            for p in self.steps(prim):
                cur = self.apply(cur, p, memo)
                if not cur:
                    break
            out = cur
        got = frozenset(out)
        memo[key] = got
        return got

    def offered(self, ents, exclude):
        rels = set()
        for e in ents:
            rels.update(self.rels_of(e))
        out = sorted(rels)
        if self.library:
            caps = set()
            for r in out:
                F = self.capidx.get(r)
                if F:
                    caps.update(c for c in self.capcb.decode(F, 0, self.stats) if c in self.capidx_list.get(r, ()))
            caps.discard(exclude)
            out += sorted(caps)
        return out

    def _reindex(self, name):
        """Keep the capability index equal to the qualified capabilities (bundles rebuilt from the
        exact per-relation lists when a capability enters or leaves; charged)."""
        for r, lst in self.capidx_list.items():
            if name in lst:
                lst.discard(name)
                self.capidx[r] = 0
                for c in lst:
                    self.capidx[r] |= self.capcb.hot[c]
        ver = self.version(name)
        if ver and ver["status"] == "qualified":
            r = self.base(name)[0]
            self.capcb.add(name)
            self.capidx_list.setdefault(r, set()).add(name)
            self.capidx[r] = self.capidx.get(r, 0) | self.capcb.hot[name]

    # ---------- acquisition ----------
    def domain(self, name):
        obs = self.obs.get(name, [])
        X = []
        for s, _ in obs:
            if s not in X:
                X.append(s)
        first = next(s for s, v in obs if v not in (NONE, SEVERAL))
        om = []
        for r in sorted(self.rels_of(first)):
            for e in self.rsub.get(r, ())[:OMEGA]:
                if len(om) >= OMEGA:
                    break
                if e not in X and e not in om:
                    om.append(e)
        return X + om, len(X)

    def acquire(self, name):
        obs = self.obs.get(name, [])
        if not any(v not in (NONE, SEVERAL) for _, v in obs):
            return {"result": "none"}
        X, nx = self.domain(name)
        want = {}
        for s, v in obs:
            want[X.index(s)] = v
        vi = [i for i, v in want.items() if v not in (NONE, SEVERAL)]
        i0 = vi[0]

        def match(t):
            for i, v in want.items():
                S = t[i]
                if v == NONE:
                    if S:
                        return False
                elif v == SEVERAL:
                    if len(S) < 2:
                        return False
                elif S != frozenset((v,)):
                    return False
            return True
        start = tuple(frozenset((e,)) for e in X)
        seen, frontier, memo = {start}, [(start, [])], {}
        found, groups, blockers, pruned = None, [], [], 0
        searched = self.deepen
        for n in range(1, self.deepen + 1):
            new = []
            for t, seq in frontier:
                for p in self.offered(t[i0], name):
                    self.stats["evaluations"] += 1
                    t2 = tuple(self.apply(S, p, memo) for S in t)
                    if any(not t2[i] for i in vi):
                        pruned += 1
                        continue
                    if t2 in seen:
                        continue
                    seen.add(t2)
                    new.append((t2, seq + [p]))
            sup = [x for x in new if match(x[0])]
            frontier = new
            if found is None:
                if sup:
                    found, groups, searched = n, sup, n
                    if len(sup) > 1:
                        break
            else:
                blockers = sup
                break
            if not frontier:
                break
        rec = {"searched_len": searched, "pruned": pruned, "evaluated": self.stats["evaluations"]}
        self.hyp[name] = rec
        if found is None:
            self.live[name] = (X, [])
            self._cap_provisional(name)
            return {"result": "none"}
        self.live[name] = (X, groups + blockers)
        if len(groups) > 1:
            self._cap_provisional(name)
            return {"result": "ambiguous"}
        t, seq = groups[0]
        status = "provisional" if blockers else "qualified"
        sq = [("cap:" + p + "@" + str(self.version(p)["v"])) if p in self.caps else "rel:" + p for p in seq]
        self._adopt(name, sq, status, X)
        return {"result": status, "seq": sq}

    def _cap_provisional(self, name):
        ver = self.version(name)
        if ver and ver["status"] == "qualified":
            ver["status"] = "provisional"
            self._reindex(name)

    def _adopt(self, name, seq, status, X):
        cap = self.caps.setdefault(name, {"current": 0, "versions": []})
        ver = self.version(name)
        if ver is None or ver["seq"] != seq:
            ver = {"v": len(cap["versions"]) + 1, "seq": seq, "status": status, "domain": list(X)}
            cap["versions"].append(ver)
            cap["current"] = ver["v"]
            self.prim.add(name)
            self.hvec[(name, ver["v"])] = self._encode_cap(seq)
        else:
            ver["status"], ver["domain"] = status, list(X)
        self._reindex(name)

    def investigate(self, name):
        if name not in self.live:
            return "nothing to investigate"
        X, live = self.live[name]
        if len(live) <= 1:
            return "settled"
        done = {s for s, _ in self.obs.get(name, [])} | set(self.unans.get(name, []))

        def cls(S):
            return NONE if not S else (next(iter(S)) if len(S) == 1 else SEVERAL)
        best, score_b = None, 0
        for i in sorted(range(len(X)), key=lambda i: X[i]):
            e = X[i]
            if e in done:
                continue
            allp = [cls(t[i]) for t, _ in live]
            if len(set(allp)) < 2:
                continue
            score = min(len(allp) - allp.count(c) for c in set(allp))
            if score > score_b:
                best, score_b = e, score
        if best is None:
            return "need knowledge for " + " | ".join("+".join(s) for _, s in live)
        return f"what is {best} {name}"

    # ---------- answers ----------
    def answer(self, s, name):
        self.stats["asks"] += 1
        ver = self.version(name)
        if ver and ver["status"] in ("qualified", "provisional"):
            out = self.apply(frozenset((s,)), name, {})
            prov = ver["status"] == "provisional" or s not in ver["domain"]
        elif name in self.rel.code:
            out, prov = frozenset(self.step(s, name)), False
        else:
            return "unknown"
        if len(out) == 1:
            return f"{s} {name} {next(iter(out))}" + (" [provisional]" if prov else "")
        if out:
            return "ambiguous: " + " or ".join(sorted(out)) + "?"
        return "unknown"

    # ---------- language ----------
    def observe(self, name, s, v):
        lst = self.obs.setdefault(name, [])
        lst[:] = [(x, y) for x, y in lst if x != s] + [(s, v)]

    def turn(self, line):
        raw = line.strip().rstrip("?").rstrip(".").lower()
        parts = raw.split()
        if not parts:
            return "empty"
        head, rest = parts[0], parts[1:]
        if head == "fact" and len(rest) == 3:
            self.tell(*rest)
            return f"recorded {' '.join(rest)}"
        if head == "complete" and rest:
            return "; ".join(f"complete {x}" for x in rest)  # closed world over told facts already
        if head == "example" and ":" in raw and "->" in raw:
            name = raw.split(":", 1)[0].split()[-1]
            lhs, rhs = raw.split(":", 1)[1].split("->")
            self.observe(name, lhs.strip(), rhs.strip())
            got = self.acquire(name)
            return f"{got['result']} {name}" + (f" {'+'.join(got['seq'])}" if "seq" in got else "")
        if head == "correct" and rest and rest[0] == "example" and ":" in raw and "->" in raw:
            name = raw.split(":", 1)[0].split()[-1]
            lhs, rhs = raw.split(":", 1)[1].split("->")
            self.observe(name, lhs.strip(), rhs.strip())
            got = self.acquire(name)
            return f"corrected example {name}: {lhs.strip()} -> {rhs.strip()}; {got['result']} {name}" + \
                (f" {'+'.join(got['seq'])}" if "seq" in got else "")
        if head == "unanswered" and ":" in raw:
            name = raw.split(":", 1)[0].split()[-1]
            subj = raw.split(":", 1)[1].split()
            self.unans.setdefault(name, []).append(subj[0])
            return f"noted: no answer for {subj[0]} {name}"
        if head == "investigate" and len(rest) == 1:
            return self.investigate(rest[0])
        if head == "correct" and len(rest) == 3:
            removed = self.correct(*rest)
            return f"corrected {' '.join(rest)}; removed {len(removed)}"
        if head == "what" and len(rest) == 3 and rest[0] == "is":
            return self.answer(rest[1], rest[2])
        return "unparsed"

    # ---------- state ----------
    def state_doc(self):
        return {"facts": [list(t) for t in self.order], "observations": {k: [list(x) for x in v] for k, v in self.obs.items()},
                "unanswered": self.unans, "capabilities": self.caps, "hypotheses": self.hyp}

    @classmethod
    def from_doc(cls, doc, **kw):
        e = cls(**kw)
        for s, r, o in doc["facts"]:
            e.tell(s, r, o)
        e.obs = {k: [tuple(x) for x in v] for k, v in doc["observations"].items()}
        e.unans = doc["unanswered"]
        e.hyp = doc["hypotheses"]
        for name, cap in doc["capabilities"].items():
            e.caps[name] = cap
            e.prim.add(name)
            for ver in cap["versions"]:
                e.hvec[(name, ver["v"])] = e._encode_cap(ver["seq"])
        for name in doc["capabilities"]:
            e._reindex(name)
        e.new_stats()
        return e

    def validate_touched(self):
        """Per-call check (charged): every fact key written in this call unbinds to its subject code."""
        for k, s, r in self.touched:
            assert C.unbind(k, C.rho(self.prim.code[r])) == self.ent.code[s], "fact key does not unbind to its subject"
            assert all(v in self.ent.name for v in self.facts[k]), "fact value without a clean code"
            assert self.sig[s] & self.rel.hot[r] == self.rel.hot[r], "signature misses a told relation"
        return True

    def validate_full(self):
        """Snapshot-time check (charged): signatures, fact memory and capability index rebuilt from the
        exact journal copy and compared."""
        sig, keys = {}, set()
        for s, r, o in self.order:
            sig[s] = sig.get(s, 0) | self.rel.hot[r]
            keys.add(self._key(s, r))
        assert all(self.sig.get(s) == v for s, v in sig.items()), "signature bundle mismatch"
        assert keys <= set(k for k, v in self.facts.items() if v), "fact memory mismatch"
        for r, lst in self.capidx_list.items():
            F = 0
            for c in lst:
                F |= self.capcb.hot[c]
            assert self.capidx.get(r, 0) == F, "capability index mismatch"
        return True
