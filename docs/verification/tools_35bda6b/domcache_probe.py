"""Probe the `_dom_set` cache key (name, v, id(ver["domain"])): run the indexed_diff sessions with
a wrapper that, on every cache hit, checks the cached set against the live ver["domain"]."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.dirname(__file__))
from packetlm import engine
hits = {"hit": 0, "stale": 0, "calls": 0}
orig = engine.Engine._dom_set
def wrapped(self, name, ver):
    hits["calls"] += 1
    c = getattr(self, "_dom_cache", {})
    if c.get("key") == (name, ver["v"], id(ver["domain"])):
        hits["hit"] += 1
        if c["set"] != set(ver["domain"]):
            hits["stale"] += 1
            print("STALE", name, ver["v"], sorted(c["set"])[:5], sorted(ver["domain"])[:5], flush=True)
    return orig(self, name, ver)
engine.Engine._dom_set = wrapped
import indexed_diff
try:
    indexed_diff.main()
finally:
    print("domcache", hits)
