"""Verifier's deterministic crash-point test for packetlm/serve.py (d6cbcf3).
The Server runs in this process. During one chosen call, the n-th durability step (os.fsync,
os.replace or os.link, anywhere in serve.py/engine.py) raises Crash instead of running: the
process 'dies' there (written bytes stay, as after kill -9; open files are closed). A new Server
then continues: the crashed call is resent unless the recovered state already contains it (state
turn equals the per-process reference's turn after that call). Every (call, n) pair is tried.
Compared: final state after close vs the per-process reference (values and whole file bytes);
recovery errors are reported.
Usage: serve_faults.py N SEED [extra flags]"""
import json, os, random, shutil, sys, tempfile
from pathlib import Path
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import serve_diff, lean_diff  # noqa: E402
sys.path.insert(0, lean_diff.ROOT)
os.chdir(lean_diff.ROOT)
from packetlm.serve import Server  # noqa: E402


class Crash(BaseException):
    pass


REAL = {k: getattr(os, k) for k in ("fsync", "replace", "link")}
ARM = {"n": None, "seen": 0, "where": None}


def _wrap(name):
    def f(*a, **k):
        if ARM["n"] is not None:
            ARM["seen"] += 1
            if ARM["seen"] == ARM["n"]:
                ARM["n"] = None
                ARM["where"] = f"{name}({', '.join(os.path.basename(str(x)) for x in a if not isinstance(x, int))})"
                raise Crash()
        return REAL[name](*a, **k)
    return f


for k in REAL:
    setattr(os, k, _wrap(k))


def drop(srv):
    if srv.cur and srv.cur.jfh:
        srv.cur.jfh.close()


def run(batches, flags, every, c, n):
    d = tempfile.mkdtemp(); st = os.path.join(d, "s.json")
    srv = Server(every); out = {"crashed": False}
    for i, b in enumerate(batches):
        if i == c:
            ARM.update(n=n, seen=0, where=None)
        try:
            srv.call(st, flags, b)
        except Crash:
            out.update(crashed=True, where=ARM["where"])
            drop(srv); srv = Server(every)
            t = serve_diff.recovered_turn(st, flags)
            out["recovered_turn"] = t
            if isinstance(t, str):
                out["error"] = t
                break
            if t != serve_diff.TURNS[i]:
                try:
                    srv.call(st, flags, b)
                except Exception as exc:  # noqa: BLE001
                    out["error"] = f"resend: {exc}"; break
        except Exception as exc:  # noqa: BLE001
            out["error"] = f"call {i}: {type(exc).__name__}: {exc}"; break
        finally:
            ARM["n"] = None
    if "error" not in out:
        try:
            srv.close()
            serve_diff.finalize(st, flags)
        except Exception as exc:  # noqa: BLE001
            out["error"] = f"close/final recovery: {exc}"
    raw = open(st, "rb").read() if os.path.exists(st) else None
    shutil.rmtree(d)
    return raw, out


if __name__ == "__main__":
    N, seed, extra = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3:]
    flags = serve_diff.BASE + extra
    rng = random.Random(seed)
    tot = {"sessions": N, "runs": 0, "crashes": 0, "final_state_differs": 0, "final_bytes_differ": 0, "errors": 0}
    bad = []
    for s in range(N):
        b = [x for x in lean_diff.session(rng) if x][:6]
        refrep, refraw = serve_diff.ref_run(b, flags)
        every = rng.choice([1, 2, 64])
        for c in range(len(b)):
            for n in range(1, 14):
                raw, out = run(b, flags, every, c, n)
                tot["runs"] += 1
                if not out["crashed"]:
                    break  # fewer than n durability steps in this call
                tot["crashes"] += 1
                if "error" in out:
                    tot["errors"] += 1; bad.append({"session": s, "every": every, "call": c, "n": n, **out}); continue
                if raw != refraw:
                    tot["final_bytes_differ"] += 1
                    g, r = json.loads(raw)["state"] if raw else None, json.loads(refraw)["state"]
                    if g != r:
                        tot["final_state_differs"] += 1
                        bad.append({"session": s, "every": every, "call": c, "n": n, **out,
                                    "turn": [g and g["turn"], r["turn"]]})
    print(json.dumps({"seed": seed, "flags": flags, **tot}))
    import collections
    print(json.dumps({"errors_by": collections.Counter(f"every={x['every']} call={x['call']} at {x.get('where')}: {x.get('error','')[:50]}" for x in bad if 'error' in x)}))
    seen = set()
    for x in bad:
        k = (x.get("where"), x.get("error", "")[:40], x["every"])
        if k not in seen:
            seen.add(k); print(json.dumps(x))
