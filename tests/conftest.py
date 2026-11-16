"""Gemeinsame Hilfen. Alle Tests laufen offline und ohne Credits (nur ffmpeg + Python)."""
import importlib.util, json, os, subprocess, sys
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.dont_write_bytecode = True  # im Repo liegen .pyc-Dateien im Git - keine neuen erzeugen


def load(relpath, name):
    """Modul per Pfad laden (die Skripte liegen nicht in Paketen)."""
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, relpath))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def cf():
    return load("pipeline/clipfabrik/clipfabrik.py", "clipfabrik_t")


@pytest.fixture(scope="session")
def src_clip(tmp_path_factory):
    """6-s-Testquelle 1280x720, 25 fps, Ton mit Lautstärke-Stößen. Kein Netz, kein Download."""
    p = str(tmp_path_factory.mktemp("src") / "src.mp4")
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=25:duration=6",
                        "-f", "lavfi", "-i", "sine=frequency=440:duration=6", "-c:v", "libx264", "-preset", "ultrafast",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", p], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return p


def ffprobe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height:format=duration",
                        "-of", "json", path], capture_output=True, text=True)
    d = json.loads(r.stdout)
    v = next(s for s in d["streams"] if s["codec_type"] == "video")
    return {"w": v["width"], "h": v["height"], "dur": float(d["format"]["duration"]),
            "audio": any(s["codec_type"] == "audio" for s in d["streams"]), "vcodec": v["codec_name"]}
