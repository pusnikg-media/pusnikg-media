"""Facecam-Auswahl (v2) und die Zusage 'native/full/framed bleiben unverändert'."""
import json, os, re
import numpy as np
import pytest
from conftest import ROOT

SW, SH = 960, 540


def clusters_to_det(spec, nf=24):
    """spec = [(cx, cy, w, Anteil Frames mit Treffer)] -> Detektionszeilen (cx, cy, w, frame)."""
    rows = []
    for cx, cy, w, share in spec:
        for fi in range(int(nf * share)): rows.append((cx, cy, w, fi))
    return np.array(rows, float)


def moving_frames(nf=24):
    rng = np.random.default_rng(0); return rng.integers(0, 255, (nf, SH, SW), dtype=np.uint8)           # Rauschen = Bewegung in jedem Kasten


def still_frames(nf=24): return np.full((nf, SH, SW), 100, np.uint8)


def pick(cf, spec, F=None):
    holder = type("H", (), {})()
    return cf.pick_face(clusters_to_det(spec), F if F is not None else moving_frames(), 24, SW, SH, holder), holder


def test_side_cam_beats_centre_character(cf):
    """tfue-Fall: Spielfigur in der Bildmitte ist öfter im Bild als die Cam -> v1 nahm sie, v2 nimmt die Cam am Rand."""
    (cx, cy, w), h = pick(cf, [(480, 270, 90, 1.0), (140, 420, 70, 0.7)])
    assert (round(cx), round(cy)) == (140, 420)


def test_only_centre_face_falls_back(cf):
    (cx, cy, w), h = pick(cf, [(480, 270, 90, 1.0)])
    assert cx is None and h.last == "no side face"


def test_two_equal_side_faces_are_ambiguous(cf):
    (cx, cy, w), h = pick(cf, [(140, 420, 70, 0.9), (820, 100, 70, 0.9)])
    assert cx is None and "ambiguous" in h.last


def test_weaker_second_side_face_does_not_block(cf):
    (cx, cy, w), h = pick(cf, [(140, 420, 70, 0.9), (820, 100, 70, 0.3)])
    assert round(cx) == 140


def test_frozen_face_is_not_a_cam(cf):
    (cx, cy, w), h = pick(cf, [(140, 420, 70, 1.0)], F=still_frames())
    assert cx is None                                                                                      # Poster/eingefrorene Figur


def test_oversized_face_is_not_a_cam(cf):
    """sykkuno-Fall (camtest 16.11.): Gesicht mit 12 % der Bildbreite in der Ecke (Minimap/Gebäude), keine Cam im Bild -> native."""
    (cx, cy, w), h = pick(cf, [(883, 83, 115, 0.5)])
    assert cx is None and h.last == "no side face"
    (cx, cy, w), h = pick(cf, [(86, 199, 27, 0.375)])                                              # winzige echte Cam (kaicenat)
    assert round(cx) == 86


def test_rare_hits_are_not_a_cam(cf):
    (cx, cy, w), h = pick(cf, [(140, 420, 70, 0.1)])
    assert cx is None


def test_v1_still_available_for_comparison(cf):
    assert cf.FACECAM_PICK == "v2"                                                                          # Standard
    assert "v1" in open(os.path.join(ROOT, "pipeline/clipfabrik/clipfabrik.py")).read()


# ---- echtes Haar-Gesicht (Astronaut-Foto aus scikit-image): nur wenn opencv + scikit-image da sind ----
@pytest.fixture(scope="module")
def synth():
    pytest.importorskip("cv2"); pytest.importorskip("skimage")
    import sys; sys.path.insert(0, os.path.dirname(__file__)); import synth as s; return s


@pytest.mark.parametrize("kw,expect", [({"side": "left"}, "left"), ({"side": "left", "centre": True}, "left"), ({"side": "right", "centre": True}, "right"),
                                       ({"centre": True}, None), ({}, None), ({"side": "left", "second_side": "right"}, None)])
def test_picker_on_synthetic_stream(cf, synth, tmp_path, kw, expect):
    v = synth.make(str(tmp_path / "v.mp4"), **kw); p = cf.probe(v)
    cf.FACECAM_PICK = "v2"
    try: cam = cf.facecam_rect(v, 0, 4, p, "auto")
    finally: cf.FACECAM_PICK = "v2"
    if expect is None: assert cam is None
    else: assert cam and ((cam[0] + cam[2] / 2) < p["w"] / 2) == (expect == "left")


def test_split_without_cam_falls_back_to_native(cf, synth, tmp_path):
    from test_clipfabrik import WORDS
    v = synth.make(str(tmp_path / "v.mp4"), centre=True); out = str(tmp_path / "out"); os.makedirs(out)
    job = {"name": "t", "min_len": 2, "clips": [{"id": "x", "a": 0.2, "b": 3.2, "title": "T", "layout": "split", "caption": "Test caption..."}]}
    r = cf.render_clip(job, job["clips"][0], v, cf.probe(v), WORDS, out, str(tmp_path))
    assert r["layout"] == "native", "ohne Seiten-Facecam muss split sauber auf native zurückfallen"


# ---- native/full/framed bitgleich: Filter und Argumente sind festgenagelt ----
def ffmpeg_calls(cf, src, tmp, layout, monkeypatch):
    from test_clipfabrik import WORDS, CAPTION
    calls = []; orig = cf.run
    monkeypatch.setattr(cf, "run", lambda cmd, *a, **k: (calls.append(list(cmd)), orig(cmd, *a, **k))[1])
    out = str(tmp / "out"); os.makedirs(out)
    job = {"name": "t", "min_len": 3, "clips": [dict({"id": "x", "a": 0.5, "b": 4.5, "title": "TEST TITLE", "layout": layout}, **({"caption": CAPTION} if layout == "native" else {}))]}
    cf.render_clip(job, job["clips"][0], src, cf.probe(src), WORDS, out, str(tmp))
    norm = lambda x: x.replace(str(tmp), "<TMP>").replace(src, "<SRC>").replace(ROOT, "<REPO>")
    return [[norm(x) for x in c] for c in calls]


@pytest.mark.parametrize("layout", ["native", "full", "framed"])
def test_other_layouts_ffmpeg_args_unchanged(cf, src_clip, tmp_path, monkeypatch, layout):
    """Zusage 16.11.: die Facecam-Arbeit ändert nichts an native/full/framed. Golden = Argumente des Stands VOR der Änderung
    (einmalig alt gegen neu verglichen: gleiche Argumente UND gleiche Bild-/Ton-MD5 auf derselben Maschine). Ändert sich der Filter bewusst: Golden neu schreiben."""
    got = ffmpeg_calls(cf, src_clip, tmp_path, layout, monkeypatch)
    gold = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures", "ffmpeg_args_golden.json")))
    assert got == gold[layout]
