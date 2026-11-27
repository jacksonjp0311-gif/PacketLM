"""Verifier (verify-80cfb17): direct property test of the §2a bound, independent of sessions. Random q (|q| 24..32 on
4096 positions) and three codes X0..X2 (<= 16 bits each) drawn mostly from q's bits so that packets are near the
pass/decode boundary. For every packet p = X0^X1^X2 with |p| >= SMALL_PART, 2|p&q| > |p| and |p^q| <= 16 (the only
triples that can add a name), check: (a) two codes have |X&q| >= k = part_threshold(q); (b) each such code has an
indexed pair (_code_pairs of its ascending bits) made of two of q's bits. Counts tight cases (second overlap == k)."""
import random, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from packetlm import engine as E
rng = random.Random(int(sys.argv[1]) if len(sys.argv) > 1 else 1); N = int(sys.argv[2]) if len(sys.argv) > 2 else 300000
part = E.Memo.part_threshold
bad = tight = eligible = 0; kmin = 99
for it in range(N):
    qbits = rng.sample(range(4096), rng.randint(24, 32)); q = sum(1 << b for b in qbits)
    k = part(None, q)
    if k is None: continue
    c = rng.sample(range(4096), rng.randint(0, 16)); cx = sum(1 << b for b in c)
    if (q ^ cx).bit_count() < E.SMALL_PART or (q ^ cx).bit_count() > 48: continue
    pbits = [b for b in qbits + c if ((q ^ cx) >> b) & 1]
    rng.shuffle(pbits); codes = [[], [], []]
    w = [rng.random() + 0.01 for _ in range(3)]
    for b in pbits:
        opts = [i for i in range(3) if len(codes[i]) < 16]
        codes[rng.choices(opts, [w[i] for i in opts])[0]].append(b)
    for _ in range(rng.randint(0, 8)):  # cancelling pairs: a bit in two codes vanishes from p
        opts = [i for i in range(3) if len(codes[i]) < 16]
        if len(opts) < 2: break
        a, b2 = rng.sample(opts, 2); bit = rng.choice(qbits) if rng.random() < .7 else rng.randrange(4096)
        if bit in codes[a] or bit in codes[b2] or (q ^ cx) >> bit & 1: continue
        codes[a].append(bit); codes[b2].append(bit)
    xs = [sum(1 << b for b in c) for c in codes]; p = xs[0] ^ xs[1] ^ xs[2]
    if p.bit_count() < E.SMALL_PART or not (2 * (p & q).bit_count() > p.bit_count()) or (p ^ q).bit_count() > 16: continue
    eligible += 1
    ov = sorted(((x & q).bit_count(), i) for i, x in enumerate(xs))[::-1]
    if ov[1][0] < k: bad += 1; print("BOUND FAIL", k, ov); continue
    tight += ov[1][0] == k; kmin = min(kmin, k)
    for o, i in ov[:2]:
        prs = set(E._code_pairs(sorted(codes[i])))
        if not any(a * 4096 + b in prs for a in qbits for b in qbits if a < b): bad += 1; print("PAIR FAIL", codes[i], o, k)
print({"samples": N, "eligible": eligible, "tight": tight, "violations": bad, "kmin": kmin})
