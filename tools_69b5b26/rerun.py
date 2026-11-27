"""Rerun the registered gate protocol (g60h.main) with a chosen engine entry point: registered serve or cc_serve."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "benchmarks"), str(ROOT)]
import g56, g60h
mode = sys.argv[1]
if mode == "cc":
    TOOL = str(ROOT / "tools_69b5b26/cc_serve.py")

    class CServer(g56.Server):
        def __init__(self):
            import subprocess as sp
            self.p = sp.Popen([sys.executable, TOOL], cwd=ROOT, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE, text=True, bufsize=1)
    g60h.HServer = CServer
sys.exit(g60h.main(sys.argv[2:]))
