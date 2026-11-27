"""Verifier's differential test for packetlm/serve.py (d6cbcf3).

Random sessions (lean_diff.session: facts, examples incl. !none/!several, complete, retract, correct,
investigate, requalify, what-is) are cut into random calls and run
  ref    one `python -m packetlm.engine STATE FLAGS --lean` process per call (G56's Xl)
  serve  one `python -m packetlm.serve` process (random PACKETLM_SNAPSHOT_EVERY), same calls, with
         random interleaved calls on brand-new paths (B-style tasks; their replies are checked
         against a fresh per-process run of the same lines), random kill -9 between calls, and
         random kill -9 in the middle of a call (then the call is resent unless the journal or a
         snapshot shows it was applied; an applied call's journaled reply hash is checked).
Compared: every reply, and the final state file after close (whole bytes, and the state text).
In-process mode (--inproc): the Server class runs in this process and after every call the
in-memory state is compared type- and order-strictly (a) with its own JSON round trip and (b) with
the state a second Server recovers from a copy of the files on disk (snapshot + journal).
Usage: serve_diff.py N SEED [--crash] [--inproc] [extra engine flags]"""
import hashlib, json, os, random, shutil, signal, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lean_diff  # noqa: E402
ROOT = lean_diff.ROOT
sys.path.insert(0, ROOT)
BASE = ["--answers", "--bounded", "--lean"]


def rhash(r):
    return hashlib.sha256(json.dumps(r).encode()).hexdigest()


def perproc(st, flags, lines):
    p = subprocess.run([sys.executable, "-m", "packetlm.engine", st, *flags, *lines], cwd=ROOT, capture_output=True, text=True)
    if p.returncode:
        return {"error": p.stderr[-300:]}
    return json.loads(p.stdout)["replies"]


TURNS = []  # ref state turn after each call


def ref_run(batches, flags):
    d = tempfile.mkdtemp(); st = os.path.join(d, "s.json"); rep = []
    TURNS.clear()
    for b in batches:
        r = perproc(st, flags, b)
        if isinstance(r, dict):
            return r, None
        rep.append(r)
        TURNS.append(json.loads(open(st, "rb").read())["state"]["turn"])
    raw = open(st, "rb").read() if os.path.exists(st) else None
    shutil.rmtree(d)
    return rep, raw


