"""Verifier (verify-33565b0; adapted from tools_8994490/corrupt_probe.py): engines XJ (--incremental, 33565b0) and
XR (--routed); index kinds now also on XR; G58 memo kinds (rvx relation map, capability index offered
list, seeds index) on XR only; sessions from routed_diff (with capability churn). Original: inject corruption between calls under the long-lived protocol and measure what the
G57b change-scoped validation + K-period guard does with it, against a never-corrupted twin.

For each session (incr_diff.session, no drops/crashes) and each corruption kind, a corrupted server
(XJ: --indexed --incremental, registered K = 64, snapshot every 64 unless --snap) and, for state
corruptions, the G57 engine (XI: every mutating call fully validated) run beside a clean twin of
the same flags. The corruption is injected into the in-memory state (or XJ's persistent index)
after call `at`. Reported per kind: detected (an error raised by a call, or by close), latency in
mutating / read-only calls served after injection, whether any reply differed from the clean twin
before detection ("served wrong"), and the outcome of recovery (the next call reopens from snapshot +
journal): recovered state == clean twin, or the reopen fails (e.g. journal replay diverged).
Usage: corrupt_probe.py N SEED [--K 64] [--snap 64]"""
import argparse, json, os, random, shutil, sys, tempfile
from collections import Counter, defaultdict
from pathlib import Path
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from routed_diff import session, churn, BASE  # noqa: E402
from packetlm.serve import Server  # noqa: E402

FJ = BASE + ["--indexed", "--incremental"]
FI = BASE + ["--indexed"]
FR = BASE + ["--indexed", "--incremental", "--routed"]


def pick_fact(st, rng):
    fs = st["facts"]
    return rng.choice(fs) if fs else None


def inj_state(kind, srv, rng):
    st = srv.cur.state
    f = pick_fact(st, rng)
    if f is None:
        return False
    if kind == "S1_supports_empty":
        f["supports"] = []
    elif kind == "S2_dangling_premise":
        f["supports"].append({"kind": "derived", "source": "x", "turn": 1, "premises": ["no such fact"], "program": None})
    elif kind == "S3_id_mismatch":
        f["id"] = f["id"] + "x"
    elif kind == "S5_inplace_valid_change":  # a valid but different fact, written in place (index now stale)
        o2 = f["o"] + "q"
        f["o"], f["id"] = o2, f"{f['s']} {f['r']} {o2}"
    elif kind == "S6_duplicate_append":
        st["facts"].append(json.loads(json.dumps(f)))
    elif kind == "S7_cap_current_bad":
        caps = st["capabilities"]
        if not caps:
            return False
        c = caps[rng.choice(sorted(caps))]
        c["current"] = len(c["versions"]) + 5
    elif kind == "S8_bits_key":
        f["bits"] = "00"
    else:
        raise ValueError(kind)
    return True


def inj_index(kind, srv, rng):
    o = srv.cur
    if o.memo is None or not o.memo.ix_valid(o.state) or not o.state["facts"]:
        return False
    ix = o.memo.ix
    f = rng.choice(o.state["facts"])
    t = (f["s"], f["r"], f["o"])
    if kind == "I1_by_sr_drop":
        ix["by_sr"][(t[0], t[1])] = [x for x in ix["by_sr"].get((t[0], t[1]), []) if x is not f]
    elif kind == "I2_told_rel_off":
        ix["told_rel"][t[1]] += 1
    elif kind == "I3_small_and_codes_drop":  # the triple can no longer be a recall candidate
        ix["small"] = [x for x in ix["small"] if x != t]
        for b, v in ix["codebits"].items():
            ix["codebits"][b] = [c for c in v if c not in ((0, t[0]), (1, t[1]), (2, t[2]))]
    elif kind == "I4_ref_core_drop":
        ix["ref"].get(t[1], {}).get(t[0], set()).discard(t[2])
    elif kind == "I5_by_rel_drop":
        ix["by_rel"][t[1]] = [x for x in ix["by_rel"].get(t[1], []) if x != t]
    else:
        raise ValueError(kind)
    return True


def inj_g58(kind, srv, rng):
    m = srv.cur.memo
    if m is None:
        return False
    if kind == "G1_rvx_rel_cleared":
        if not m.rvx or not m.rvx["rel"]:
            return False
        m.rvx["rel"] = {}
    elif kind == "G2_cx_offered_drop":
        if not m.cx or not m.cx["order"]:
            return False
        i = rng.randrange(len(m.cx["order"])); del m.cx["order"][i], m.cx["order_p"][i]
    elif kind == "G3_sx_by_ent_cleared":
        if not m.sx or not m.sx["by_ent"]:
            return False
        m.sx["by_ent"] = {}
    elif kind == "G4_rvx_subj_cleared":
        if not m.rvx or not m.rvx["subj"]:
            return False
        m.rvx["subj"] = {}
    else:
        raise ValueError(kind)
    return True


G58_KINDS = ["G1_rvx_rel_cleared", "G2_cx_offered_drop", "G3_sx_by_ent_cleared", "G4_rvx_subj_cleared"]
STATE_KINDS = ["S1_supports_empty", "S2_dangling_premise", "S3_id_mismatch", "S5_inplace_valid_change",
               "S6_duplicate_append", "S7_cap_current_bad", "S8_bits_key"]
