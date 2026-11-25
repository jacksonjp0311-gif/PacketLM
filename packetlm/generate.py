"""Multi-token generation with learned update.

Chains predictions for several steps.
After scoring the continuation, updates the prompt-to-token table
so correct next tokens from the target are preferred on the next pass.
Measures overlap before and after the update.
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

def score(windows, table) -> float:
    scores = []
    for w in windows[:8]:
        prompt, target = split_window(w)
        if not target:
            continue
        gen = generate(prompt, table, steps=6)
        target_toks = target.split()
        hit = sum(1 for t in target_toks if t in gen)
        scores.append(hit / max(len(target_toks), 1))
    return sum(scores) / max(len(scores), 1)

def learn_from_score(table: dict[str, str], windows: list[str]) -> int:
    """On a miss, write the correct next token into the table for that prompt."""
    updates = 0
    for w in windows:
        prompt, target = split_window(w)
        if not prompt or not target:
            continue
        correct = target.split()[0]
        pred = nearest(prompt, table)
        if pred != correct:
            table[prompt] = correct
            updates += 1
    return updates

def run() -> dict:
    raw = load_corpus()
    windows = window_stories(raw)
    if len(windows) < 4:
        windows = windows * 2
    cut = max(1, len(windows) // 3)
    train = windows[:-cut]
    holdout = windows[-cut:]
    table = build_table(train)
    before = score(holdout, table)
    updates = learn_from_score(table, train)
    after = score(holdout, table)
    samples = []
    for w in holdout[:4]:
        prompt, target = split_window(w)
        if not target:
            continue
        gen = generate(prompt, table, steps=6)
        samples.append({
            "prompt": prompt[:60],
            "generated": gen,
            "target": target.split()[:6]
        })
    receipt = {
        "train": len(train),
        "holdout": len(holdout),
        "overlap_before": round(before, 3),
        "overlap_after": round(after, 3),
        "improved": after > before,
        "updates": updates,
        "samples": samples,
        "claim": "continuation scored; table updated from misses; still a proxy"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/generate_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