def strict_eq(a, b, p=""):
    if type(a) is not type(b):
        return f"{p}: type {type(a).__name__} vs {type(b).__name__}"
    if isinstance(a, dict):
        if list(a) != list(b):
            return f"{p}: key order/keys {list(a)[:6]} vs {list(b)[:6]}"
        for k in a:
            e = strict_eq(a[k], b[k], f"{p}/{k}")
            if e:
                return e
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{p}: len {len(a)} vs {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            e = strict_eq(x, y, f"{p}[{i}]")
            if e:
                return e
        return None
    return None if a == b else f"{p}: {a!r} vs {b!r}"


class Srv:
    def __init__(self, every):
        env = dict(os.environ, PACKETLM_SNAPSHOT_EVERY=str(every))
        self.p = subprocess.Popen([sys.executable, "-m", "packetlm.serve"], cwd=ROOT, env=env, stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

    def send(self, **r):
        self.p.stdin.write(json.dumps(r) + "\n"); self.p.stdin.flush()

    def recv(self):
        line = self.p.stdout.readline()
        return json.loads(line) if line else {"error": "died: " + self.p.stderr.read()[-300:]}

    def req(self, **r):
        self.send(**r); return self.recv()

    def kill(self):
        self.p.send_signal(signal.SIGKILL); self.p.wait()


def mini(rng):
    ents = [f"m{i}" for i in range(rng.randint(2, 4))]
    lines = [f"fact {rng.choice(ents)} ra {rng.choice(ents)}" for _ in range(rng.randint(1, 4))]
    lines += [f"example kk: {ents[0]} -> {ents[1]}", f"what is {ents[0]} kk", f"what is {ents[1]} ra"]
    return lines


def recovered_turn(st, flags):
    from packetlm.serve import Server
    from packetlm.engine import parse_cli
    from pathlib import Path
    d2 = tempfile.mkdtemp(); q = os.path.join(d2, "s.json")
    for suf in ("", ".bak", ".journal"):
        if os.path.exists(st + suf):
            shutil.copy2(st + suf, q + suf)
    try:
        o = Server().open_path(Path(q), parse_cli(list(flags))[0], list(flags))
        o.jfh.close()
        return o.state["turn"]
    except Exception as exc:  # noqa: BLE001
        return f"recovery error: {exc}"
    finally:
        shutil.rmtree(d2)


def finalize(st, flags):
    """The durable state is snapshot + journal: recover it into the file (as the next open would)
    before comparing; a journal with records means the file alone is not the state."""
    from packetlm.serve import Server
    from packetlm.engine import parse_cli
    from pathlib import Path
    if os.path.exists(st + ".journal") and len(open(st + ".journal", "rb").read().splitlines()) > 1:
        srv = Server(); srv.cur = srv.open_path(Path(st), parse_cli(list(flags))[0], list(flags)); srv.close()
        return True
    return False


def serve_run(batches, flags, rng, crash, refrep):
    d = tempfile.mkdtemp(); st = os.path.join(d, "s.json")
    every = rng.choice([1, 2, 3, 5, 64]); s = Srv(every)
    rep, ev = [], {"every": every, "kill_between": 0, "kill_mid": 0, "mid_applied": 0, "mid_applied_hash_checked": 0,
                   "new_path_calls": 0, "new_path_diffs": 0, "errors": []}
    for i, b in enumerate(batches):
        if rng.random() < 0.2:  # a B-style task on a brand-new path between two calls
            ev["new_path_calls"] += 1
            lines = mini(rng); q = os.path.join(d, f"new{i}.json")
            got = s.req(op="call", state=q, flags=flags, lines=lines)
            want = perproc(os.path.join(tempfile.mkdtemp(), "x.json"), flags, lines)
            if got.get("replies") != want:
                ev["new_path_diffs"] += 1
        if crash and rng.random() < 0.2:
            s.kill(); s = Srv(every); ev["kill_between"] += 1
        if crash and rng.random() < 0.2:
            ev["kill_mid"] += 1
            jp = st + ".journal"
            j0 = open(jp, "rb").read() if os.path.exists(jp) else b""
            p0 = open(st, "rb").read() if os.path.exists(st) else None
            s.send(op="call", state=st, flags=flags, lines=b)
            time.sleep(rng.choice([0, 0.001, 0.005, 0.02, 0.05]))
            s.kill(); s = Srv(every)
            j1 = open(jp, "rb").read() if os.path.exists(jp) else b""
            recs = []
            for raw in j1.splitlines()[1:]:
                try:
                    recs.append(json.loads(raw))
                except ValueError:
                    pass
            journaled = bool(recs) and recs[-1]["lines"] == b and j1 != j0
            # applied = the state recovered from a copy of the files has the ref turn after this call
            # (the reopen before a call can itself snapshot, so "primary changed" is not evidence)
            t = recovered_turn(st, flags)
            ev.setdefault("trace", []).append((i, "mid", journaled, t, TURNS[i]))
            if isinstance(t, str):
                ev["errors"].append(f"call {i}: {t[:200]}")
            if t == TURNS[i]:
                ev["mid_applied"] += 1
                if journaled:
                    ev["mid_applied_hash_checked"] += 1
                    if recs[-1]["replies_sha256"] != rhash(refrep[i]):
                        ev["errors"].append(f"journaled reply hash differs at call {i}")
                rep.append(refrep[i])  # reply was lost with the process; state carries the call
                continue
        got = s.req(op="call", state=st, flags=flags, lines=b)
        if "error" in got:
            ev["errors"].append(f"call {i}: {got['error'][:200]}")
            rep.append(None); continue
        rep.append(got["replies"])
    c = s.req(op="close"); s.p.stdin.close(); s.p.wait()
    try:
        ev["finalized_from_journal"] = int(finalize(st, flags))
    except Exception as exc:  # noqa: BLE001
        ev["errors"].append(f"final recovery: {exc}")
    raw = open(st, "rb").read() if os.path.exists(st) else None
    shutil.rmtree(d)
    return rep, raw, ev


def inproc_run(batches, flags, rng):
    from packetlm.serve import Server
    from packetlm.engine import parse_cli
    d = tempfile.mkdtemp(); st = os.path.join(d, "s.json")
    srv = Server(rng.choice([1, 2, 3, 64])); rep, errs = [], []
    for i, b in enumerate(batches):
        out = srv.call(st, flags, b); rep.append(out["replies"])
        mem = srv.cur.state
        e = strict_eq(mem, json.loads(json.dumps(mem)))
        if e:
            errs.append(f"call {i} roundtrip: {e}")
        d2 = tempfile.mkdtemp(); q = os.path.join(d2, "s.json")
        for suf in ("", ".bak", ".journal"):
            if os.path.exists(st + suf):
                shutil.copy2(st + suf, q + suf)
        o2 = Server().open_path(__import__("pathlib").Path(q), parse_cli(list(flags))[0], list(flags))
        e = strict_eq(mem, o2.state)
        if e:
            errs.append(f"call {i} fresh-recovery: {e}")
        o2.jfh.close(); shutil.rmtree(d2)
    srv.close()
    raw = open(st, "rb").read()
    shutil.rmtree(d)
    return rep, raw, errs


if __name__ == "__main__":
    a = sys.argv[1:]
    crash, inproc = "--crash" in a, "--inproc" in a
    a = [x for x in a if x not in ("--crash", "--inproc")]
    N, seed, extra = int(a[0]), int(a[1]), a[2:]
    flags = BASE + extra
    rng = random.Random(seed); tot = {"sessions": N, "calls": 0, "diff_replies": 0, "diff_final_bytes": 0, "errors": 0}
    agg = {}; bad = []
    for i in range(N):
        b = lean_diff.session(rng)
        b = [x for x in b if x]
        tot["calls"] += len(b)
        refrep, refraw = ref_run(b, flags)
        if refraw is None:
            bad.append({"session": i, "ref_error": str(refrep)[:200]}); continue
        if inproc:
            rep, raw, errs = inproc_run(b, flags, rng); ev = {"errors": errs}
        else:
            rep, raw, ev = serve_run(b, flags, rng, crash, refrep)
        for k, v in ev.items():
            if isinstance(v, int) and not isinstance(v, bool):
                agg[k] = agg.get(k, 0) + v
        if rep != refrep:
            tot["diff_replies"] += 1
            k = next((j for j, (x, y) in enumerate(zip(refrep, rep)) if x != y), None)
            bad.append({"session": i, "first_diff_call": k, "ref": refrep[k] if k is not None else None,
                        "got": rep[k] if k is not None else None})
        if raw != refraw:
            tot["diff_final_bytes"] += 1
            st_eq = json.loads(raw)["state"] == json.loads(refraw)["state"] if raw and refraw else None
            gs, rs = (json.loads(raw)["state"] if raw else {}), json.loads(refraw)["state"]
            bad.append({"session": i, "final_bytes_differ": True, "state_equal_as_values": st_eq,
                        "turn": [gs.get("turn"), rs["turn"]], "log_len": [len(gs.get("log", [])), len(rs["log"])],
                        "trace": ev.get("trace"), "every": ev.get("every")})
        if ev["errors"]:
            tot["errors"] += 1
            bad.append({"session": i, "errors": ev["errors"][:3]})
    print(json.dumps({"seed": seed, "flags": flags, "crash": crash, "inproc": inproc, **tot, "events": agg}))
    for x in bad[:8]:
        print(json.dumps(x))
