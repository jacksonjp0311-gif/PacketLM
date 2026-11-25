"""Language-phase training stub.

Focus: TinyStories-scale next-token on packet overlap.
Windows stories into short segments and measures whether residual hops change retrieval.
Evaluates sealed probes with twin measurement (cold vs field).
Hard gate: rejects the run if no probes certify OR hops do not improve on requires_hop probes (M3 demand).
Hop-depth ablation: path union must cover more of the expected than single-select.
Produces a simple loss curve artifact for the runner.
"""

from __future__ import annotations
import json
import random
import sys
from pathlib import Path
from .packets import hash_to_bits, Packet
from .router import Router

def load_corpus() -> list[str]:
    slice_path = Path("data/tinystories_slice.txt")
    if slice_path.exists():
        text = slice_path.read_text()
        stories = [s.strip() for s in text.split("\n\n") if s.strip()]
        if stories:
            return stories
    return toy_corpus()

def window_stories(stories: list[str], max_len: int = 120) -> list[str]:
    windows = []
    for story in stories:
        words = story.split()
        for i in range(0, len(words), max_len // 8):
            chunk = " ".join(words[i:i + max_len // 4])
            if len(chunk) > 20:
                windows.append(chunk)
    return windows or stories

def toy_corpus(n: int = 32) -> list[str]:
    templates = [
        "the {a} {v} the {b}",
        "a {a} and a {b} {v} together",
        "once there was a {a} who {v} a {b}",
    ]
    nouns = ["cat", "dog", "bird", "child", "tree"]
    verbs = ["saw", "chased", "found", "helped", "watched"]
    stories = []
    for _ in range(n):
        t = random.choice(templates)
        stories.append(t.format(
            a=random.choice(nouns),
            b=random.choice(nouns),
            v=random.choice(verbs)
        ))
    return stories

def train_step(router: Router, text: str) -> float:
    q = hash_to_bits(text)
    scored = router.select(q, k=1)
    if not scored:
        return 1.0
    _, score = scored[0]
    return max(0.0, 1.0 - score / 100.0)

def hop_effect(router: Router, text: str) -> dict:
    q = hash_to_bits(text)
    single = router.select(q, k=1)
    hops = router.residual_hop(q, depth=3)
    return {
        "single_score": single[0][1] if single else 0,
        "hop_count": len(hops),
        "hop_changed": len(hops) > 1
    }

def load_probes() -> list[dict]:
    path = Path("data/probes.json")
    if not path.exists():
        return []
    return json.loads(path.read_text())

def evaluate_probe(router: Router, probe: dict) -> dict:
    """Twin measurement: field vs cold (empty router)."""
    q = hash_to_bits(probe["prompt"])
    exp = hash_to_bits(probe["expected"])
    field_scored = router.select(q, k=1)
    field_hit = False
    field_overlap = 0
    if field_scored:
        winner = field_scored[0][0]
        field_overlap = winner.overlap(exp)
        field_hit = field_overlap > 0
    cold = Router([])
    cold_scored = cold.select(q, k=1)
    cold_hit = False
    if cold_scored:
        cold_hit = cold_scored[0][0].overlap(exp) > 0
    certified = field_hit and (not cold_hit) if probe.get("cold_must_fail") else field_hit
    return {
        "id": probe["id"],
        "phase": probe["phase"],
        "field_hit": field_hit,
        "cold_hit": cold_hit,
        "field_overlap": field_overlap,
        "certified": certified,
        "requires_hop": probe.get("requires_hop", False)
    }

def hop_ablation(router: Router, probes: list[dict]) -> dict:
    """Path union must cover more of the expected than single-select."""
    hop_probes = [p for p in probes if p.get("requires_hop")] or probes
    single_total = 0
    hop_total = 0
    improved = 0
    for probe in hop_probes:
        q = hash_to_bits(probe["prompt"])
        exp = hash_to_bits(probe["expected"])
        single = router.select(q, k=1)
        s_ov = single[0][0].overlap(exp) if single else 0
        union = router.path_union(q, depth=3)
        h_ov = union.overlap(exp) if union else 0
        single_total += s_ov
        hop_total += h_ov
        if h_ov > s_ov:
            improved += 1
    n = len(hop_probes) or 1
    return {
        "single_overlap_sum": single_total,
        "hop_overlap_sum": hop_total,
        "probes_improved": improved,
        "delta": (hop_total - single_total) / max(single_total, 1),
        "hops_improve": improved > 0,
        "probes_scored": n
    }

def run(seed: int = 0, steps: int = 50) -> dict:
    random.seed(seed)
    raw = load_corpus()
    corpus = window_stories(raw)
    packets = [hash_to_bits(s, seed=seed) for s in corpus]
    router = Router(packets)
    losses = []
    effects = []
    for i in range(steps):
        text = random.choice(corpus)
        loss = train_step(router, text)
        losses.append(loss)
        if i % 10 == 0:
            effects.append(hop_effect(router, text))
    probes = load_probes()
    probe_results = [evaluate_probe(router, p) for p in probes]
    certified_count = sum(1 for r in probe_results if r["certified"])
    ablation = hop_ablation(router, probes)
    gate_passed = certified_count > 0 and ablation["hops_improve"]
    m3_ready = ablation["hops_improve"]
    status = "M3 gate passed" if gate_passed else "M2/M3 gate rejected"
    receipt = {
        "seed": seed,
        "steps": steps,
        "stories_raw": len(raw),
        "windows": len(corpus),
        "final_loss": losses[-1] if losses else None,
        "mean_loss": sum(losses) / len(losses) if losses else None,
        "hop_effects": effects,
        "probes": probe_results,
        "certified_probes": certified_count,
        "hop_ablation": ablation,
        "gate_passed": gate_passed,
        "m3_ready": m3_ready,
        "phase": "language",
        "corpus": "tinystories_slice" if Path("data/tinystories_slice.txt").exists() else "toy",
        "claim": "overlap proxy + hop count + twin probe eval with hard gate demanding higher residual coverage on requires_hop probes; not a real language model yet",
        "status": status
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if not gate_passed:
        print("GATE REJECTED: need certified probes AND higher residual coverage", file=sys.stderr)
        sys.exit(1)
    return receipt

if __name__ == "__main__":
    run()
