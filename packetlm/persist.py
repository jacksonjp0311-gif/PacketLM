"""Weight persistence.

Loads embeddings and output weights if a file exists.
Saves them after training so the next run continues from here.
"""

from __future__ import annotations
import json
from pathlib import Path
from .tiny import TinyLM, DIM

PATH = Path("data/weights.json")

def load_into(model: TinyLM) -> bool:
    if not PATH.exists():
        return False
    data = json.loads(PATH.read_text())
    if data.get("dim") != DIM or data.get("vocab") != model.V:
        return False
    model.E = data["E"]
    model.Wo = data["Wo"]
    return True

def save_from(model: TinyLM) -> None:
    PATH.parent.mkdir(exist_ok=True)
    PATH.write_text(json.dumps({
        "dim": DIM,
        "vocab": model.V,
        "E": model.E,
        "Wo": model.Wo,
    }))
