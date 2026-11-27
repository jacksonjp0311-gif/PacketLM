"""G55 soundness probe (docs/G55.md): the verifier's honest-teacher adversarial search
(benchmarks/verifier_tools_050bebd/adversarial.py, copied unchanged from verify-050bebd) run with the
engine's closed-world guard budget set to N for every Engine it creates.
Run: python3 benchmarks/g55_adversarial.py BUDGET CASES SEED MODE"""
import os
import runpy
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import packetlm.engine as E  # noqa: E402

budget = int(sys.argv[1])
_init = E.Engine.__init__


def _init_budget(self, *a, **k):
    k.setdefault("closed_guards", budget)
    _init(self, *a, **k)


E.Engine.__init__ = _init_budget
tool = os.path.join(ROOT, "benchmarks", "verifier_tools_050bebd", "adversarial.py")
sys.argv = [tool] + sys.argv[2:]
runpy.run_path(tool, run_name="__main__")
