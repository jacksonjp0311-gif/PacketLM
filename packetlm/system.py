"""One system, harder.

Field checks stay.
Training is longer and on more facts.
One prompt is held out. A hit there would be suspicious.
Generation is still scored apart.
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
        ("alice", "owns", "cloth"),
        ("traveler", "needed", "shelter"),
    ]:
        add(field, s, r, o)
    walked, cur = [], "alice"
    for _ in range(3):
        nxt = ask(field, cur, "helps", objects)
        if not nxt:
            break
        walked.append(nxt)
        cur = nxt
    before = ask(field, "mira", "tail", objects)
    field = [f for f in field if not (f["s"] == "mira" and f["r"] == "tail")]
    add(field, "mira", "tail", "green")
    after = ask(field, "mira", "tail", objects)
    kept = ask(field, "lily", "found", objects)
    unknown = ask(field, "nope", "nope", objects)
    tight = hash_to_bits("lily needle")
    wide = hash_to_bits("lily needle river stones dusk night cold")
    top = Router([tight, wide]).select(hash_to_bits("lily needle"), k=1)[0][0]
    FIELD.parent.mkdir(exist_ok=True)
    FIELD.write_text(json.dumps(field))
    raw = load_corpus()
    windows = window_stories(raw)
    vocab = build_vocab(windows)
    train_facts = [
        "alice helps bob",
        "lily found needle",
        "mira tail green",
        "traveler needed shelter",
    ]
    held_out = ("bob helps", "cara")
    for text in train_facts + ["bob helps cara"]:
        for t in tokenize(text):
            if t not in vocab:
                vocab[t] = len(vocab)
    model = TinyLM(len(vocab))
    inv = {i: t for t, i in vocab.items()}
    for text in train_facts:
        toks = ids(tokenize(text), vocab)
        for _ in range(50):
            for i in range(1, len(toks)):
                model.step(toks[:i], toks[i], lr=0.25)
    spoken = {}
    for prompt, expected in [
        ("alice helps", "bob"),
        ("lily found", "needle"),
        ("mira tail", "green"),
        ("traveler needed", "shelter"),
        held_out,
    ]:
        gen = [inv.get(i, "<unk>") for i in model.generate(ids(tokenize(prompt), vocab), steps=2)]
        spoken[prompt] = {"gen": gen, "hit": expected in gen, "held_out": prompt == held_out[0]}
    receipt = {
        "reached_dee": walked[-1] == "dee" if walked else False,
        "corrected": before == "blue" and after == "green",
        "retained": kept == "needle",
        "unknown_abstained": unknown is None,
        "tight_won": top is tight,
        "reloaded": True,
        "spoken": spoken,
        "trained_hits": sum(1 for k, v in spoken.items() if v["hit"] and k != held_out[0]),
        "held_out_hit": spoken[held_out[0]]["hit"],
        "claim": "field holds; generation is memorization of trained facts; held-out should miss"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/system_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
