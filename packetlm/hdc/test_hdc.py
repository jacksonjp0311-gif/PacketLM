"""G60H checks (docs/G60H.md §9). Run: python3 -m packetlm.hdc.test_hdc"""
from __future__ import annotations
import json
import sys
import tempfile
from pathlib import Path

from . import codes as C
from .engine import HEngine
from .serve import Server

CHECKS = []


def check(f):
    CHECKS.append(f)
    return f


def world(e):
    # two layers of 4 entities and relations a, b (functional), c (one subject two-valued)
    L0, L1, L2 = ["x0", "x1", "x2", "x3"], ["y0", "y1", "y2", "y3"], ["z0", "z1", "z2", "z3"]
    for i in range(4):
        e.tell(L0[i], "a", L1[(i + 1) % 4])
        e.tell(L0[i], "b", L1[(i + 2) % 4])
        e.tell(L1[i], "a", L2[(i + 3) % 4])
        e.tell(L1[i], "b", L2[i])
    return L0, L1, L2


@check
def codes_algebra():
    x, y = C.code("p"), C.code("q")
    assert C.unbind(C.bind(x, y), y) == x and C.bind(x, y) != x
    assert bin(C.onehot(x)).count("1") == C.K
    assert C.lanes(C.rho(x, 3))[3] == C.lanes(x)[0] and C.rho(C.rho(x, 2), C.K - 2) == x
    cb = C.Codebook()
    for i in range(300):
        cb.add(f"n{i}")
    S = cb.hot["n3"] | cb.hot["n200"]
    assert sorted(cb.decode(S)) == ["n200", "n3"]
    assert cb.decode(C.onehot(C.rho(cb.code["n9"], 4)), 4) == ["n9"] and cb.decode(C.onehot(C.rho(cb.code["n9"], 4)), 0) == []


@check
def learns_composition_and_answers():
    e = HEngine()
    L0, L1, L2 = world(e)
    # hidden a then b: x0 -a-> y1 -b-> z1 ; x1 -> y2 -> z2
    r = e.turn("example t: x0 -> z1")
    r = e.turn("example t: x1 -> z2")
    assert r.split()[0] in ("qualified", "provisional", "ambiguous"), r
    while r.split()[0] != "qualified":
        q = e.turn("investigate t")
        assert q.startswith("what is "), q
        s = q.split()[2]
        v = e.apply(frozenset((s,)), "a", {})
        v = e.apply(v, "b", {})
        r = e.turn(f"example t: {s} -> {next(iter(v))}")
    assert e.base("t") == ["a", "b"], e.base("t")
    assert e.turn("what is x2 t") == "x2 t z3"
    assert e.turn("what is y0 t") == "unknown"


@check
def library_reuse_and_no_library_same_answers():
    outs = []
    for lib in (True, False):
        e = HEngine(library=lib)
        world(e)
        for s, v in [("x0", "z1"), ("x1", "z2"), ("x2", "z3"), ("x3", "z0")]:
            e.turn(f"example ab: {s} -> {v}")
        # aba is not definable (layer 2 has no out-edges): use ab then nothing; test cap offered
        offered = e.offered(frozenset(("x0",)), "zz")
        assert ("ab" in offered) == lib, offered
        outs.append([e.turn(f"what is x{i} ab") for i in range(4)])
    assert outs[0] == outs[1]


@check
def statements_none_several():
    e = HEngine()
    world(e)
    e.tell("y9", "c", "z0")
    e.tell("y9", "c", "z1")
    e.tell("y0", "c", "z0")
    e.observe("t", "y9", "!several")
    e.observe("t", "y0", "z0")
    r = e.acquire("t")
    assert r.get("seq") == ["rel:c"], r  # b also maps y0 -> z0 but gives y9 nothing
    e2 = HEngine()
    world(e2)
    e2.observe("u", "x0", "y1")
    e2.observe("u", "z0", "!none")  # z has no out-edges; y0 a z3 would rule a out
    r2 = e2.acquire("u")
    assert r2.get("seq") == ["rel:a"], r2


@check
def correction_propagates():
    e = HEngine()
    world(e)
    for s, v in [("x0", "z1"), ("x1", "z2"), ("x2", "z3"), ("x3", "z0")]:
        e.turn(f"example ab: {s} -> {v}")
    assert e.turn("what is x0 ab").startswith("x0 ab z1")
    assert e.turn("correct y1 b z3").startswith("corrected y1 b z3; removed 1")
    assert e.turn("what is x0 ab").startswith("x0 ab z3")


