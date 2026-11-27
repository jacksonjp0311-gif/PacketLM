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
  support: several distinct tuples -> `ambiguous`; one -> candidate, searched `margin` levels further (registered
  margin 1: n+1): a new supported tuple there blocks (-> `provisional`), else `qualified`. Answers are qualified only on
  X (the decided domain); elsewhere [provisional].
G60H2 (docs/G60H2.md): `check="equal"` makes C's verdict B's base-language rule on the same evidence
(the library only proposes); `certifier="mitm"` computes that rule by meet in the middle (exactly the DP);
every hypervector read has a counted exact check (collisions, signature / index / capability decodes).
"""
from __future__ import annotations
from . import codes as C

OMEGA = 16
NONE, SEVERAL = "!none", "!several"


class HEngine:
    def __init__(self, library=True, deepen=5, margin=1, check="own", certifier="dp"):
        assert check in ("own", "equal") and certifier in ("dp", "mitm")
        self.library, self.deepen, self.margin = library, deepen, margin
        self.check, self.certifier = check, certifier
        self.owner, self.spill = {}, {}  # bound key -> (s, r) that owns it; colliding (s, r) -> values (G60H2 L1)
        self.relx = {}                   # entity -> exact relation set (verifies signature decodes; charged)
        self.inv, self.iowner, self.ispill = {}, {}, {}  # inverse fact memory bind(o, rho^2 r) -> subjects (G60H2 certifier)
        self.isig, self.irelx = {}, {}   # object -> in-relation bundle / exact {r: count}
        self.pcache = {}                 # (entity, base seq) -> image (certifier memo; cleared when a known entity changes)
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
        self.counters = {"decode_errors": 0, "decodes": 0, "sig_decodes": 0, "collisions": 0, "key_collision_reads": 0,
                         "sig_spurious": 0, "sig_missing": 0, "isig_spurious": 0, "isig_missing": 0,
                         "capidx_spurious": 0, "capidx_missing": 0, "inv_collisions": 0, "code_collision_reads": 0,
                         "cert_runs": 0, "prop_runs": 0, "prop_agree": 0, "prop_differ": 0, "prop_none": 0}
        self.new_stats()

    def new_stats(self):
        self.stats = {"evaluations": 0, "executions": 0, "row_ops": 0, "asks": 0, "cleanup_checks": 0}
        self.touched = []

    # ---------- memory ----------
    def _key(self, s, r):
        return C.bind(self.ent.add(s), C.rho(self.prim.add(r)))

    def _vals(self, s, r, k):
        """The value list of (s, r): the fact memory slot, unless another (s', r') owns that bound key
        (a key collision, counted; the colliding pair is kept exactly in the spill table)."""
        own = self.owner.get(k)
        if own is None:
            self.owner[k] = (s, r)
            return self.facts.setdefault(k, [])
        if own != (s, r):
            if (s, r) not in self.spill:
                self.counters["collisions"] += 1
            return self.spill.setdefault((s, r), [])
        return self.facts.setdefault(k, [])

    def _ikey(self, o, r):
        return C.bind(self.ent.add(o), C.rho(self.prim.add(r), 2))

    def _ivals(self, o, r, k):
        own = self.iowner.get(k)
        if own is None:
            self.iowner[k] = (o, r)
            return self.inv.setdefault(k, [])
        if own != (o, r):
            if (o, r) not in self.ispill:
                self.counters["inv_collisions"] += 1
            return self.ispill.setdefault((o, r), [])
        return self.inv.setdefault(k, [])

    def tell(self, s, r, o):
        if s in self.ent.code:
            self.pcache.clear()  # a known entity changes: certifier memo invalid (exact; new entities keep it)
        self.rel.add(r)
        self.prim.add(r)
        k = self._key(s, r)
        oc = self.ent.add(o)
        vals = self._vals(s, r, k)
        if oc not in vals:
            vals.append(oc)
            self.order.append((s, r, o))
            iv = self._ivals(o, r, self._ikey(o, r))
            iv.append(self.ent.code[s])
            ir = self.irelx.setdefault(o, {})
            ir[r] = ir.get(r, 0) + 1
            self.isig[o] = self.isig.get(o, 0) | self.rel.hot[r]
        self.sig[s] = self.sig.get(s, 0) | self.rel.hot[r]
        self.relx.setdefault(s, set()).add(r)
        if s not in self.rsubset.setdefault(r, set()):
            self.rsubset[r].add(s)
            self.rsub.setdefault(r, []).append(s)
        self.touched.append((k, s, r))

    def correct(self, s, r, o):
        k = self._key(s, r)
        vals = self._vals(s, r, k)  # (tell below clears the certifier memo: s is known)
        old = list(vals)
        removed = [self.ent.name[c] for c in old if self.ent.name[c] != o]
        self.order = [t for t in self.order if not (t[0] == s and t[1] == r)]
        sc = self.ent.code[s]
        for c in old:
            ob = self.ent.name[c]
            iv = self._ivals(ob, r, self._ikey(ob, r))
            if sc in iv:
                iv.remove(sc)
            ir = self.irelx[ob]
            ir[r] -= 1
            if not ir[r]:
                del ir[r]
                self.isig[ob] = 0
                for r2 in ir:
                    self.isig[ob] |= self.rel.hot[r2]
        vals[:] = []
        self.tell(s, r, o)
        return removed

    def step(self, e, r):
        """One relation step: bind, look up, clean up the value codes (O(K))."""
        self.stats["row_ops"] += 1
        c = self.ent.code.get(e)
        pc = self.prim.code.get(r)
        if c is None or pc is None:
            return ()
        k = C.bind(c, C.rho(pc))
        own = self.owner.get(k)
        if own is None:
            return ()
        if own != (e, r):  # bound-key collision: verified against the owner (charged), exact spill used
            self.counters["key_collision_reads"] += 1
            vals = self.spill.get((e, r))
        else:
            vals = self.facts.get(k)
        if not vals:
            return ()
        if self.ent.collided and (c in self.ent.collided or any(v in self.ent.collided for v in vals)):
            self.counters["code_collision_reads"] += 1  # value or subject code not unique: exact copy
            return tuple(o for s, r2, o in self.order if s == e and r2 == r)
        return tuple(self.ent.name[v] for v in vals)

    def pre(self, o, r):
        """Inverse step: the subjects s with o in r(s) (inverse fact memory, O(K))."""
        self.stats["row_ops"] += 1
        c, pc = self.ent.code.get(o), self.prim.code.get(r)
        if c is None or pc is None:
            return ()
        k = C.bind(c, C.rho(pc, 2))
        own = self.iowner.get(k)
        if own is None:
            return ()
        vals = self.inv.get(k) if own == (o, r) else self.ispill.get((o, r))
        if own != (o, r):
            self.counters["key_collision_reads"] += 1
        if not vals:
            return ()
        if self.ent.collided and (c in self.ent.collided or any(v in self.ent.collided for v in vals)):
            self.counters["code_collision_reads"] += 1
            return tuple(s for s, r2, o2 in self.order if o2 == o and r2 == r)
        return tuple(self.ent.name[v] for v in vals)

    def _checked(self, got, exact, kind):
        """Decoded relation set verified against the exact copy (charged); errors counted, exact used."""
        g = set(got)
        if g == exact:
            return got
        self.counters[kind + "_spurious"] += len(g - exact)
        self.counters[kind + "_missing"] += len(exact - g)
        return sorted(exact)

    def rels_of(self, e):
        S = self.sig.get(e)
        if not S:
            return []
        self.counters["sig_decodes"] += 1
        return self._checked(self.rel.decode(S, 0, self.stats), self.relx.get(e, set()), "sig")

    def in_rels(self, o):
        S = self.isig.get(o)
        if not S:
            return []
        self.counters["sig_decodes"] += 1
        return self._checked(self.rel.decode(S, 0, self.stats), set(self.irelx.get(o, {})), "isig")

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

    def offered(self, ents, exclude, lib=None):
        rels = set()
        for e in ents:
            rels.update(self.rels_of(e))
        out = sorted(rels)
        if self.library if lib is None else lib:
            caps = set()
            for r in out:
                F = self.capidx.get(r)
                if F:
                    caps.update(self._capdecode(F, r))
            caps.discard(exclude)
            out += sorted(caps)
        return out

    def _capdecode(self, F, r):
        got = set(self.capcb.decode(F, 0, self.stats))
        exact = self.capidx_list.get(r, set())
        if got != exact:
            self.counters["capidx_spurious"] += len(got - exact)
            self.counters["capidx_missing"] += len(exact - got)
        return exact

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

    def _setup(self, name):
        obs = self.obs.get(name, [])
        X, nx = self.domain(name)
        want = {}
        for s, v in obs:
            want[X.index(s)] = v
        vi = [i for i, v in want.items() if v not in (NONE, SEVERAL)]

        def match(t, pos=None):
            for i, v in want.items():
                S = t[i] if pos is None else t[pos[i]]
                if v == NONE:
                    if S:
                        return False
                elif v == SEVERAL:
                    if len(S) < 2:
                        return False
                elif S != frozenset((v,)):
                    return False
            return True
        return X, want, vi, match

    def _search(self, name, lib, margin):
        """Iterative deepening DP over tuples on X in the language offered (lib: + capabilities).
        margin None: stop at the first supported depth (a proposal, G60H2)."""
        X, want, vi, match = self._setup(name)
        i0 = vi[0]
        start = tuple(frozenset((e,)) for e in X)
        seen, frontier, memo = {start}, [(start, [])], {}
        found, groups, blockers, pruned = None, [], [], 0
        searched = self.deepen
        for n in range(1, self.deepen + 1):
            new = []
            for t, seq in frontier:
                for p in self.offered(t[i0], name, lib):
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
                    if len(sup) > 1 or margin is None:
                        break
            else:
                blockers += sup
                if n >= found + margin:
                    break
            if not frontier:
                break
        return {"X": X, "found": found, "groups": groups, "blockers": blockers, "searched": searched, "pruned": pruned}

    def _mitm(self, name):
        """Base-language certificate, meet in the middle (G60H2 §2). Exactly B's verdict (same first
        supported depth n, same distinct supported tuples on X through min(deepen, n+margin), same
        representative = lexicographically first shortest program, as B's DP), computed from forward
        images of base prefixes (length <= A) of the observed subjects and inverse steps from the first
        observed value (suffixes), joined on the meeting entity; every joined program is checked exactly."""
        X, want, vi, match = self._setup(name)
        W = sorted(want)
        Xo = [X[i] for i in W]
        posw = {i: j for j, i in enumerate(W)}
        p0, v0 = posw[vi[0]], want[vi[0]]
        vpos = [posw[i] for i in vi]
        pc, st = self.pcache, self.stats

        def img(e, seq):
            key = (e, seq)
            got = pc.get(key)
            if got is None:
                prev = img(e, seq[:-1]) if len(seq) > 1 else (e,)
                out = set()
                r = seq[-1]
                for x in prev:
                    st["executions"] += 1
                    out.update(self.step(x, r))
                got = frozenset(out)
                pc[key] = got
            return got
        A = min(3, self.deepen)
        level, pref, pruned = [((), None)], {}, 0
        for d in range(1, A + 1):
            nxt = []
            for seq, pj in level:
                at = (Xo[p0],) if pj is None else pj[p0]
                for r in self.offered(at, name, False):
                    st["evaluations"] += 1
                    s2 = seq + (r,)
                    pj2 = tuple(img(e, s2) for e in Xo)
                    if any(not pj2[j] for j in vpos):
                        pruned += 1
                        continue
                    nxt.append((s2, pj2))
            pref[d] = nxt
            level = nxt
        idx = {}
        for k, (seq, pj) in enumerate(pref.get(A, ())):
            for e in pj[p0]:
                idx.setdefault(e, []).append(k)

        def suffixes(b):
            """(suffix, entities from which it reaches v0), all base suffixes of length b."""
            out, lev = [], [((), (v0,))]
            for _ in range(b):
                nl = []
                for w, ents in lev:
                    rs = set()
                    for e in ents:
                        rs.update(self.in_rels(e))
                    for r in sorted(rs):
                        st["evaluations"] += 1
                        P = set()
                        for e in ents:
                            P.update(self.pre(e, r))
                        if P:
                            nl.append(((r,) + w, tuple(sorted(P))))
                lev = nl
            return lev

        def supported(L):
            if L <= A:
                progs = [seq for seq, pj in pref.get(L, ()) if match(pj, posw)]
            else:
                progs = []
                P3 = pref.get(A, ())
                for w, ents in suffixes(L - A):
                    ks = set()
                    for e in ents:
                        ks.update(idx.get(e, ()))
                    for k in sorted(ks):
                        st["evaluations"] += 1
                        seq = P3[k][0] + w
                        if match(tuple(img(e, seq) for e in Xo), posw):
                            progs.append(seq)
            best = {}
            for seq in progs:
                t = tuple(img(e, seq) for e in X)
                if t not in best or seq < best[t]:
                    best[t] = seq
            return best
        found, groups, blockers, seen = None, [], [], set()
        searched = self.deepen
        for n in range(1, self.deepen + 1):
            got = supported(n)
            sup = sorted(((t, list(q)) for t, q in got.items() if t not in seen), key=lambda x: x[1])
            seen.update(got)
            if found is None:
                if sup:
                    found, groups, searched = n, sup, n
                    if len(sup) > 1:
                        break
            else:
                blockers += sup
                if n >= found + self.margin:
                    break
        return {"X": X, "found": found, "groups": groups, "blockers": blockers, "searched": searched, "pruned": pruned}

    def _certify(self, name):
        self.counters["cert_runs"] += 1
        if self.certifier == "mitm":
            return self._mitm(name)
        return self._search(name, False, self.margin)

    def acquire(self, name):
        obs = self.obs.get(name, [])
        if not any(v not in (NONE, SEVERAL) for _, v in obs):
            return {"result": "none"}
        prop = None
        if not self.library:
            res = self._certify(name)                       # B, P: the base-language rule
        elif self.check == "own":
            res = self._search(name, True, self.margin)     # G60H: margin in C's own language
        else:
            # G60H2 equal check: the library proposes (first supported depth in C's language, charged);
            # the verdict is the base-language rule's (B's), on the same evidence, fully charged.
            self.counters["prop_runs"] += 1
            prop = self._search(name, True, None)
            res = self._certify(name)
        X, found, groups, blockers = res["X"], res["found"], res["groups"], res["blockers"]
        rec = {"searched_len": res["searched"], "pruned": res["pruned"], "evaluated": self.stats["evaluations"]}
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
        if prop is not None:
            pg = prop["groups"]
            if len(pg) == 1 and pg[0][0] == t:
                self.counters["prop_agree"] += 1
                seq = pg[0][1]          # same function on X: keep the library's (compositional) form
            elif pg:
                self.counters["prop_differ"] += 1
            else:
                self.counters["prop_none"] += 1
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
