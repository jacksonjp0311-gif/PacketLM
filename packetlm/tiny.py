"""Tiny next-token model.

Pure Python. No torch. Trains on the runner.
Token embeddings, one attention layer, next-token head.
Trained by prediction error on the corpus windows.
Generates by argmax. Receipt records loss and a sample.
This is a real next-token model, still tiny, still a proxy at this scale.
"""

from __future__ import annotations
import json
import math
import random
from pathlib import Path
from .train import load_corpus, window_stories

DIM = 16
HEADS = 1
STEPS = 40

def tokenize(text: str) -> list[str]:
    return [t for t in text.lower().split() if t]

def build_vocab(windows: list[str]) -> dict[str, int]:
    vocab = {"<pad>": 0, "<unk>": 1}
    for w in windows:
        for t in tokenize(w):
            if t not in vocab:
                vocab[t] = len(vocab)
    return vocab

def ids(tokens: list[str], vocab: dict[str, int]) -> list[int]:
    return [vocab.get(t, 1) for t in tokens]

def zeros(n: int, m: int) -> list[list[float]]:
    return [[0.0] * m for _ in range(n)]

def rand_mat(n: int, m: int, scale: float = 0.1) -> list[list[float]]:
    return [[(random.random() - 0.5) * scale for _ in range(m)] for _ in range(n)]

def dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))

def softmax(xs: list[float]) -> list[float]:
    m = max(xs) if xs else 0.0
    ex = [math.exp(x - m) for x in xs]
    s = sum(ex) or 1.0
    return [e / s for e in ex]

class TinyLM:
    def __init__(self, vocab_size: int):
        self.V = vocab_size
        self.E = rand_mat(vocab_size, DIM, 0.2)
        self.Wq = rand_mat(DIM, DIM, 0.1)
        self.Wk = rand_mat(DIM, DIM, 0.1)
        self.Wv = rand_mat(DIM, DIM, 0.1)
        self.Wo = rand_mat(DIM, vocab_size, 0.1)

    def embed(self, token_ids: list[int]) -> list[list[float]]:
        return [self.E[i][:] for i in token_ids]

    def attn(self, x: list[list[float]]) -> list[list[float]]:
        # single-head scaled dot-product, causal
        n = len(x)
        q = [[dot(row, self.Wq[j]) for j in range(DIM)] for row in x]
        k = [[dot(row, self.Wk[j]) for j in range(DIM)] for row in x]
        v = [[dot(row, self.Wv[j]) for j in range(DIM)] for row in x]
        out = zeros(n, DIM)
        scale = math.sqrt(DIM)
        for i in range(n):
            scores = [dot(q[i], k[j]) / scale for j in range(i + 1)]
            weights = softmax(scores)
            for j, w in enumerate(weights):
                for d in range(DIM):
                    out[i][d] += w * v[j][d]
        return out

    def logits(self, hidden: list[float]) -> list[float]:
        return [dot(hidden, self.Wo[j]) for j in range(self.V)]

    def step(self, token_ids: list[int], target: int, lr: float = 0.05) -> float:
        if not token_ids:
            return 0.0
        x = self.embed(token_ids)
        h = self.attn(x)
        last = h[-1]
        logits = self.logits(last)
        probs = softmax(logits)
        loss = -math.log(max(probs[target], 1e-9))
        # gradient on output and embedding of last token
        for j in range(self.V):
            g = probs[j] - (1.0 if j == target else 0.0)
            for d in range(DIM):
                self.Wo[j][d] -= lr * g * last[d]
        # nudge last token embedding toward the target direction
        last_id = token_ids[-1]
        for d in range(DIM):
            self.E[last_id][d] -= lr * 0.01 * (probs[target] - 1.0) * self.Wo[target][d]
        return loss

    def predict(self, token_ids: list[int]) -> int:
        if not token_ids:
            return 1
        x = self.embed(token_ids)
        h = self.attn(x)
        logits = self.logits(h[-1])
        return max(range(self.V), key=lambda j: logits[j])

    def generate(self, prompt_ids: list[int], steps: int = 8) -> list[int]:
        out = prompt_ids[:]
        for _ in range(steps):
            nxt = self.predict(out[-8:])
            out.append(nxt)
        return out[len(prompt_ids):]

def run() -> dict:
    random.seed(0)
    raw = load_corpus()
    windows = window_stories(raw)
    vocab = build_vocab(windows)
    inv = {i: t for t, i in vocab.items()}
    model = TinyLM(len(vocab))
    # training pairs: context -> next token
    pairs = []
    for w in windows:
        toks = tokenize(w)
        for i in range(1, len(toks)):
            pairs.append((ids(toks[max(0, i - 6):i], vocab), vocab.get(toks[i], 1)))
    if not pairs:
        pairs = [([1], 1)]
    losses = []
    for step in range(STEPS):
        ctx, tgt = random.choice(pairs)
        losses.append(model.step(ctx, tgt))
    # sample generation
    prompt = tokenize(windows[0])[:4] if windows else ["one"]
    gen_ids = model.generate(ids(prompt, vocab), steps=8)
    gen = [inv.get(i, "<unk>") for i in gen_ids]
    mean_loss = sum(losses) / max(len(losses), 1)
    receipt = {
        "vocab": len(vocab),
        "pairs": len(pairs),
        "steps": STEPS,
        "mean_loss": round(mean_loss, 4),
        "final_loss": round(losses[-1], 4) if losses else None,
        "prompt": prompt,
        "generated": gen,
        "claim": "tiny next-token model with embeddings and one attention layer; trained by prediction error on the runner; still tiny, not a general language model"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/tiny_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return receipt

if __name__ == "__main__":
    run()