@check
def outside_domain_is_provisional():
    e = HEngine()
    world(e)
    for s, v in [("x0", "z1"), ("x1", "z2"), ("x2", "z3"), ("x3", "z0")]:
        e.turn(f"example ab: {s} -> {v}")
    assert e.version("ab")["status"] == "qualified"
    e.tell("w0", "a", "y0")
    assert e.turn("what is w0 ab") == "w0 ab z0 [provisional]"


@check
def validation_catches_corruption():
    e = HEngine()
    world(e)
    e.new_stats()
    e.tell("x0", "a", "y1")
    e.tell("x1", "b", "y3")
    assert e.validate_touched() and e.validate_full()
    k = e.touched[0][0]
    caught = 0
    saved = list(e.facts[k])
    e.facts[k] = [12345]
    try:
        e.validate_touched()
    except AssertionError:
        caught += 1
    e.facts[k] = saved
    s0 = e.sig["x1"]
    e.sig["x1"] = 0
    try:
        e.validate_full()
    except AssertionError:
        caught += 1
    e.sig["x1"] = s0
    for s, v in [("x0", "z1"), ("x1", "z2"), ("x2", "z3"), ("x3", "z0")]:
        e.turn(f"example ab: {s} -> {v}")
    r = next(iter(e.capidx))
    e.capidx[r] ^= 1
    try:
        e.validate_full()
    except AssertionError:
        caught += 1
    e.capidx[r] ^= 1
    del e.facts[e._key("x2", "a")]
    try:
        e.validate_full()
    except AssertionError:
        caught += 1
    assert caught == 4, caught


@check
def capability_decode_error_falls_back_and_is_counted():
    e = HEngine()
    world(e)
    for s, v in [("x0", "z1"), ("x1", "z2"), ("x2", "z3"), ("x3", "z0")]:
        e.turn(f"example ab: {s} -> {v}")
    before = [e.turn(f"what is x{i} ab") for i in range(4)]
    e.decoded.clear()
    e.hvec[("ab", 1)] = 0  # wipe the composed hypervector
    after = [e.turn(f"what is x{i} ab") for i in range(4)]
    assert before == after and e.counters["decode_errors"] == 1


@check
def serve_journal_replay_and_reopen():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "s.json"
        srv = Server(every=1000)
        lines = [f"fact x{i} a y{(i + 1) % 4}" for i in range(4)] + [f"fact y{i} b z{i}" for i in range(4)]
        srv.call(p, [], lines)
        r1 = srv.call(p, [], ["example ab: x0 -> z1", "example ab: x1 -> z2", "example ab: x2 -> z3"])["replies"]
        q1 = srv.call(p, [], ["what is x3 ab"])["replies"]
        srv.cur["jfh"].close()
        srv.cur = None  # crash: no snapshot; the journal holds the calls
        srv2 = Server(every=1000)
        q2 = srv2.call(p, [], ["what is x3 ab"])
        assert q2["load"]["loaded"] == "primary" and q2["replies"] == q1, (q1, q2)
        srv2.close()
        doc = json.loads(p.read_text())["state"]
        assert doc["capabilities"]["ab"]["versions"][0]["seq"] == ["rel:a", "rel:b"], doc["capabilities"]
        assert r1[-1].startswith(("qualified", "provisional"))


@check
def blocking_alternative_makes_provisional():
    e = HEngine()
    for t in [("x0", "a", "y1"), ("x1", "a", "y2"), ("x0", "e", "w0"), ("w0", "f", "y1"), ("x1", "e", "w1"), ("w1", "f", "y3")]:
        e.tell(*t)
    e.observe("t", "x0", "y1")
    r = e.acquire("t")
    assert r == {"result": "provisional", "seq": ["rel:a"]}, r  # e+f also maps x0 -> y1 at depth 2
    assert e.turn("investigate t") == "what is x1 t"
    e.observe("t", "x1", "y2")
    assert e.acquire("t")["result"] == "qualified"


