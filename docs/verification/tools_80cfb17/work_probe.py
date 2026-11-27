"""Verifier (verify-80cfb17): where does k's task time grow from 16k to 64k when function calls stay ~flat?
For one seed and N, the g59_scale run_one protocol (padding, uncharged snapshot), then the 10-task workload
(1) timed plain, (2) with per-query counters on Memo.recall_partitioned / recall_candidates (sizes of small_part,
pair hits, H, candidates), (3) under cProfile (tottime per function). Usage: work_probe.py SEED N [ARM]"""
import cProfile, io, json, os, pstats, random, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]; sys.path[:0] = [str(ROOT), str(ROOT / "benchmarks")]
from packetlm import serve, engine as E
import g57_scale, g59_scale as H
seed, n = int(sys.argv[1]), int(sys.argv[2]); arm = sys.argv[3] if len(sys.argv) > 3 else "k"
flags = H.FLAGS + H.ARMS[arm]
facts, caps = g57_scale.padding(random.Random(seed * 100003 + n), n)
work = g57_scale.workload(random.Random(seed), H.TASKS)
C = {"q": 0, "small_part": 0, "hit": 0, "H": 0, "cand": 0, "g57b_q": 0, "g57b_cand": 0, "t": 0.0}
orig_p, orig_c = E.Memo.recall_partitioned, E.Memo.recall_candidates
def rp(self, s, r, qi, k):
    t0 = time.process_time(); out = orig_p(self, s, r, qi, k); C["t"] += time.process_time() - t0
    C["q"] += 1; C["small_part"] += len(self.ix["small_part"]); C["cand"] += len(out); return out
def rc(self, s, r):
    t0 = time.process_time(); out = orig_c(self, s, r); C["t"] += time.process_time() - t0
    C["g57b_q"] += 1; C["g57b_cand"] += len(out); return out
with tempfile.TemporaryDirectory() as d:
    p = Path(d) / "s.json"; srv = serve.Server()
    for i in range(0, len(facts), 2000): srv.call(p, flags, facts[i:i + 2000])
    for ex in caps: srv.call(p, flags, ex)
    srv._snapshot(srv.cur)
    ix = srv.cur.memo.ix
    sizes = {"facts": len(srv.cur.state["facts"]), "small_part": len(ix.get("small_part", [])), "small": len(ix["small"]),
             "pair_keys": len(ix.get("pairs", {})), "codes": len(ix["codes"])}
    def run(label):
        t0 = time.process_time()
        for _, lines in work: srv.call(p, flags, lines)
        return time.process_time() - t0
    t_plain = run("plain")  # workload once (warms per-query memo; later passes hit the recall memo)
    E.Memo.recall_partitioned, E.Memo.recall_candidates = rp, rc
    # fresh recall memos so the counted pass does the queries again
    srv.cur.memo.recall.clear(); t_count = run("count")
    E.Memo.recall_partitioned, E.Memo.recall_candidates = orig_p, orig_c
    srv.cur.memo.recall.clear(); pr = cProfile.Profile(); pr.enable(); run("prof"); pr.disable()
    s = io.StringIO(); pstats.Stats(pr, stream=s).sort_stats("tottime").print_stats(14)
    srv.close()
print(json.dumps({"seed": seed, "n": n, "arm": arm, "sizes": sizes, "workload_cpu_s_first_pass": round(t_plain, 4),
                  "workload_cpu_s_counted_pass": round(t_count, 4), "recall_fn_cpu_s": round(C["t"], 4), "counters": C}))
print("\n".join(s.getvalue().splitlines()[:40]))
