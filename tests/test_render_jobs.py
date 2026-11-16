"""pipeline/gh_jobs.py = Auftragsliste der Render-Farm (Risiko 1/3: stilles Aufgeben nach 3 Fehlversuchen, Drive-Scrape)."""
import json, os, runpy
import pytest
from conftest import ROOT

SCRIPT = os.path.join(ROOT, "pipeline", "gh_jobs.py")
JOB = {"name": "pusnikg-2026-12-01-t", "date": "2026-12-01", "day": 1, "script": ["a b c", "d e f", "g h i", "j k l"],
       "shots": [[{"url": "https://x/1.mp4", "start": 0}]] * 4, "music": {"url": "https://x/m.m4a"}, "tiktok_lines": [0, 2]}


def pending(tmp, capsys, monkeypatch):
    monkeypatch.chdir(tmp); monkeypatch.delenv("DRIVE_FOLDER", raising=False)
    runpy.run_path(SCRIPT, run_name="__main__")
    out = capsys.readouterr().out.strip().splitlines()[-1]
    return sorted(os.path.basename(p)[:-5] for p in json.loads(out))


def repo(tmp, results=None):
    (tmp / "jobs").mkdir(); (tmp / "shorts").mkdir(); json.dump(JOB, open(tmp / "jobs" / (JOB["name"] + ".json"), "w"))
    for n, r in (results or {}).items(): json.dump(r, open(tmp / "shorts" / (n + ".json"), "w"))


def test_new_job_and_tiktok_cut_are_pending(tmp_path, capsys, monkeypatch):
    repo(tmp_path); assert pending(tmp_path, capsys, monkeypatch) == [JOB["name"], JOB["name"] + "-tt"]


def test_done_job_not_pending(tmp_path, capsys, monkeypatch):
    repo(tmp_path, {JOB["name"]: {"ok": True}, JOB["name"] + "-tt": {"ok": True}}); assert pending(tmp_path, capsys, monkeypatch) == []


def test_failed_job_retried_until_three_attempts(tmp_path, capsys, monkeypatch):
    repo(tmp_path, {JOB["name"]: {"ok": False, "attempts": 2}, JOB["name"] + "-tt": {"ok": True}})
    assert pending(tmp_path, capsys, monkeypatch) == [JOB["name"]]


def test_gave_up_after_three_attempts_is_silent(tmp_path, capsys, monkeypatch):
    """Dokumentiert das stille Aufgeben - deshalb meldet der Wächter 'ok:false' in shorts/*.json."""
    repo(tmp_path, {JOB["name"]: {"ok": False, "attempts": 3}, JOB["name"] + "-tt": {"ok": True}})
    assert pending(tmp_path, capsys, monkeypatch) == []


def test_drive_fixture(tmp_path, capsys, monkeypatch):
    repo(tmp_path, {JOB["name"]: {"ok": True}, JOB["name"] + "-tt": {"ok": True}})
    monkeypatch.setenv("DRIVE_FOLDER", "F"); fid = "A" * 33
    page = (f'<a href="https://drive.google.com/file/d/{fid}/view?usp=drive_web"><div class="flip-entry-title">job-drv.json</div></a>').encode()
    body = json.dumps(dict(JOB, name="drv-test", script=JOB["script"], tiktok_lines=[])).encode()
    class R:
        def __init__(s, b): s.b = b
        def read(s): return s.b
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=0: R(page if "embeddedfolderview" in req.full_url else body))
    monkeypatch.chdir(tmp_path); runpy.run_path(SCRIPT, run_name="__main__")
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1]); assert [os.path.basename(p) for p in out] == ["drv-test.json"]
