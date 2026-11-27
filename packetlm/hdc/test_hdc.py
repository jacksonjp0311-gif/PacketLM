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
