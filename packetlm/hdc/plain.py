"""G60H2 ablation (M1): the G60H/G60H2 engine with plain exact data structures in place of every
hypervector part. Fact memory is a dict keyed by (s, r); signatures are exact relation sets; a
capability is its exact primitive sequence; the capability index is the exact per-relation set; the
inverse memory is a dict keyed by (o, r). Search, certification, language and protocol are inherited
unchanged from HEngine, so any difference in cost or answers is due to the representation alone."""
from __future__ import annotations
from .engine import HEngine


class Names:
    """Membership only (no codes)."""

    def __init__(self):
        self.code = {}
        self.collisions = 0

    def add(self, nm):
        self.code[nm] = True
        return nm


class PlainEngine(HEngine):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.ent, self.prim, self.rel, self.capcb = Names(), Names(), Names(), Names()

    def tell(self, s, r, o):
        if s in self.ent.code:
            self.pcache.clear()
        self.rel.add(r)
        self.prim.add(r)
        self.ent.add(s)
        self.ent.add(o)
        vals = self.facts.setdefault((s, r), [])
        if o not in vals:
            vals.append(o)
            self.order.append((s, r, o))
            self.inv.setdefault((o, r), []).append(s)
            ir = self.irelx.setdefault(o, {})
            ir[r] = ir.get(r, 0) + 1
        self.relx.setdefault(s, set()).add(r)
        self.sig[s] = True
        if s not in self.rsubset.setdefault(r, set()):
            self.rsubset[r].add(s)
            self.rsub.setdefault(r, []).append(s)
        self.touched.append(((s, r), s, r))

    def correct(self, s, r, o):
        old = list(self.facts.get((s, r), []))
        removed = [x for x in old if x != o]
        self.order = [t for t in self.order if not (t[0] == s and t[1] == r)]
        for ob in old:
            iv = self.inv.get((ob, r), [])
            if s in iv:
                iv.remove(s)
            ir = self.irelx[ob]
            ir[r] -= 1
            if not ir[r]:
                del ir[r]
        self.facts[(s, r)] = []
        self.tell(s, r, o)
        return removed

    def step(self, e, r):
        self.stats["row_ops"] += 1
        return tuple(self.facts.get((e, r), ()))

    def pre(self, o, r):
        self.stats["row_ops"] += 1
        return tuple(self.inv.get((o, r), ()))

    def rels_of(self, e):
        return sorted(self.relx.get(e, ()))

    def in_rels(self, o):
        return sorted(self.irelx.get(o, {}))

    def _capdecode(self, F, r):
        return self.capidx_list.get(r, set())

    def offered(self, ents, exclude, lib=None):
        rels = set()
        for e in ents:
            rels.update(self.relx.get(e, ()))
        out = sorted(rels)
        if self.library if lib is None else lib:
            caps = set()
            for r in out:
                caps.update(self.capidx_list.get(r, ()))
            caps.discard(exclude)
            out += sorted(caps)
        return out

    def _encode_cap(self, seq):
        return tuple(seq)

    def steps(self, name):
        ver = self.version(name)
        key = (name, ver["v"])
        got = self.decoded.get(key)
        if got is None:
            got = [p.split(":", 1)[1].split("@")[0] for p in ver["seq"]]
            self.decoded[key] = got
        return got

    def _reindex(self, name):
        for lst in self.capidx_list.values():
            lst.discard(name)
        ver = self.version(name)
        if ver and ver["status"] == "qualified":
            self.capidx_list.setdefault(self.base(name)[0], set()).add(name)

    def validate_touched(self):
        for k, s, r in self.touched:
            assert k == (s, r) and r in self.relx[s], "plain fact without its relation"
            assert all(s in self.inv[(o, r)] for o in self.facts[k]), "inverse memory misses a fact"
        return True

    def validate_full(self):
        keys = {}
        for s, r, o in self.order:
            keys.setdefault((s, r), set()).add(o)
        assert all(set(self.facts.get(k, ())) == v for k, v in keys.items()), "fact memory mismatch"
        for r, lst in self.capidx_list.items():
            assert all(self.version(c)["status"] == "qualified" and self.base(c)[0] == r for c in lst), "index mismatch"
        return True
