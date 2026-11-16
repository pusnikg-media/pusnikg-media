"""Clipfabrik: jedes Layout rendert 1080x1920 mit der richtigen Dauer und Ton (Risiko: stiller Fallback/Mass-Rerender)."""
import json, os, pytest
from conftest import ffprobe

WORDS = [{"w": "Hello", "s": 0.6, "e": 1.0}, {"w": "this", "s": 1.1, "e": 1.4}, {"w": "is", "s": 1.5, "e": 1.7}, {"w": "a", "s": 1.8, "e": 1.9},
         {"w": "test.", "s": 2.0, "e": 2.6}]
CAPTION = "Lacy couldn't believe Rug is too SCARED to drive his Rolls-Royce in the RAIN... 😭"


def render(cf, src, tmp, **clip):
    out = str(tmp / "out"); os.makedirs(out, exist_ok=True)
    job = {"name": "t", "min_len": 3, "clips": [dict({"id": "x", "a": 0.5, "b": 4.5, "title": "TEST TITLE"}, **clip)]}
    p = cf.probe(src)
    assert cf.check_clips(job, p["dur"]) == []
    r = cf.render_clip(job, job["clips"][0], src, p, WORDS, out, str(tmp))
    return r, os.path.join(out, r["file"])


@pytest.mark.parametrize("layout", ["native", "full", "framed"])
def test_layout_renders(cf, src_clip, tmp_path, layout):
    extra = {"caption": CAPTION} if layout == "native" else {}
    r, f = render(cf, src_clip, tmp_path, layout=layout, **extra)
    q = ffprobe(f)
    assert (q["w"], q["h"]) == (1080, 1920) and q["vcodec"] == "h264"
    assert abs(q["dur"] - 4.0) < 0.5, q                  # Dauer = b - a
    assert q["audio"], "Originalton fehlt"
    assert r["layout"] == layout and r["ok"] and os.path.exists(os.path.join(os.path.dirname(f), "qa", "t_x.jpg"))


def test_split_layout_with_explicit_facecam(cf, src_clip, tmp_path):
    """Mit festem facecam-Rechteck (kein OpenCV nötig). 'auto' fällt auf synthetischem Material still auf native zurück."""
    r, f = render(cf, src_clip, tmp_path, layout="split", facecam=[0.70, 0.05, 0.28, 0.28], caption=CAPTION)
    q = ffprobe(f)
    assert r["layout"] == "split", "split fiel still auf native zurück"
    assert (q["w"], q["h"]) == (1080, 1920) and abs(q["dur"] - 4.0) < 0.5 and q["audio"]


def test_hook_teaser_adds_duration(cf, src_clip, tmp_path):
    r, f = render(cf, src_clip, tmp_path, layout="native", caption=CAPTION, hook=[3.0, 4.0])
    assert abs(ffprobe(f)["dur"] - 5.0) < 0.6 and r["hook"] == [3.0, 4.0]   # Teaser (1 s) + Clip (4 s)


def test_layouts_differ_visually(cf, src_clip, tmp_path):
    """Schutz gegen 'alle Layouts sehen gleich aus': native und full müssen sich im Bild unterscheiden (Mittel- vs. Randpixel)."""
    import subprocess
    def px(f, x, y):
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", "1", "-i", f, "-vf", f"crop=4:4:{x}:{y},format=gray", "-frames:v", "1", "-f", "rawvideo", "-"],
                           capture_output=True); return r.stdout[0]
    d1, d2 = tmp_path / "a", tmp_path / "b"; d1.mkdir(); d2.mkdir()
    _, fn = render(cf, src_clip, d1, layout="native", caption=CAPTION)
    _, ff = render(cf, src_clip, d2, layout="full")
    assert [px(fn, 540, 100), px(fn, 540, 960)] != [px(ff, 540, 100), px(ff, 540, 960)]


def test_check_clips_rejects_bad_jobs(cf):
    bad = {"min_len": 10, "clips": [{"id": "a", "a": 0, "b": 5, "title": "x"},          # zu kurz
                                    {"id": "a", "a": 0, "b": 20, "title": "x"},          # doppelte ID
                                    {"id": "b", "a": 50, "b": 70, "title": "x"},         # hinter dem Ende
                                    {"id": "c", "a": 0, "b": 20},                        # kein Titel/Caption
                                    {"id": "d", "a": 0, "b": 20, "title": "x", "hook": [1, 9]}]}  # Hook > 5 s
    errs = cf.check_clips(bad, 30)
    assert len(errs) == 5, errs


def test_job_sig_is_stable(cf):
    """Goldene Signatur: ändert sie sich, rendert die Clipfabrik ALLE Aufträge neu (Massen-Rerender, Laufzeit/Repo-Größe)."""
    job = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures", "clipjob_golden.json")))
    assert cf.job_sig(job) == "dd0c61a82b21", "job_sig geändert -> alle clipjobs würden neu gerendert (gewollt? dann Golden-Wert anpassen)"