INDEX_KINDS = ["I1_by_sr_drop", "I2_told_rel_off", "I3_small_and_codes_drop", "I4_ref_core_drop", "I5_by_rel_drop"]


def trial(calls, at, kind, flags, K, snap, rng):
    d = Path(tempfile.mkdtemp(dir="/tmp"))
    bad, good = Server(snap, full_every=K), Server(snap, full_every=K)
    pb, pg = d / "b" / "s.json", d / "g" / "s.json"
    res = {"kind": kind, "engine": "XR" if "--routed" in flags else "XJ" if "--incremental" in flags else "XI"}
    try:
        for j, c in enumerate(calls):
            rg = good.call(pg, flags, c)
            if j == at:
                bad.call(pb, flags, c)
                if not {"I": inj_index, "S": inj_state, "G": inj_g58}[kind[0]](kind, bad, rng):
                    res["skipped"] = True
                    return res
                res.update(mut_after=0, ro_after=0, served_wrong=0)
                ixobj = bad.cur.memo.ix if bad.cur.memo is not None else None
                continue
            if "mut_after" not in res:
                bad.call(pb, flags, c)
                continue
            try:
                rb = bad.handle({"op": "call", "state": str(pb), "flags": flags, "lines": c})
            except Exception as exc:  # noqa: BLE001
                res["detected"] = f"call: {type(exc).__name__}: {str(exc)[:90]}"
                # recovery: the next call reopens from snapshot + journal
                try:
                    rr = bad.call(pb, flags, c)  # the client retries the refused call after the reopen
                    res["retry_reply_equal_clean"] = rr["replies"] == rg["replies"]
                    res["recovered_equal_clean"] = json.dumps(bad.cur.state) == json.dumps(good.cur.state)
                except Exception as exc2:  # noqa: BLE001
                    res["recovery"] = f"reopen failed: {type(exc2).__name__}: {str(exc2)[:120]}"
                return res
            res["ro_after" if rb.get("readonly") else "mut_after"] += 1
            if rb["replies"] != rg["replies"]:
                res["served_wrong"] += 1
        if bad.cur is not None and bad.cur.memo is not None and kind[0] == "I" and bad.cur.memo.ix is not ixobj:
            res["healed_by_rebuild"] = True
        elif "--incremental" in flags and bad.cur is not None and bad.cur.memo.ix is not ixobj:
            res["index_rebuilt_after_injection"] = True
        try:
            bad.close()
            res["detected"] = "never (close passed)"
            res["final_state_equal_clean"] = (pb.read_bytes() == (good.close() or pg.read_bytes()))
        except Exception as exc:  # noqa: BLE001
            res["detected"] = f"close: {type(exc).__name__}: {str(exc)[:90]}"
        return res
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("N", type=int); ap.add_argument("seed", type=int)
    ap.add_argument("--K", type=int, default=64); ap.add_argument("--snap", type=int, default=64)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    agg = defaultdict(Counter); examples = []
    for i in range(a.N):
        calls = [c for c in churn(random.Random(a.seed * 31 + i), session(rng, 0.0), 0) if c[0] != "__drop__"]
        at = rng.randrange(3, max(4, len(calls) - 6))
        for kind in STATE_KINDS + INDEX_KINDS + G58_KINDS:
            engines = {"S": [FJ, FR], "I": [FJ, FR], "G": [FR]}[kind[0]]
            for fl in engines:
                r = trial(calls, at, kind, fl, a.K, a.snap, random.Random(a.seed * 1000 + i))
                key = f"{r['engine']}:{kind}"
                g = agg[key]
                if r.get("skipped"):
                    g["skipped"] += 1; continue
                g["trials"] += 1
                det = r.get("detected", "?")
                g["det_" + det.split(":")[0].split(" ")[0]] += 1
                if det.startswith("call"):
                    g["latency_mut_sum"] += r["mut_after"] + 1
                    g["latency_mut_max"] = max(g["latency_mut_max"], r["mut_after"] + 1)
                    g["ro_served_before_detect"] += r["ro_after"]
                    if r.get("recovered_equal_clean"):
                        g["recovered_equal_clean"] += 1
                    elif "recovery" in r:
                        g["recovery_failed"] += 1
                    else:
                        g["recovered_but_differs"] += 1
                if r.get("served_wrong"):
                    g["trials_with_wrong_replies_before_detection"] += 1
                if r.get("healed_by_rebuild"):
                    g["index_healed_by_rebuild_before_end"] += 1
                if r.get("index_rebuilt_after_injection"):
                    g["index_rebuilt_after_injection"] += 1
                if r.get("retry_reply_equal_clean") is False:
                    g["retry_reply_differs"] += 1
                if det.startswith("never") and not r.get("final_state_equal_clean"):
                    g["undetected_final_differs"] += 1
                if (r.get("served_wrong") or "recovery" in r or det.startswith("never")) and len(examples) < 400:
                    examples.append({"session": i, **r})
    print(json.dumps({"seed": a.seed, "K": a.K, "snap": a.snap, "sessions": a.N, "by_kind": {k: dict(v) for k, v in sorted(agg.items())}}, indent=1))
    for e in examples:
        print(json.dumps(e))


if __name__ == "__main__":
    main()
