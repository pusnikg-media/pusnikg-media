"""Crop + Frame-Prüfungen (Jason-Kampagne, 16.11.): crop-Option, "Gesicht im Bild", Multi-Fenster, Overlay-Warnung.
Rein synthetisch, offline. Die Haar-Tests brauchen OpenCV (+ scikit-image für ein echtes Gesicht) und überspringen sich ohne sie."""
import os, subprocess, sys
import numpy as np
import pytest
from conftest import ROOT, ffprobe

sys.path.insert(0, os.path.join(ROOT, "pipeline", "clipfabrik"))
import framecheck as fc

try:
    import cv2 as _cv2
    HAVE_CV2 = True
except ImportError:
    HAVE_CV2 = False
needs_cv2 = pytest.mark.skipif(not HAVE_CV2, reason="OpenCV fehlt")


def moving(n=12, h=270, w=480, seed=0):
    """Jedes Bild ein anderes weiches Muster = Bewegung überall (wie eine bewegte IRL-Kamera), aber keine Dauerkanten wie bei weißem Rauschen."""
    from scipy.ndimage import gaussian_filter
    rng = np.random.default_rng(seed)
    return np.stack([np.clip(gaussian_filter(rng.normal(130, 110, (h, w)), 5), 30, 230).astype(np.uint8) for _ in range(n)])


# ---------------------------------------------------------------- crop
def test_norm_crop_forms():
    assert fc.norm_crop(None) is None and fc.norm_crop(0) is None and fc.norm_crop(False) is None
    assert fc.norm_crop(0.15) == (0.15, 0, 0, 0)
    assert fc.norm_crop({"top": 0.15, "right": 0.1}) == (0.15, 0, 0, 0.1)
    assert fc.norm_crop([0.1, 0, 0, 0]) == (0.1, 0, 0, 0)
    for bad in (0.6, -0.1, "x", {"top": 0.9}):
        with pytest.raises(ValueError): fc.norm_crop(bad)


def test_crop_rect_even_and_cuts_top():
    x, y, w, h = fc.crop_rect((0.15, 0, 0, 0), 1920, 1080)
    assert (x, w) == (0, 1920) and y == 162 and h == 918 and all(v % 2 == 0 for v in (x, y, w, h))
    x, y, w, h = fc.crop_rect((0.15, 0.05, 0.1, 0), 1281, 721)   # ungerade Quelle: trotzdem gerade Maße (yuv420)
    assert all(v % 2 == 0 for v in (x, y, w, h)) and x + w <= 1281 and y + h <= 721


@pytest.fixture(scope="module")
def banner_src(tmp_path_factory):
    """720p, oben ein 108-px-Streifen (15 %) in knallrot = 'eingebrannter Chat', darunter blau mit weißem Rechteck in der Mitte; mit Ton."""
    p = str(tmp_path_factory.mktemp("bn") / "banner.mp4")
    vf = "drawbox=x=0:y=0:w=1280:h=108:color=red:t=fill,drawbox=x=500:y=300:w=280:h=200:color=white:t=fill"
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=1280x720:r=25:d=5", "-f", "lavfi", "-i", "sine=frequency=300:d=5",
                        "-vf", vf, "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", p], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return p


def mean_rgb(f, t, x, y):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", f, "-vf", f"crop=8:8:{x}:{y},scale=1:1,format=rgb24", "-frames:v", "1", "-f", "rawvideo", "-"], capture_output=True)
    return tuple(r.stdout[:3])


def render(cf, src, tmp, job_extra=None, **clip):
    out = str(tmp / "out"); os.makedirs(out, exist_ok=True)
    job = dict({"name": "t", "min_len": 3, "clips": []}, **(job_extra or {}))
    c = dict({"id": "x", "a": 0.5, "b": 4.0, "title": "TEST"}, **clip)
    p = cf.probe(src)
    r = cf.render_clip(job, c, src, p, [], out, str(tmp))
    return r, os.path.join(out, r["file"])


def test_crop_removes_top_strip_full_layout(cf, banner_src, tmp_path):
    """layout full = ganzes 9:16-Bild aus der Quelle: ohne crop sitzt der rote Streifen oben im Bild, mit crop 0.15 ist er weg."""
    d1, d2 = tmp_path / "a", tmp_path / "b"; d1.mkdir(); d2.mkdir()
    cap = "Jason did NOT expect this to happen on stream today... 😭"      # mit Caption kein dunkler Titel-Verlauf über dem Bild
    _, f0 = render(cf, banner_src, d1, layout="full", zoom=False, caption=cap)
    r, f1 = render(cf, banner_src, d2, layout="full", zoom=False, caption=cap, crop=0.15)
    red0 = mean_rgb(f0, 1, 40, 60); red1 = mean_rgb(f1, 1, 40, 60)
    assert red0[0] > 180 and red0[2] < 80, f"Testbild ohne crop sollte oben rot sein: {red0}"
    assert not (red1[0] > 180 and red1[2] < 80), f"mit crop darf oben nichts Rotes mehr sein: {red1}"
    q = ffprobe(f1)
    assert (q["w"], q["h"]) == (1080, 1920) and abs(q["dur"] - 3.5) < 0.5 and q["audio"], q   # sauber 9:16, Dauer + Ton unverändert
    assert r["crop"] == [0.15, 0.0, 0.0, 0.0] and r["layout"] == "full" and r["ok"]


