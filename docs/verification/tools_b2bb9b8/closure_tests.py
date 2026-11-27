import sys, json, tempfile, os
sys.path.insert(0, "/workspace/pl-verify")
from packetlm.engine import Engine

BASE = ["fact a p b", "fact b p c", "fact c k top", "fact b k mid", "fact x p y", "fact y k top", "fact z p a"]

def run(lines, programs=True):
    fd, path = tempfile.mkstemp(suffix=".json"); os.close(fd); os.unlink(path)
    e = Engine(path, programs=programs, answers=True)
    out = [e.turn(l) for l in lines]
    cap = e.state["capabilities"].get("k1")
    ver = cap["versions"][cap["current"] - 1] if cap and cap.get("current") else None
    return {"replies": out[len(BASE):], "complete": {k: v["closure"] for k, v in e.state.get("complete", {}).items()},
            "log": e.state.get("complete_log", []), "status": ver["status"] if ver else None, "seq": ver["seq"] if ver else None}

T = BASE + ["example k1: a -> c", "complete a", "example k1: x -> y", "complete x"]
cases = {
 "baseline (honest, complete a, x)": T,
 "add fact inside closure (c p d)": T + ["fact c p d"],
 "add fact at X itself (a q w)": T + ["fact a q w"],
 "add incoming edge into closure (w p a; subject outside)": T + ["fact w p a"],
 "add fact unrelated (u p v)": T + ["fact u p v"],
 "retract fact inside closure (b k mid)": T + ["retract b k mid"],
 "correct fact inside closure (b p e)": T + ["correct b p e"],
 "re-tell existing fact (a p b)": T + ["fact a p b"],
 "complete stated before facts; later fact in closure": ["fact a p b", "example k1: a -> b", "complete a", "fact b p c"],
 "correct example value->!none (P1 via correction)": BASE + ["example k1: a -> c", "correct example k1: a -> !none", "what is x k1"],
}
for mode in (True, False):
    print("=== programs" if mode else "=== base")
    for k, ls in cases.items():
        r = run(ls, mode)
        print(json.dumps({"case": k, **r})[:700])