@check
def demoted_capability_leaves_index():
    e = HEngine()
    world(e)
    for s, v in [("x0", "z1"), ("x1", "z2"), ("x2", "z3"), ("x3", "z0")]:
        e.turn(f"example ab: {s} -> {v}")
    assert "ab" in e.offered(frozenset(("x0",)), "zz")
    e._cap_provisional("ab")
    assert e.version("ab")["status"] == "provisional"
    assert "ab" not in e.offered(frozenset(("x0",)), "zz") and e.validate_full()


@check
def dead_tuples_are_pruned():
    e = HEngine()
    world(e)
    for s, v in [("x0", "z1"), ("x1", "z2"), ("x2", "z3"), ("x3", "z0")]:
        e.turn(f"example ab: {s} -> {v}")
    e.turn("example u: y0 -> z3")  # at y0 the capability ab (a then b) leads nowhere: pruned
    assert e.hyp["u"]["pruned"] > 0 and e.base("u") == ["a"], e.hyp["u"]


def tiny(e, facts):
    for t in facts.split():
        e.tell(*t.split(","))
    return e


AMB = "x0,a,y0 x0,b,y1 y0,c,z0 y1,c,z0 x1,a,y2 x1,b,y3 y2,c,z1 y3,c,z2"
DEEP = "x0,a,p0 x1,a,p1 x0,b,q0 x1,b,q1 q0,c,r0 q1,c,r1 r0,d,p0 r1,d,s1"
DECOY = ("x0,b,q0 x1,b,q1 q0,c,r0 q1,c,r1 r0,d,p0 r1,d,p1 "
         "x0,e,u0 x1,e,u1 u0,f,v0 u1,f,v1 v0,g,p0 v1,g,w1")


@check
def ambiguity_is_reported_and_investigated():
    # G60H2 (verifier L2): two distinct supported tuples at the first depth -> ambiguous, never qualified
    for kw in ({}, {"library": False, "certifier": "mitm"}, {"check": "equal", "certifier": "mitm"}):
        e = tiny(HEngine(**kw), AMB)
        r = e.turn("example t: x0 -> z0")
        assert r == "ambiguous t", (kw, r)
        assert e.version("t") is None
        assert e.turn("investigate t") == "what is x1 t"
        assert e.turn("example t: x1 -> z2").startswith("qualified t rel:b+rel:c"), kw


@check
def margin_two_sees_two_levels_further():
    # G60H2 (verifier L2): a blocker at depth n+2 is missed at margin 1 and seen at margin 2
    for cert in ("dp", "mitm"):
        e1 = tiny(HEngine(library=False, margin=1, certifier=cert), DEEP)
        assert e1.turn("example t: x0 -> p0") == "qualified t rel:a", cert
        e2 = tiny(HEngine(library=False, margin=2, certifier=cert), DEEP)
        assert e2.turn("example t: x0 -> p0") == "provisional t rel:a", cert
        assert e2.turn("investigate t") == "what is x1 t"


@check
def equal_check_refuses_the_library_decoy():
    # G60H2 §2: the library proposes cap k (= b,c,d) at depth 1; e,f,g also fits at base length 3.
    # Own-language rule (+1 in C's language) qualifies the decoy; the equal check (B's rule) does not.
    def mk(**kw):
        e = tiny(HEngine(**kw), DECOY)
        e._adopt("k", ["rel:b", "rel:c", "rel:d"], "qualified", ["x0", "x1"])
        return e
    own = mk(check="own")
    assert own.turn("example t: x0 -> p0") == "qualified t cap:k@1"
    for cert in ("dp", "mitm"):
        eq, b = mk(check="equal", certifier=cert), tiny(HEngine(library=False, certifier=cert), DECOY)
        assert eq.turn("example t: x0 -> p0") == b.turn("example t: x0 -> p0") == "ambiguous t"
        assert eq.turn("investigate t") == b.turn("investigate t") == "what is x1 t"
        assert eq.turn("example t: x1 -> w1") == "qualified t rel:e+rel:f+rel:g"
        assert eq.counters["prop_runs"] == 2 and eq.counters["cert_runs"] == 2


@check
def equal_check_keeps_library_form_when_it_agrees():
    e = tiny(HEngine(check="equal", certifier="mitm"), DECOY.replace("v1,g,w1", "v1,g,p1"))
    e._adopt("k", ["rel:b", "rel:c", "rel:d"], "qualified", ["x0", "x1"])
    r = e.turn("example t: x0 -> p0")  # bcd and efg are one function on X: one tuple, the library's form kept
    assert r == "qualified t cap:k@1" and e.counters["prop_agree"] == 1, r
    assert e.base("t") == ["b", "c", "d"]