@pytest.mark.parametrize("layout", ["native", "framed"])
def test_crop_other_layouts_render_1080x1920(cf, banner_src, tmp_path, layout):
    r, f = render(cf, banner_src, tmp_path, layout=layout, crop={"top": 0.15}, caption="Jason did NOT expect this to happen on stream today... 😭")
    q = ffprobe(f)
    assert (q["w"], q["h"]) == (1080, 1920) and q["audio"] and abs(q["dur"] - 3.5) < 0.5 and r["layout"] == layout


def test_crop_with_hook_keeps_duration(cf, banner_src, tmp_path):
    r, f = render(cf, banner_src, tmp_path, layout="native", crop=0.15, caption="Jason did NOT expect this to happen on stream today... 😭", hook=[3.0, 4.0])
    assert abs(ffprobe(f)["dur"] - 4.5) < 0.7 and r["hook"] == [3.0, 4.0]    # Teaser 1 s + Clip 3.5 s, trotz Zeitverschiebung im Crop-Zwischenstück


def test_crop_in_signature_only_when_set(cf):
    """Alte Aufträge ohne crop/check behalten ihre Signatur (sonst Neurender aller Clips)."""
    base = {"source": "x", "clips": [{"id": "a"}]}
    assert cf.job_sig(base) == cf.job_sig(dict(base)) and cf.job_sig(dict(base, crop=0.15)) != cf.job_sig(base)
    assert cf.job_sig(dict(base, check=True)) != cf.job_sig(base)


# ---------------------------------------------------------------- Gesicht im Bild (Entscheidung, rein)
def test_face_verdict_pass_and_fail():
    dt = 0.67
    assert fc.face_verdict([0.12] * 20, dt)["ok"]
    assert fc.face_verdict([0.12, 0, 0.1, 0.11, 0, 0.12, 0.1, 0.09] * 3, dt)["ok"]                 # kurze Lücken sind normal (Kopf gedreht)
    v = fc.face_verdict([0.0] * 20, dt); assert not v["ok"] and "only 0%" in v["reason"]            # nie ein Gesicht (POV-Szene)
    v = fc.face_verdict([0.12] * 6 + [0.0] * 14, dt); assert not v["ok"]                           # 30 % Anteil
    v = fc.face_verdict([0.12] * 8 + [0.02] * 12 + [0.12] * 8, dt, {"min_share": 0.3}); assert not v["ok"] and "in a row" in v["reason"]   # lange Lücke trotz Anteil
    assert not fc.face_verdict([0.05] * 20, dt)["ok"]                                              # Gesicht zu klein (< 7 % der Breite)
    assert not fc.face_verdict([], dt)["ok"]


# ---------------------------------------------------------------- Multi-Fenster
def with_lines(F, xs=(), ys=()):
    F = F.copy(); h, w = F.shape[1:]
    for x in xs: F[:, :, int(x * w):int(x * w) + 3] = 0
    for y in ys: F[:, int(y * h):int(y * h) + 3, :] = 0
    return F


def test_tiles_plain_moving_picture_passes():
    assert fc.tile_verdict(fc.tile_metrics(moving()))["ok"]


def test_tiles_lasting_lines_rejected():
    v = fc.tile_verdict(fc.tile_metrics(with_lines(moving(), xs=(0.5,), ys=(0.5,)))); assert not v["ok"] and "multi-window" in v["reason"]
    assert not fc.tile_verdict(fc.tile_metrics(with_lines(moving(), xs=(0.33, 0.66))))["ok"]
    assert fc.tile_verdict(fc.tile_metrics(with_lines(moving(), xs=(0.5,))))["ok"]                  # EINE Linie allein (Türrahmen) reicht nicht


def test_tiles_mostly_black_rejected():
    F = moving(); F[:, :, : int(0.7 * F.shape[2])] = 0
    v = fc.tile_verdict(fc.tile_metrics(F)); assert not v["ok"] and "black" in v["reason"]


