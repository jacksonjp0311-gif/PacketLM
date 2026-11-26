"""One system.

The field is written, then read back, then queried from the reloaded bytes.
A failed check exits nonzero.
Generation is scored apart and does not gate the field.
Not a general mind.
"""

from __future__ import annotations
import json
import hashlib
from pathlib import Path
from .packets import Packet, BITS, hash_to_bits
from .router import Router
from .tiny import TinyLM, tokenize, build_vocab, ids
from .train import load_corpus, window_stories

FIELD = Path("data/system_field.json")

def bits_for(token: str, role: int) -> int:
    h = hashlib.sha256(f"{role}:{token}".encode()).digest()
    acc = 0
    for i in range(16):
        acc |= 1 << (int.from_bytes(h[i * 2:(i * 2) + 2], "big") % BITS)
    return acc

def pack(n: int) -> Packet:
    return Packet(bits=n.to_bytes(BITS // 8, "big"), count=bin(n).count("1"))

def bind(s, r, o) -> Packet:
    return pack(bits_for(s, 0) ^ bits_for(r, 1) ^ bits_for(o, 2))

def partial(s, r) -> Packet:
    return pack(bits_for(s, 0) ^ bits_for(r, 1))

def decode(left: Packet, objects: list[str]) -> str | None:
    for name in objects:
        if left.bits == pack(bits_for(name, 2)).bits:
            return name
    return None

def ask(field, s, r, objects) -> str | None:
    q = partial(s, r)
    best, best_s = None, 0
    for item in field:
        pkt = Packet(bits=bytes.fromhex(item["bits"]), count=item["count"])
        sc = pkt.score(q)
        if sc > best_s:
            best, best_s = pkt, sc
    if not best:
        return None
    left = pack(int.from_bytes(best.bits, "big") ^ int.from_bytes(q.bits, "big"))
    return decode(left, objects)

def add(field, s, r, o):
    pkt = bind(s, r, o)
    field.append({"s": s, "r": r, "o": o, "bits": pkt.bits.hex(), "count": pkt.count})

def run() -> dict:
    objects = ["bob", "cara", "dee", "blue", "green", "needle", "cloth", "shelter"]
    field = []
    for s, r, o in [
        ("alice", "helps", "bob"),
        ("bob", "helps", "cara"),
        ("cara", "helps", "dee"),
        ("mira", "tail", "blue"),
        ("lily", "found", "needle"),
        ("traveler", "needed", "shelter"),
    ]:
        add(field, s, r, o)
    before = ask(field, "mira", "tail", objects)
    field = [f for f in field if not (f["s"] == "mira" and f["r"] == "tail")]
    add(field, "mira", "tail", "green")
    FIELD.parent.mkdir(exist_ok=True)
    FIELD.write_text(json.dumps(field))
    loaded = json.loads(FIELD.read_text())
    walked, cur = [], "alice"
    for _ in range(3):
        nxt = ask(loaded, cur, "helps", objects)
        if not nxt:
            break
        walked.append(nxt)
        cur = nxt
    after = ask(loaded, "mira", "tail", objects)
    kept = ask(loaded, "lily", "found", objects)
    unknown = ask(loaded, "nope", "nope", objects)
    tight = hash_to_bits("lily needle")
    wide = hash_to_bits("lily needle river stones dusk night cold")
    top = Router([tight, wide]).select(hash_to_bits("lily needle"), k=1)[0][0]
    checks = {
        "reached_dee": walked[-1] == "dee" if walked else False,
        "corrected": before == "blue" and after == "green",
        "retained": kept == "needle",
        "unknown_abstained": unknown is None,
        "tight_won": top is tight,
        "reloaded": len(loaded) == len(field) and after == "green",
    }
    raw = load_corpus()
    windows = window_stories(raw)
    vocab = build_vocab(windows)
    train_facts = ["alice helps bob", "lily found needle", "mira tail green"]
    for text in train_facts:
        for t in tokenize(text):
            if t not in vocab:
                vocab[t] = len(vocab)
    model = TinyLM(len(vocab))
    inv = {i: t for t, i in vocab.items()}
    for text in train_facts:
        toks = ids(tokenize(text), vocab)
        for _ in range(40):
            for i in range(1, len(toks)):
                model.step(toks[:i], toks[i], lr=0.25)
    spoken = {}
    for prompt, expected in [("alice helps", "bob"), ("lily found", "needle"), ("mira tail", "green")]:
        gen = [inv.get(i, "<unk>") for i in model.generate(ids(tokenize(prompt), vocab), steps=2)]
        spoken[prompt] = {"gen": gen, "hit": expected in gen}
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "walked": walked,
        "spoken": spoken,
        "generated_hits": sum(1 for v in spoken.values() if v["hit"]),
        "failed": failed,
        "claim": "field queried after reload; run fails if a field check fails; not a mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/system_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
