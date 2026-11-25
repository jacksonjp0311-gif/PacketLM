"""Multi-token generation.

Chains nearest-prompt predictions for several steps.
Scores how many of the target tokens appear in the generated continuation.
This is a continuation, not a single first-token hit.
"""

from __future__ import annotations
import json
from pathlib import Path
from .train import load_corpus, window_stories
from .nexttoken import split_window
from .direct import tokens, nearest

def build_table(windows: list[str]) -> dict[str, str]:
    table = {}
    for w in windows:
        prompt, target = split_window(w)
        if not prompt or not target:
            continue
        # map prompt to the next token in the target
        nxt = target.split()[0] if target.split() else ""
        if nxt:
            table[prompt] = nxt
    return table

def generate(prompt: str, table: dict[str, str], steps: int = 6) -> list[str]:
    out = []
    current = prompt
    for _ in range(steps):
        tok = nearest(current, table)
        if not tok:
            break
        out.append(tok)
        current = (current + " " + tok).strip()
    return out

def run() -> dict:
    raw = load_corpus()
    windows = window_stories(raw)
    if len(windows) < 4:
        windows = windows * 2
    cut = max(1, len(windows) // 3)
    train = windows[:-cut]
    holdout = windows[-cut:]
    table = build_table(train)

    scores = []
    samples = []
    for w in holdout[:8]:
        prompt, target = split_window(w)
        if not target:
            continue
        gen = generate(prompt, table, steps=6)
        target_toks = target.split()
        hit = sum(1 for t in target_toks if t in gen)
        scores.append(hit / max(len(target_toks), 1))
        samples.append({
            "prompt": prompt[:60],
            "generated": gen,
            "target": target_toks[:6],
            "token_overlap": round(hit / max(len(target_toks), 1), 3)
        })

    mean = sum(scores) / max(len(scores), 1)
    receipt = {
        "train": len(train),
        "holdout_scored": len(scores),
        "mean_token_overlap": round(mean, 3),
        "samples": samples[:4],
        "claim": "multi-token continuation by chained nearest-prompt; scored against target tokens; still a proxy"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/generate_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
