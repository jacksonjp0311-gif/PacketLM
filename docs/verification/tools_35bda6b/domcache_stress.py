"""Directed probe of the `_dom_set` cache (key = (name, v, id(ver["domain"]))) in a long-lived
serve engine: an answer caches domain list A; then two domain replacements happen with no
`_dom_set` call between them (growth requalification after a fact at a new entity, or
`requalify`), so the third list may reuse A's address; then an entity of the new domain is asked.
Detector: on every cache hit, compare the cached set with the live ver["domain"]; and compare each
reply with a fresh engine opened on the same snapshot (no cache).
Usage: domcache_stress.py N SEED"""
import sys, os, random, tempfile, shutil, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..")); sys.path.insert(0, HERE)
from packetlm import engine
from packetlm.serve import Server
import indexed_diff as D
st = {"hit": 0, "stale": 0, "fresh_diff": 0, "calls": 0}
orig = engine.Engine._dom_set
def wrapped(self, name, ver):
    c = getattr(self, "_dom_cache", {})
    if c.get("key") == (name, ver["v"], id(ver["domain"])):
        st["hit"] += 1
        if c["set"] != set(ver["domain"]):
            st["stale"] += 1
    return orig(self, name, ver)
engine.Engine._dom_set = wrapped
FL = ["--answers", "--bounded", "--lean"] + sys.argv[3:]
def main():
    n, seed = int(sys.argv[1]), int(sys.argv[2]); rng = random.Random(seed)
    for i in range(n):
        ents, rels, tri = D.world(rng)
        name = "zz"; seq = [rng.choice(rels)]
        calls = [[f"fact {s} {r} {o}" for s, r, o in sorted(tri)], D.examples(rng, tri, ents, name, seq, 4)]
        k = 0
        for _ in range(12):
            calls.append([f"what is {x} {name}" for x in ents])
            pat = rng.random()
            for _ in range(2):
                if pat < 0.5:
                    k += 1; calls.append([f"fact {rng.choice(ents)} {seq[0]} n{k}", f"fact n{k} {seq[0]} {rng.choice(ents)}"])
                    calls.append(["what is zq zz"])
                else:
                    calls.append([f"requalify {name}"])
                ents.append(f"n{k}") if pat < 0.5 else None
            calls.append([f"what is {x} {name}" for x in ents])
        d = tempfile.mkdtemp(); p = os.path.join(d, "s.json")
        srv = Server()
        for c in calls:
            st["calls"] += 1
            before = st["stale"]
            srv.call(p, FL, c)
            if st["stale"] > before and st["stale"] <= 3:
                print("STALE in session", i, "call", c[:3], flush=True)
        srv.close(); shutil.rmtree(d)
    print(json.dumps(st))
main()
