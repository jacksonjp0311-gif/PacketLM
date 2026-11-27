"""HDC serve with a shadow uniqueness audit (verifier, untimed). Every acquire() is also re-run on deep
copies of the pre-call engine under other certificates; the real engine is never touched by the shadows.
  B1: base language (no library), margin 1       (= what B's rule says on C's evidence)
  B5: base language, horizon 5 (all depths <= 5)  (= G59-like horizon)
  C5: the arm's own language, horizon 5 (only if SHADOW_C5=1)
"""
import copy, json, os, sys, hashlib
sys.path.insert(0, os.getcwd())
from packetlm.hdc import engine as E, serve

LOG = open(os.environ["SHADOW_LOG"], "a")
orig = E.HEngine.acquire


def h(t):
    return hashlib.sha256(json.dumps([sorted(x) for x in t]).encode()).hexdigest()[:16]


def summary(eng, name, r):
    X, live = eng.live.get(name, (None, []))
    out = {"result": r["result"], "seq": r.get("seq"), "searched": eng.hyp.get(name, {}).get("searched_len"),
           "found_tuples": [h(t) for t, _ in live], "n_live": len(live)}
    if r["result"] in ("qualified", "provisional"):
        out["tuple"] = h(live[0][0])
    return out


def acq(self, name):
    pre = copy.deepcopy(self)
    r = orig(self, name)
    rec = {"name": name, "library": self.library, "margin": self.margin, "nobs": len(self.obs.get(name, [])),
           "real": summary(self, name, r)}
    variants = [("B1", False, 1), ("B5", False, 99)]
    if os.environ.get("SHADOW_C5") == "1":
        variants.append(("C5", self.library, 99))
    for tag, lib, m in variants:
        s = copy.deepcopy(pre)
        s.library, s.margin, s.deepen = lib, m, 5
        rr = orig(s, name)
        rec[tag] = summary(s, name, rr)
        rec[tag]["evaluations"] = s.stats["evaluations"] - pre.stats["evaluations"]
    rec["real"]["evaluations"] = self.stats["evaluations"] - pre.stats["evaluations"]
    LOG.write(json.dumps(rec) + "\n")
    LOG.flush()
    return r


E.HEngine.acquire = acq
serve.HEngine = E.HEngine
if __name__ == "__main__":
    raise SystemExit(serve.main())
