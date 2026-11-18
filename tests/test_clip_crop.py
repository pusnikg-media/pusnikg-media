"""crop (v6, 18.11.2026): eingebrannte Overlays am Rand (Sub-Zaehler, Logo) vor dem Layout abschneiden. Offline, nur ffmpeg."""
import subprocess
import pytest
from PIL import Image


def _src(tmp_path):
    """Gruene Quelle 1280x720 mit rotem Streifen im rechten Bereich (x >= 88 %) = 'Overlay'."""
    p = str(tmp_path / "ov.mp4")
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=0x00b000:s=1280x720:r=25:d=5,drawbox=x=1130:y=200:w=150:h=300:color=0xff0000:t=fill",
                        "-f", "lavfi", "-i", "sine=frequency=440:duration=5", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", p], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return p


def _red_pixels(mp4, tmp_path, name):
    png = str(tmp_path / (name + ".png"))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "1.5", "-i", mp4, "-frames:v", "1", png], check=True)
    im = Image.open(png).convert("RGB"); px = im.load()
    return sum(1 for x in range(0, im.width, 4) for y in range(0, im.height, 4) if px[x, y][0] > 200 and px[x, y][1] < 80)


def _render(cf, src, tmp_path, name, **fields):
    d = tmp_path / name; d.mkdir()
    job = {"name": "t", "min_len": 3, "layout": "native", "clips": [dict({"id": "x", "a": 0.5, "b": 4.5, "caption": "Clix is testing the crop..."}, **fields)]}
    r = cf.render_clip(job, job["clips"][0], src, cf.probe(src), [], str(d), str(tmp_path))
    return str(d / r["file"]), r


def test_crop_removes_edge_overlay(cf, tmp_path):
    src = _src(tmp_path)
    f0, _ = _render(cf, src, tmp_path, "plain")
    f1, r1 = _render(cf, src, tmp_path, "cropped", crop=[0, 0, 0.87, 1])
    assert _red_pixels(f0, tmp_path, "p0") > 50                      # control: the overlay is in the plain render
    assert _red_pixels(f1, tmp_path, "p1") == 0                      # cut off, also in the blurred background
    q = cf.probe(f1); assert (q["w"], q["h"]) == (1080, 1920) and r1["layout"] == "native"


@pytest.mark.parametrize("bad", [[0, 0, 0.2, 1], [0.5, 0, 0.9, 1], ["a", 0, 1, 1], [0, 0, 1], [-0.1, 0, 0.9, 1]])
def test_crop_rejects_bad_values(cf, bad):
    with pytest.raises(cf.Fail):
        cf.parse_crop(bad, {"w": 1280, "h": 720})


def test_parse_crop_pixels_and_noop(cf):
    p = {"w": 1280, "h": 720}
    assert cf.parse_crop(None, p) is None and cf.parse_crop([0, 0, 1, 1], p) is None
    x, y, w, h = cf.parse_crop([0, 0.1, 0.87, 0.8], p)
    assert (x, y) == (0, 72) and w == 1113 // 2 * 2 and h == 576 and all(v % 2 == 0 for v in (x, y, w, h))


def test_crop_changes_job_signature(cf):
    a = {"name": "t", "source": "s", "clips": [{"id": "x", "a": 0, "b": 12}]}
    assert cf.job_sig(a) != cf.job_sig({**a, "crop": [0, 0, 0.87, 1]})
    assert cf.job_sig(a) == cf.job_sig(dict(a))
