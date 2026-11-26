"""Masks from predictions. Composition with bits.

Not a proven geometric advantage.
Not a general mind.
"""

from __future__ import annotations
import json
from pathlib import Path

def mask_of(ids):
    m = 0
    for i in ids:
        m |= 1 << i
    return m

def bits(m):
    return [i for i in range(m.bit_length()) if m & (1 << i)]

def classify(preds, answer):
    supported, undetermined = [], []
    for i, pred in enumerate(preds):
        if pred is None:
            undetermined.append(i)
        elif pred == answer:
            supported.append(i)
    return supported, undetermined

def filter_mask(live, supported, undetermined):
    return live & (mask_of(supported) | mask_of(undetermined))

def compose(a_rows, b_rows):
    """C_i = OR over k of (A_ik and B_k). Rows are bitsets of targets."""
    out = []
    for a in a_rows:
        acc = 0
        k = 0
        row = a
        while row:
            if row & 1:
                acc |= b_rows[k]
            row >>= 1
            k += 1
        out.append(acc)
    return out

def run() -> dict:
    # predictions for 8 hypotheses on one question
    preds = ["w", None, "w", "no", "w", "no", "w", "no"]
    supported, undetermined = classify(preds, "w")
    live = (1 << 8) - 1
    after = filter_mask(live, supported, undetermined)
    # second question
    preds2 = ["yes", None, "no", "no", "yes", "no", "no", "no"]
    s2, u2 = classify(preds2, "yes")
    after2 = filter_mask(after, s2, u2)
    # composition: in then in
    # nodes: 0 bearing, 1 motor, 2 machine
    inn = [1 << 1, 1 << 2, 0]
    composed = compose(inn, inn)
    walked = 1 << 2  # bearing -> machine
    checks = {
        "from_predictions": bits(after) == [0, 1, 2, 4, 6],
        "narrowed": bits(after2) == [0, 1, 4],
        "undetermined_kept": 1 in bits(after2),
        "composed": composed[0] == walked,
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "after": bits(after),
        "after2": bits(after2),
        "failed": failed,
        "claim": "masks built from predictions; composition matches the walk; not a proven advantage"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/geom_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
