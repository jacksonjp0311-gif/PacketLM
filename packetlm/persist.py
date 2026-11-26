"""Weight persistence. No import of tiny, to avoid a circular import."""

from __future__ import annotations
import json
from pathlib import Path

PATH = Path("data/weights.json")

def load_into(model, dim: int) -> bool:
    if not PATH.exists():
        return False
    data = json.loads(PATH.read_text())
    if data.get("dim") != dim or data.get("vocab") != model.V:
        return False
    model.E = data["E"]
    model.Wo = data["Wo"]
    return True

def save_from(model, dim: int) -> None:
    PATH.parent.mkdir(exist_ok=True)
    PATH.write_text(json.dumps({
        "dim": dim,
        "vocab": model.V,
        "E": model.E,
        "Wo": model.Wo,
    }))
