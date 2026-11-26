"""One system. One run.

Field: bind, unbind, multi-object, walk, abstain, correct, retain, persist.
Train: the tiny model on the same facts, scored apart from retrieval.
Not a general mind.
"""

from __future__ import annotations
import json
import hashlib
import random
from pathlib import Path
from .packets import Packet, BITS, hash_to_bits
from .router import Router
from .tiny import TinyLM, tokenize, build_vocab, ids
from .train import load_corpus, window_stories

FIELD = Path("data/system_field.json")

def bits_for(token: str, role: int, nbits: int = 16) -> int:
    h = hashlib.sha256(f"{role}:{token}".encode()).digest()
    acc = 0
    for i in range(nbits):
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
    random.seed(43)
    objects = ["bob", "cara", "dee", "blue", "green", "needle", "cloth"]
    field = []
    add(field, "alice", "helps", "bob")
    add(field, "bob", "helps", "cara")
    add(field, "cara", "helps", "dee")
    add(field, "mira", "tail", "blue")
    add(field, "lily", "found", "needle")
    add(field, "alice", "owns", "cloth")
    add(field, "alice", "owns", "needle")
    # walk
    walked, cur = [], "alice"
    for _ in range(3):
        nxt = ask(field, cur, "helps", objects)
        if not nxt:
            break
        walked.append(nxt)
        cur = nxt
    # multi-object
    owned = []
    q = partial("alice", "owns")
    for item in field:
        pkt = Packet(bits=bytes.fromhex(item["bits"]), count=item["count"])
        if pkt.score(q) > 0:
            left = pack(int.from_bytes(pkt.bits, "big") ^ int.from_bytes(q.bits, "big"))
            name = decode(left, objects)
            if name:
                owned.append(name)
    # correct and retain
    before = ask(field, "mira", "tail", objects)
    field = [f for f in field if not (f["s"] == "mira" and f["r"] == "tail")]
    add(field, "mira", "tail", "green")
    after = ask(field, "mira", "tail", objects)
    kept = ask(field, "lily", "found", objects)
    # abstain
    unknown = ask(field, "nope", "nope", objects)
    # score tightness
    tight, wide = hash_to_bits("lily needle"), hash_to_bits("lily needle river stones dusk")
    top = Router([tight, wide]).select(hash_to_bits("lily needle"), k=1)[0][0]
    # persist
    FIELD.parent.mkdir(exist_ok=True)
    FIELD.write_text(json.dumps(field))
    reloaded = len(json.loads(FIELD.read_text())) == len(field)
    # train on the facts, score generation apart
    raw = load_corpus()
    windows = window_stories(raw)
    vocab = build_vocab(windows)
    facts_text = [
        "alice helps bob",
        "bob helps cara",
        "mira tail green",
        "lily found needle",
    ]
    for text in facts_text:
        for t in tokenize(text):
            if t not in vocab:
                vocab[t] = len(vocab)
    model = TinyLM(len(vocab))
    inv = {i: t for t, i in vocab.items()}
    for text in facts_text:
        toks = ids(tokenize(text), vocab)
        for _ in range(30):
            for i in range(1, len(toks)):
                model.step(toks[:i], toks[i], lr=0.2)
    spoken = {}
    for prompt, expected in [("alice helps", "bob"), ("lily found", "needle"), ("mira tail", "green")]:
        gen = [inv.get(i, "<unk>") for i in model.generate(ids(tokenize(prompt), vocab), steps=2)]
        spoken[prompt] = {"gen": gen, "hit": expected in gen}
    receipt = {
        "walked": walked,
        "reached_dee": walked[-1] == "dee" if walked else False,
        "owned": sorted(set(owned)),
        "corrected": before == "blue" and after == "green",
        "retained": kept == "needle",
        "unknown_abstained": unknown is None,
        "tight_won": top is tight,
        "reloaded": reloaded,
        "spoken": spoken,
        "generated_hits": sum(1 for v in spoken.values() if v["hit"]),
        "claim": "one system: field and training; generation scored apart; not a mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/system_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