def test_pending_skips_done_and_gave_up(cf, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("DRIVE_FOLDER", raising=False)
    root = tmp_path / "repo"; (root / "clipjobs").mkdir(parents=True)
    jobs = {n: {"name": n, "source": "https://example.com/" + n + ".mp4", "clips": []} for n in ("new", "done", "dead", "retry")}
    for n, j in jobs.items(): json.dump(j, open(root / "clipjobs" / f"{n}.json", "w"))
    for n, res in {"done": {"ok": True, "attempts": 1}, "dead": {"ok": False, "attempts": 3}, "retry": {"ok": False, "attempts": 2}}.items():
        os.makedirs(root / "clips" / n); json.dump(dict(res, sig=cf.job_sig(jobs[n])), open(root / "clips" / n / "result.json", "w"))
    cf.pending(str(root), str(tmp_path / "in"))
    got = sorted(os.path.basename(p)[:-5] for p in json.loads(capsys.readouterr().out.strip().splitlines()[-1]))
    assert got == ["new", "retry"]   # 'dead' (3 Fehlversuche) wird still übersprungen - der Wächter muss das melden


DRIVE_PAGE = ('<div class="flip-entry"><a href="https://drive.google.com/file/d/%s/view?usp=drive_web" target="_blank">'
              '<div class="flip-entry-info"><div class="flip-entry-title">%s</div></div></a></div>')


def test_drive_folder_parser_fixture(cf, tmp_path, monkeypatch, capsys):
    """Risiko 3: Drive-Ordner-Scrape per Regex. Mit gespeicherter Beispielseite: findet clipjob-*.json, ignoriert andere."""
    monkeypatch.setenv("DRIVE_FOLDER", "FOLDER")
    fid = "A" * 33
    page = (DRIVE_PAGE % (fid, "clipjob-drv1.json") + DRIVE_PAGE % ("B" * 33, "notes.txt")).encode()
    body = json.dumps({"name": "drv1", "source": "https://example.com/x.mp4"}).encode()

    class R:
        def __init__(s, b): s.b = b
        def read(s): return s.b
    def fake(req, timeout=0):
        u = req.full_url if hasattr(req, "full_url") else req
        return R(page if "embeddedfolderview" in u else body)
    import urllib.request; monkeypatch.setattr(urllib.request, "urlopen", fake)
    root = tmp_path / "repo"; (root / "clipjobs").mkdir(parents=True)
    cf.pending(str(root), str(tmp_path / "in"))
    out = capsys.readouterr().out.strip().splitlines()[-1]
    assert [os.path.basename(p) for p in json.loads(out)] == ["drv1.json"]


# --- Review 16.11.2026 (Fable-Nacht): Feinfehler an Wort-/Schnittgrenzen ------------------------------------------------------
def test_snap_to_words_never_cuts_inside_a_word(cf):
    W = [{"w": "car.", "s": 210.0, "e": 210.44}, {"w": "next", "s": 211.0, "e": 211.3}]
    a, b, tail = cf.snap_to_words(200.0, 210.40, 300.0, W)            # end lands inside "car." (0.04 s before its end)
    assert b == pytest.approx(210.56) and tail == pytest.approx(0.12)
    a, b, tail = cf.snap_to_words(210.1, 215.0, 300.0, W)             # start inside the first quarter of a word -> before the word
    assert a == pytest.approx(209.95)
    a, b, tail = cf.snap_to_words(210.3, 215.0, 300.0, W)             # start late in the word -> behind the word
    assert a == pytest.approx(210.47)
    assert cf.snap_to_words(0.0, 5.0, 300.0, [])[:2] == (0.0, 5.0)    # no words (silent source): untouched


def test_fix_word_handles_quotes_possessive_and_case(cf):
    fix = {"Lacey": "Lacy", "rugg": "Rug"}
    assert [cf.fix_word(w, fix) for w in ["Lacey", '"Lacey', "Lacey's", "lacey", "(Rugg)", "Rugg…", "Lacey.", "other"]] == \
        ["Lacy", '"Lacy', "Lacy's", "Lacy", "(Rug)", "Rug…", "Lacy.", "other"]


def test_livewatch_cut_refuses_a_recording_gap():
    from conftest import load
    lw = load("pipeline/clipfabrik/livewatch.py", "livewatch_gap")
    with pytest.raises(Exception, match="gap"):
        lw.cut({1: "/x/1.ts", 2: "/x/2.ts"}, 0.0, 50.0, 70.0, "/tmp/never.mp4")      # segment 0 missing


def test_opencv5_without_cascade_falls_back_instead_of_crashing(cf, src_clip, monkeypatch):
    """16.11.: opencv >= 5 hat kein CascadeClassifier -> facecam 'auto' = None (native) und face_track = None, kein Absturz."""
    import sys, types
    fake = types.ModuleType("cv2")                                     # ohne CascadeClassifier
    monkeypatch.setitem(sys.modules, "cv2", fake)
    p = cf.probe(src_clip)
    assert cf.facecam_rect(src_clip, 0.5, 3.0, p, "auto") is None
    assert cf.face_track(src_clip, 0.5, 3.0, p, 600) is None
