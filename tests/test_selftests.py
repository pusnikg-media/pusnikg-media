"""Die eingebauten Offline-Selbsttests der Action-Skripte laufen mit (Kampagnen-Radar, Trendscout, Stats)."""
import os, subprocess, sys
import pytest
from conftest import ROOT


@pytest.mark.parametrize("script", ["pipeline/kampagnen/kampagnen.py", "pipeline/trendscout/trendscout.py", "pipeline/stats/stats.py"])
def test_selftest(script):
    r = subprocess.run([sys.executable, os.path.join(ROOT, script), "selftest"], capture_output=True, text=True, timeout=120,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    assert r.returncode == 0, r.stdout[-500:] + r.stderr[-800:]


@pytest.mark.parametrize("script", ["pipeline/gh_render.py", "pipeline/hyperframes/render_hf.py", "pipeline/clipfabrik/clipfabrik.py", "pipeline/stats/stats.py",
                                    "pipeline/kampagnen/kampagnen.py", "pipeline/trendscout/trendscout.py", "pipeline/reflab/reflab.py", "pipeline/preflight.py", "pipeline/qa.py"])
def test_compiles(script):
    import ast; ast.parse(open(os.path.join(ROOT, script)).read())
