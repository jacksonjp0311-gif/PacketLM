import json, sys, tarfile, io
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "benchmarks"), str(ROOT)]
from g59_scale import boot, alpha
rec = json.load(open(ROOT / "docs/evidence/g60h/scale/g60h_reg_scale_receipt.json"))
tf = tarfile.open(ROOT / "docs/evidence/g60h/scale/runs.tgz")
R = {}
for m in tf.getmembers():
    if m.isfile():
        r = json.load(tf.extractfile(m)); R[(r["seed"], r["n"], r["arm"])] = r
seeds, sizes = rec["seeds"], rec["sizes"]
ok = True
for a in ("hC", "hP"):
    S = {"mean_task_cpu_ms": {str(n): round(1000 * sum(R[(s, n, a)]["mean_task_cpu_s"] for s in seeds) / len(seeds), 4) for n in sizes}}
    for n1, n2 in [(1000, 16000), (16000, 32000), (16000, 64000), (32000, 64000)]:
        for key, f in [("", "mean_task_cpu_s"), ("_charged_fixed", "charged_fixed_cpu_s"), ("_charged_prop", "charged_prop_cpu_s"), ("_work", "work_calls"), ("_snapshot", "snapshot_cpu_s")]:
            S[f"alpha{key}_{n1}_{n2}"] = alpha([R[(s, n2, a)][f] / R[(s, n1, a)][f] for s in seeds], n1, n2)
    S["decode_errors"] = sum(R[(s, n, a)]["hdc_counters"]["decode_errors"] for s in seeds for n in sizes)
    S["decodes"] = sum(R[(s, n, a)]["hdc_counters"]["decodes"] for s in seeds for n in sizes)
    S["workload_identical_across_N"] = all(len({R[(s, n, a)]["reply_stream_sha256"] for n in sizes}) == 1 for s in seeds)
    for k, v in S.items():
        same = json.dumps(v, default=str) == json.dumps(rec["summary"][a][k], default=str)
        ok &= same
        if not same or k in ("alpha_16000_64000", "alpha_charged_prop_16000_64000", "decodes", "decode_errors"):
            print(a, k, "EQUAL" if same else "DIFF", v, rec["summary"][a][k])
    # work calls identical at every N?
    print(a, "work_calls per N identical:", all(len({R[(s, n, a)]["work_calls"] for n in sizes}) == 1 for s in seeds),
          "padding caps decoded in window?", sorted({R[(s, n, a)]["hdc_counters"]["decodes"] for s in seeds for n in sizes})[:8])
print("ALL EQUAL", ok)