def _rand_facts(rng, n=4, rels="abc", miss=0.2, layers=6, flat=False):
    L = [[f"n{k}_{i}" for i in range(n)] for k in range(layers)]
    out = []
    if flat:  # one pool with cycles: the same function is reachable at several lengths
        pool = [x for lay in L for x in lay][:8]
        for r in rels:
            for s in pool:
                if rng.random() >= miss:
                    out.append((s, r, rng.choice(pool)))
        return [pool], out
    for k in range(layers - 1):
        for r in rels:
            for s in L[k]:
                if rng.random() < miss:
                    continue
                out.append((s, r, rng.choice(L[k + 1])))
                if rng.random() < 0.1:
                    out.append((s, r, rng.choice(L[k + 1])))
    return L, out


def _observe(rng, e, L, prog, k=3):
    for s in rng.sample(L[0], k):
        cur = frozenset((s,))
        for r in prog:
            cur = e.apply(cur, r, {})
        v = "!none" if not cur else (next(iter(cur)) if len(cur) == 1 else "!several")
        e.observe("t", s, v)
    return any(v not in ("!none", "!several") for _, v in e.obs["t"])


@check
def mitm_certificate_equals_dp():
    # G60H2 §2: the meet-in-the-middle certificate returns exactly the DP's verdict, tuples and
    # representatives (HDC and plain engines), on random 6-layer worlds (programs up to length 5, so the
    # backward half is exercised) with missing and multi-valued facts and !none / !several statements
    import random
    from .plain import PlainEngine
    rng = random.Random(7)
    cases, deep = 0, 0
    for trial in range(120):
        kw = {"library": False, "deepen": rng.choice([3, 4, 5]), "margin": rng.choice([1, 2])}
        L, facts = _rand_facts(rng, flat=trial % 2 == 1)
        prog = [rng.choice("abc") for _ in range(rng.randint(1, 5))]
        engines = [HEngine(**kw), PlainEngine(**kw)]
        for e in engines:
            for f in facts:
                e.tell(*f)
        st = rng.getstate()
        ok = [(rng.setstate(st), _observe(rng, e, L, prog))[1] for e in engines]
        if not ok[0]:
            continue
        a = engines[0]._search("t", False, engines[0].margin)
        for e in engines:
            b = e._mitm("t")
            for k in ("X", "found", "groups", "blockers", "searched"):
                assert a[k] == b[k], (trial, type(e).__name__, k, a[k], b[k])
        cases += 1
        deep += (a["found"] or 0) + kw["margin"] > 3
    assert cases > 60 and deep > 20, (cases, deep)


@check
def equal_check_adopts_the_certified_program_when_the_proposal_differs():
    # the proposal (cap k = b,c,d at depth 1) differs from B's rule's candidate (a,h at base length 2,
    # with b,c,d a blocker at 3): the certified base program is adopted, provisional
    w = "x0,a,m0 x1,a,m1 m0,h,p0 m1,h,p1 x0,b,q0 x1,b,q1 q0,c,r0 q1,c,r1 r0,d,p0 r1,d,s1"
    for cert in ("dp", "mitm"):
        e = tiny(HEngine(check="equal", certifier=cert), w)
        e._adopt("k", ["rel:b", "rel:c", "rel:d"], "qualified", ["x0", "x1"])
        assert e.turn("example t: x0 -> p0") == "provisional t rel:a+rel:h", cert
        assert e.counters["prop_differ"] == 1 and e.counters["prop_agree"] == 0


@check
def mitm_prunes_dead_prefixes():
    e = tiny(HEngine(library=False, certifier="mitm"), "x0,a,y0 x1,a,y1 y0,b,z0")
    e.turn("example t: x0 -> y0")
    assert e.turn("example t: x1 -> y1") == "qualified t rel:a"
    assert e.hyp["t"]["pruned"] > 0, e.hyp["t"]  # a,b is dead at x1


