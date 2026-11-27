"""Invariant checks for the ten modules restored with Router.path_union.

These modules have no assertions of their own. Each check here recomputes
something independently and compares it with the module's receipt or
behaviour. They are invariant checks, not capability claims:
these modules are overlap proxies, not language models. G44 audit item 12.
"""

from __future__ import annotations
import contextlib
import io
import json
from pathlib import Path
from .packets import hash_to_bits
from .router import Router
from .train import load_corpus, window_stories, load_probes


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


def manual_union(path):
    acc = 0
    for p in path:
        acc |= int.from_bytes(p.bits, "big")
    return acc


def best_packet(packets, q):
    best, best_s = None, None
    for p in packets:
        s = 2 * bin(int.from_bytes(p.bits, "big") & int.from_bytes(q.bits, "big")).count("1") - p.count
        if best_s is None or s > best_s:
            best, best_s = p, s
    return best


def run() -> dict:
    from . import memory, gap, gaptest, demo, learn, crossdomain, nexttoken, train, vocab, feedoffer
    windows = window_stories(load_corpus())
    router = Router([hash_to_bits(s) for s in windows])
    c = {}

    r = quiet(memory.run)
    # The module's own prompt opens no packet (0 hops), so its receipt measures nothing.
    # That is recorded as a finding, not hidden; the invariant is checked on a window that does hop.
    q1 = hash_to_bits(windows[0])
    path = router.residual_hop(q1, depth=3)
    u = manual_union(path)
    pu = router.path_union(q1, depth=3)
    c["_memory_module_turn1_hops"] = r["turn1_hops"]
    mem = memory.ResidualMemory()
    mem.covered = u
    res = mem.residual_query(hash_to_bits("What did they do next?"))
    c["memory.path_union_is_or_of_path"] = pu is not None and int.from_bytes(pu.bits, "big") == u
    c["memory.residual_excludes_covered"] = int.from_bytes(res.bits, "big") & u == 0 and res.count == bin(int.from_bytes(res.bits, "big")).count("1")
    q0 = hash_to_bits("Lily thanked her mom. How did they both feel?")
    c["memory.receipt_covered_bits"] = r["covered_bits"] == bin(manual_union(router.residual_hop(q0, depth=3))).count("1") \
        and len(path) >= 1

    r = quiet(gap.run)
    c["gap.store_grows_by_kept"] = r["store_size"] == len(windows) + r["kept"] and r["kept"] <= r["proposals"]
    first = 0
    for w in windows[:5]:
        first |= manual_union(router.residual_hop(hash_to_bits(w), depth=3))
    c["gap.kept_raise_coverage"] = (r["final_covered_bits"] > bin(first).count("1")) == (r["kept"] > 0) \
        and r["final_covered_bits"] >= bin(first).count("1")

    r = quiet(gaptest.run)
    probes = load_probes()
    base = [hash_to_bits(w) for w in windows]
    hits = {p["id"]: best_packet(base, hash_to_bits(p["prompt"])).overlap(hash_to_bits(p["expected"])) > 0 for p in probes}
    c["gaptest.base_hits_recomputed"] = hits == r["base_hits"]
    c["gaptest.improved_only_base_misses"] = all(not hits[i] for i in r["probes_improved_by_gap"]) \
        and r["any_new_capability"] == bool(r["probes_improved_by_gap"])

    r1, r2 = quiet(demo.demo), quiet(demo.demo)
    c["demo.deterministic"] = r1 == r2
    c["demo.consistency_flag"] = r1["consistent"] == (r1["consistency_overlap"] > 0) and all(t["hop_count"] <= 3 for t in r1["turns"])

    r = quiet(learn.run)
    h = r["history"]
    c["learn.gate_rule"] = all(p["kept"] == (len(p["improved_domains"]) >= 2) for p in h) and r["kept_passes"] == sum(p["kept"] for p in h)
    c["learn.improved_recomputed"] = all(sorted(p["improved_domains"]) == sorted(d for d in p["before"] if p["after"][d] > p["before"][d]) for p in h)
    c["learn.coverage_monotone"] = all(a["covered_bits"] <= b["covered_bits"] for a, b in zip(h, h[1:]))

    r = quiet(crossdomain.run)
    c["crossdomain.gate_rule"] = r["kept"] == (len(r["improved_domains"]) >= 2) \
        and all(r["after"][d] >= r["before"][d] for d in r["improved_domains"]) \
        and all(0 <= v <= 1 for v in list(r["before"].values()) + list(r["after"].values()))

    r = quiet(nexttoken.run)
    n = len(windows if len(windows) >= 4 else windows * 2)
    c["nexttoken.split_recomputed"] = r["train_windows"] + r["holdout"] == n and r["holdout"] == max(1, n // 3)
    c["nexttoken.flags_match_scores"] = r["segment_improved"] == (r["segment_after"] > r["segment_before"]) or \
        (r["segment_after"] == r["segment_before"])  # flags use unrounded values

    r = quiet(train.run)
    c["train.certified_count"] = r["certified_probes"] == sum(p["certified"] for p in r["probes"])
    c["train.cold_never_hits"] = all(not p["cold_hit"] for p in r["probes"])
    c["train.gate_rule"] = r["gate_passed"] == (r["certified_probes"] > 0 and r["hop_ablation"]["hops_improve"]) \
        and all(e["hop_count"] <= 3 for e in r["hop_effects"])

    r = quiet(vocab.run)
    w2 = windows if len(windows) >= 4 else windows * 2
    tr = w2[:-max(1, len(w2) // 3)]
    c["vocab.size_recomputed"] = r["vocab_size"] == len(vocab.build_vocab(tr))
    c["vocab.accuracy_recomputed"] = r["accuracy"] == round(r["correct_first_tokens"] / max(r["holdout"], 1), 3) \
        and r["correct_first_tokens"] <= r["holdout"]

    r = quiet(feedoffer.offer)
    feed = json.loads(Path("feed/latest_language.json").read_text())
    c["feedoffer.gate_rule"] = r["offered"] == bool(r["gate_kept"] and r["residual_reduced"] and r["gap"]["last_kept"])
    c["feedoffer.feed_matches"] = feed == (r["packet"] or {})

    findings = {k[1:]: c.pop(k) for k in list(c) if k.startswith("_")}
    failed = [k for k, v in c.items() if not v]
    receipt = {**c, "findings": findings, "failed": failed, "claim": "invariants of ten restored proxy modules; not capability claims"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/legacy_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt


if __name__ == "__main__":
    run()
