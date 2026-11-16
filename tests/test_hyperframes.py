"""HyperFrames/Short-Pipeline im Trockenlauf: Preflight + build_cd.py bauen die Komposition, ohne Browser/Render/TTS."""
import json, os, subprocess, sys
import pytest
from conftest import ROOT

PRE = os.path.join(ROOT, "pipeline", "preflight.py")
BUILD = os.path.join(ROOT, "pipeline", "hyperframes", "build_cd.py")
LINES = ["Two days left until GTA 6 launches.", "Pre-load is live and it is huge.", "Follow for day one."]


def ff(*a):
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", *a], capture_output=True, text=True); assert r.returncode == 0, r.stderr


@pytest.fixture()
def proj(tmp_path):
    vo = tmp_path / "vo"; vo.mkdir(); (tmp_path / "clips").mkdir(); (tmp_path / "hf_proj").mkdir()
    timing, words = [], []
    for i, t in enumerate(LINES):
        wav = vo / f"line{i}.wav"; ff("-f", "lavfi", "-i", "sine=frequency=300:duration=6.5", str(wav))
        timing.append({"file": str(wav), "text": t, "dur": 6.5})
        n = len(t.split()); words.append([{"w": w, "s": round(0.2 + k * 6.0 / n, 2), "e": round(0.2 + (k + 0.8) * 6.0 / n, 2)} for k, w in enumerate(t.split())])
    json.dump(timing, open(vo / "timing.json", "w")); json.dump(words, open(vo / "words.json", "w"))
    shots = []
    for i in range(3):
        line = []
        for k in range(3):
            c = tmp_path / "clips" / f"c{i}{k}.mp4"; ff("-f", "lavfi", "-i", "testsrc=size=320x568:rate=25:duration=4", "-pix_fmt", "yuv420p", str(c))
            line.append({"file": f"clips/c{i}{k}.mp4", "start": 0})
        shots.append(line)
    job = {"vo_dir": "vo", "shots": shots, "day": 2, "hook_mid": "DAYS LEFT", "badge": "GTA 6 • DAY 2", "out": "out.mp4", "punch": ["pre-load"]}
    jp = tmp_path / "job.json"; json.dump(job, open(jp, "w"))
    return tmp_path, job, str(jp)


def run(cmd): return subprocess.run([sys.executable, *cmd], capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))


def test_preflight_ok(proj):
    _, _, jp = proj
    r = run([PRE, jp]); assert r.returncode == 0 and "PREFLIGHT_OK 3 lines, 9 shots" in r.stdout, r.stdout + r.stderr


def test_preflight_catches_short_clip_and_wrong_count(proj):
    tmp, job, jp = proj
    job["shots"] = job["shots"][:2]; json.dump(job, open(jp, "w"))
    r = run([PRE, jp]); assert r.returncode == 1 and "PREFLIGHT_FAIL" in r.stdout and "shot lists" in r.stdout
    job["shots"].append([{"file": "clips/c00.mp4", "start": 3.9}]); json.dump(job, open(jp, "w"))   # Clip zu kurz für start + Slot
    r = run([PRE, jp]); assert r.returncode == 1 and "needs start" in r.stdout


def test_build_cd_writes_composition(proj):
    tmp, _, jp = proj
    r = run([BUILD, jp, str(tmp / "hf_proj")]); assert r.returncode == 0, r.stderr
    html = open(tmp / "hf_proj" / "index.html").read()
    assert "TOTAL" in r.stdout and html.count('<video ') == 9 and "GTA 6" in html and "%BODY%" not in html and "%JS%" not in html


def test_build_cd_fails_loudly_on_stale_words(proj):
    tmp, _, jp = proj
    w = json.load(open(tmp / "vo" / "words.json")); w[0] = w[0][:-1]; json.dump(w, open(tmp / "vo" / "words.json", "w"))
    r = run([BUILD, jp, str(tmp / "hf_proj")]); assert r.returncode != 0 and "BUILD FAIL" in (r.stderr + r.stdout)
