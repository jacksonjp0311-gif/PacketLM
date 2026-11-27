import subprocess, sys
from pathlib import Path
R = Path(sys.argv[1]); E = R / "packetlm/hdc/engine.py"
M = [("margin_ignored", "                if n >= found + self.margin:\n                    break", "                break"),
     ("ambiguity_ignored", "    if len(groups) > 1:\n            self._cap_provisional(name)\n            return {\"result\": \"ambiguous\"}", "    if False:\n            pass"),
     ("self_not_excluded", "            caps.discard(exclude)\n", "            pass\n"),
     ("omega_empty", "        return X + om, len(X)", "        return X, len(X)"),
     ("several_unchecked", "                    if len(S) < 2:\n                        return False", "                    pass")]
for name, a, b in M:
    src = E.read_text(); assert a in src, name
    E.write_text(src.replace(a, b, 1))
    try:
        p = subprocess.run([sys.executable, "-m", "packetlm.hdc.test_hdc"], cwd=R, capture_output=True, text=True, timeout=120)
        killed = p.returncode != 0
    except subprocess.TimeoutExpired:
        killed = True
    finally:
        E.write_text(src)
    print(name, "killed" if killed else "SURVIVED", flush=True)