# ---------------------------------------------------------------- Overlay-Warnung
@needs_cv2
def test_static_overlay_found_on_moving_scene():
    F = moving(); F[:, 20:60, 300:460] = np.tile(np.random.default_rng(9).integers(0, 255, (40, 160), dtype=np.uint8), (len(F), 1, 1))   # gleiche Pixel in jedem Bild
    so = fc.static_overlays(F)
    assert so and so[0]["box"][0] > 0.55 and so[0]["box"][1] < 0.2


@needs_cv2
def test_static_overlay_silent_on_static_scene_and_on_moving_scene():
    assert fc.static_overlays(np.repeat(moving(1), 12, axis=0)) == []     # nichts bewegt sich: Overlay nicht von Szene trennbar -> keine Warnung
    assert fc.static_overlays(moving()) == []                              # alles bewegt sich -> nichts bleibt stehen


# ---------------------------------------------------------------- OpenCV: echtes Gesicht
@needs_cv2
def test_face_widths_real_face_and_no_face():
    skd = pytest.importorskip("skimage.data", reason="scikit-image fehlt")
    img = _cv2.resize(_cv2.cvtColor(skd.astronaut(), _cv2.COLOR_RGB2GRAY), (270, 270))      # 512x512 -> quadratisch lassen (kein Verzerren)
    canvas = np.full((270, 480), 90, np.uint8); canvas[:, 105:375] = img                     # 16:9-Bild, Gesicht ca. 10 % der Breite
    wd = fc.face_widths(np.stack([canvas] * 4))
    assert wd is not None and all(w >= 0.07 for w in wd), wd
    assert fc.face_widths(np.full((4, 270, 480), 90, np.uint8)) == [0.0] * 4     # leeres Bild: kein Gesicht


@needs_cv2
def test_check_clip_rejects_clip_without_face(banner_src):
    r = fc.check_clip(banner_src, 0.5, 4.0, {"face": True, "tiles": False, "logo": False})
    assert not r["ok"] and any("face" in x for x in r["reasons"])
    assert fc.check_clip(banner_src, 0.5, 4.0, {"face": False, "tiles": False, "logo": False})["ok"]


@needs_cv2
def test_render_clip_raises_rejected_when_check_fails(cf, banner_src, tmp_path):
    with pytest.raises(cf.Fail, match="rejected"):
        render(cf, banner_src, tmp_path, layout="native", crop=0.15, check={"face": True, "tiles": False, "logo": False}, caption="Jason did NOT expect this to happen... 😭")


# ---------------------------------------------------------------- Livewatch-Profile
def test_irl_profile_crops_and_checks_gaming_does_not():
    from conftest import load
    lw = load("pipeline/clipfabrik/livewatch.py", "livewatch_fc")
    irl = lw.with_profile({"name": "x", "profile": "irl"}); g = lw.with_profile({"name": "x"})
    assert irl["crop"] == 0.17 and irl["check"] is True and "crop" not in g and "check" not in g
    assert lw.with_profile({"name": "x", "profile": "irl", "crop": 0.2})["crop"] == 0.2      # eigener Wert im Kanaleintrag gewinnt


def test_publish_to_throwaway_branch_never_touches_main(tmp_path, monkeypatch):
    """Testlauf-Modus (LW_PUSH_BRANCH): Ergebnisse gehen auf einen Wegwerf-Branch, main bleibt unberührt."""
    from conftest import load
    lw = load("pipeline/clipfabrik/livewatch.py", "livewatch_pub")
    g = lambda *a, cwd=None: subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=True).stdout
    bare, work = str(tmp_path / "bare.git"), str(tmp_path / "work")
    g("init", "-q", "--bare", "-b", "main", bare); g("clone", "-q", bare, work)
    g("config", "user.email", "t@t", cwd=work); g("config", "user.name", "t", cwd=work)
    open(os.path.join(work, "README"), "w").write("x"); g("add", "README", cwd=work); g("commit", "-q", "-m", "init", cwd=work); g("push", "-q", "origin", "HEAD:main", cwd=work)
    main_sha = g("rev-parse", "main", cwd=bare).strip()
    monkeypatch.setenv("LW_PUSH_BRANCH", "tmp-replay")
    os.makedirs(os.path.join(work, "clips", "live-x")); open(os.path.join(work, "clips", "live-x", "a.txt"), "w").write("clip")
    lw.publish(work, "live-x", {"id": "1", "hype": 9.0, "url": "https://raw.githubusercontent.com/o/r/main/clips/live-x/a.txt"}, True)
    assert g("rev-parse", "main", cwd=bare).strip() == main_sha, "main wurde verändert"
    assert "live-x" in g("ls-tree", "-r", "--name-only", "tmp-replay", cwd=bare)