@check
def certificate_memo_follows_new_facts_and_corrections():
    # the certifier's image memo is cleared when a known entity changes (a new fact or a correction)
    for change in ("fact x0 a q9", "correct x1 b y0", "correct y3 c z1", "fact y2 c z2"):
        e = tiny(HEngine(library=False, certifier="mitm"), AMB + " x2,a,y0 x2,b,y3")
        e.turn("example t: x0 -> z0")
        e.turn(change)
        e.turn("example t: x1 -> z1")
        d = tiny(HEngine(library=False), AMB + " x2,a,y0 x2,b,y3")
        d.turn(change)
        d.observe("t", "x0", "z0")
        d.observe("t", "x1", "z1")
        a, b = d._search("t", False, 1), e._mitm("t")
        assert all(a[k] == b[k] for k in ("X", "found", "groups", "blockers")), (change, a, b)


@check
def plain_engine_answers_identically():
    # G60H2 ablation: exact dicts/sets in place of the hypervector parts give the same replies
    from .plain import PlainEngine
    for kw in ({}, {"check": "equal", "certifier": "mitm"}):
        lines = []
        h, p = HEngine(**kw), PlainEngine(**kw)
        for x in (h, p):
            world(x)
        for ln in ["example t: x0 -> z1", "example t: x1 -> z2", "investigate t", "example ab: x0 -> z1",
                   "example ab: x2 -> z3", "investigate ab", "example u: y0 -> z3", "what is x3 t", "correct x0 a y3",
                   "what is x0 t", "example v: x1 -> z0", "investigate v"]:
            lines.append((h.turn(ln), p.turn(ln)))
        assert all(a == b for a, b in lines), lines
        assert p.validate_full() and p.validate_touched()


@check
def collisions_are_counted_and_lose_nothing():
    # G60H2 (verifier L1): with tiny codes (K=2, L=4) keys, codes and signatures collide; every
    # collision is counted and the exact copies keep the answers equal to the plain engine's
    import os
    import subprocess
    prog = (
        "from packetlm.hdc.engine import HEngine\nfrom packetlm.hdc.plain import PlainEngine\n"
        "from packetlm.hdc import test_hdc as T\nimport json\n"
        "h,p=HEngine(),PlainEngine()\n"
        "for x in (h,p): T.world(x)\n"
        "L=['example t: x0 -> z1','example t: x1 -> z2','investigate t','what is x3 t','what is y1 a','what is x2 b']\n"
        "r=[(h.turn(l),p.turn(l)) for l in L]\n"
        "c=dict(h.counters); c['code']=sum(cb.collisions for cb in (h.ent,h.prim,h.rel))\n"
        "print(json.dumps({'same':all(a==b for a,b in r),'c':c}))\n")
    env = dict(os.environ, PACKETLM_HDC_K="2", PACKETLM_HDC_L="4")
    out = subprocess.run([sys.executable, "-c", prog], env=env, capture_output=True, text=True,
                         cwd=Path(__file__).resolve().parents[2])
    got = json.loads(out.stdout.strip().splitlines()[-1])
    c = got["c"]
    assert got["same"], got
    assert c["code"] > 0 and c["collisions"] > 0 and c["inv_collisions"] > 0, c
    assert c["key_collision_reads"] > 0 and c["code_collision_reads"] > 0, c


@check
def signature_and_index_decode_errors_are_counted():
    # G60H2 (verifier L1): a spurious or missing item in a signature / index cleanup is counted and the
    # exact copy is used
    e = HEngine()
    world(e)
    real = e.rel.decode
    e.rel.decode = lambda S, k=0, st=None: real(S, k, st)[:1] + ["zz"]
    assert sorted(e.rels_of("x0")) == ["a", "b"]
    assert e.counters["sig_spurious"] == 1 and e.counters["sig_missing"] == 1
    e.rel.decode = real
    e._adopt("k", ["rel:a", "rel:b"], "qualified", ["x0"])
    e.capcb.decode = lambda S, k=0, st=None: []
    assert "k" in e.offered(frozenset(("x0",)), "t") and e.counters["capidx_missing"] == 1


@check
def no_engine_import_from_existing():
    import packetlm.hdc.engine as he
    src = Path(he.__file__).read_text() + Path(C.__file__).read_text()
    assert "from ..engine" not in src and "import packetlm.engine" not in src


def main():
    failed = 0
    for f in CHECKS:
        try:
            f()
            print("ok  ", f.__name__)
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print("FAIL", f.__name__, repr(exc))
    print(json.dumps({"checks": len(CHECKS), "failed": failed}))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
