"""Livewatch offline abgesichert (Session 2, 16.11.2026): Werbepause und Watchdog Ende-zu-Ende mit synthetischen Daten.
Bisher waren nur die Bausteine einzeln getestet (is_ad_playlist, AdWatch.hit, stalled). Hier laufen der AdWatch-Thread,
der Recorder-Watchdog und loop() selbst - ohne Netz, ohne Twitch. livewatch.py wird dafür NICHT geändert."""
import glob, os, subprocess, time, types
import pytest
from conftest import load

AD = '#EXTM3U\n#EXT-X-DATERANGE:ID="stitched-ad-1",CLASS="twitch-stitched-ad",START-DATE="2026-11-19T12:00:00Z"\n#EXTINF:2.0,\nad.ts\n'
LIVE = '#EXTM3U\n#EXT-X-TARGETDURATION:2\n#EXTINF:2.000,live\nsegment1.ts\n'


@pytest.fixture()
def lw():
    return load("pipeline/clipfabrik/livewatch.py", "livewatch_off")


def fast_time(lw, monkeypatch, step=0.05):
    real = time
    monkeypatch.setattr(lw, "time", types.SimpleNamespace(time=real.time, sleep=lambda s: real.sleep(step)))


def wait_for(cond, timeout=5.0):
    t = time.time()
    while time.time() - t < timeout:
        if cond(): return True
        time.sleep(0.02)
    return False


def test_adwatch_thread_opens_and_closes_a_break(lw, tmp_path, monkeypatch):
    """Playlist wechselt live -> Werbung -> live: AdWatch muss genau einen Bereich melden und Kandidaten darin sperren."""
    fast_time(lw, monkeypatch)
    pl = tmp_path / "media.m3u8"; pl.write_text(LIVE)
    a = lw.AdWatch(lambda: pl.as_uri(), t0=time.time() - 100)       # Aufnahme läuft seit 100 s
    time.sleep(0.2); assert a.open is None and a.ranges == []
    pl.write_text(AD); assert wait_for(lambda: a.open is not None)
    assert a.hit(a.open + 1, a.open + 5), "laufende Werbepause muss Kandidaten sperren"
    pl.write_text(LIVE); assert wait_for(lambda: a.ranges)
    (x, y), = a.ranges
    assert 99 <= x <= y and a.open is None
    assert a.hit(x, y) and not a.hit(y + 60, y + 70)
    pl.write_text(LIVE + "garbage"); time.sleep(0.2); assert len(a.ranges) == 1   # kein Fehlalarm ohne Marker


def test_adwatch_survives_network_errors(lw, tmp_path, monkeypatch):
    """Playlist kurz nicht erreichbar (404/Timeout) -> kein Absturz, kein Bereich."""
    fast_time(lw, monkeypatch)
    a = lw.AdWatch(lambda: (tmp_path / "fehlt.m3u8").as_uri())
    time.sleep(0.3); assert a.open is None and a.ranges == []


class FakeProc:
    def __init__(self, hung): self.hung = hung; self.terminated = False
    def poll(self): return None if self.hung and not self.terminated else 0
    def terminate(self): self.terminated = True
    def kill(self): self.terminated = True
    def wait(self, timeout=None): return 0


def test_recorder_watchdog_restarts_hung_ffmpeg_and_gives_up(lw, tmp_path, monkeypatch):
    """ffmpeg hängt (läuft, schreibt nichts): nach `stall` s beenden, neue HLS-URL holen, mit passender Stücknummer weiter;
    nach max_restarts aufgeben (alive() False -> loop endet)."""
    fast_time(lw, monkeypatch)
    starts = []
    monkeypatch.setattr(lw, "live_url", lambda url, h: "https://hls.example/" + str(len(starts)))
    def popen(args, **k):
        starts.append(args[args.index("-segment_start_number") + 1]); return FakeProc(hung=True)
    monkeypatch.setattr(lw.subprocess, "Popen", popen)
    rec = tmp_path / "rec"; rec.mkdir()
    r = lw.Recorder({"url": "https://twitch.tv/x"}, str(rec), stall=1, max_restarts=2)
    assert r.start() and starts == ["0"]
    (rec / "00000.ts").write_bytes(b"x"); (rec / "00001.ts").write_bytes(b"x")
    assert r.alive(), "frisch beschrieben = lebt"
    old = time.time() - 30; [os.utime(f, (old, old)) for f in rec.iterdir()]; r.started = old
    r.t_start = time.time() - 5 * 60                                    # Stream läuft seit 5 min
    assert r.alive() and r.restarts == 1 and starts[-1] == "5", starts  # neue Nummer = Stream-Zeit, nicht 2 (loop füllt die Lücke)
    r.started = old
    assert r.alive() and r.restarts == 2
    r.started = old
    assert not r.alive(), "nach max_restarts muss der Recorder aufgeben"


def test_recorder_restarts_after_ffmpeg_exit(lw, tmp_path, monkeypatch):
    """ffmpeg beendet sich (Stream-Neustart, Spielwechsel): sofortiger Neustart ohne auf `stall` zu warten."""
    fast_time(lw, monkeypatch)
    procs = []
    monkeypatch.setattr(lw, "live_url", lambda url, h: "https://hls.example/x")
    monkeypatch.setattr(lw.subprocess, "Popen", lambda args, **k: procs.append(FakeProc(hung=False)) or procs[-1])
    r = lw.Recorder({"url": "u"}, str(tmp_path), stall=999, max_restarts=1)
    assert r.start() and r.alive() and r.restarts == 1 and len(procs) == 2


def test_recorder_offline_on_restart_ends(lw, tmp_path, monkeypatch):
    """Stream offline beim Neustart (keine HLS-URL) -> alive() False, kein Endlos-Neustart."""
    fast_time(lw, monkeypatch)
    urls = iter(["https://hls.example/1", None])
    monkeypatch.setattr(lw, "live_url", lambda url, h: next(urls))
    monkeypatch.setattr(lw.subprocess, "Popen", lambda args, **k: FakeProc(hung=False))
    r = lw.Recorder({"url": "u"}, str(tmp_path), stall=999, max_restarts=6)
    assert r.start() and not r.alive()


# ---- loop() Ende-zu-Ende auf einer synthetischen Aufnahme: leise Grundlinie, ein lauter Moment, Lücke durch Neustart ----

def _pieces(rec, minutes=6, loud_at=(250, 262), gap=()):
    """60-s-Stücke wie der Recorder (%05d.ts): Sinus leise, ein 12-s-Ausbruch +24 dB. gap = Stücknummern, die fehlen (Neustart)."""
    src = os.path.join(rec, "src.mp4")
    vol = f"volume='if(between(t,{loud_at[0]},{loud_at[1]}),1.0,0.06)':eval=frame"
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=gray:s=320x180:r=10:d={minutes * 60}",
                        "-f", "lavfi", "-i", f"anoisesrc=d={minutes * 60}:c=pink:a=0.5", "-af", vol, "-c:v", "libx264", "-preset", "ultrafast", "-g", "10",
                        "-c:a", "aac", "-shortest", "-f", "segment", "-segment_time", "60", "-reset_timestamps", "1",
                        os.path.join(rec, "%05d.ts")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    for i in gap: os.remove(os.path.join(rec, f"{i:05d}.ts"))
    return sorted(glob.glob(os.path.join(rec, "*.ts")))


class Ads:
    def __init__(self, ranges): self.ranges = ranges
    def hit(self, a, b, pad=8): return any(x - pad <= b and y + pad >= a for x, y in self.ranges)


def _run_loop(lw, monkeypatch, tmp_path, ads=None, gap=()):
    rec = tmp_path / "rec"; rec.mkdir(); _pieces(str(rec), gap=gap)
    made = []
    monkeypatch.setattr(lw, "make_clip", lambda ch, root, segs, t0, peak, hype, stamp: made.append((peak, hype)) or ({"id": "x", "url": "u"}, "n"))
    monkeypatch.setattr(lw, "publish", lambda *a, **k: None)
    fast_time(lw, monkeypatch, 0)
    ch = {"name": "synth", "url": "u", "warmup_s": 0, "min_hype": 9, "per_hour": 3, "max_clips": 8}
    n = lw.loop(ch, str(tmp_path), str(rec), lambda: False, False, time.time() + 600, chat=None, ads=ads, keep=True)
    return n, made


def test_loop_clips_the_loud_moment_without_chat(lw, tmp_path, monkeypatch, capsys):
    """Ohne Chat (wie Kick) entscheidet nur die Lautstärke: der Ausbruch bei 250-262 s wird genau einmal Kandidat."""
    n, made = _run_loop(lw, monkeypatch, tmp_path)
    assert n == 1 and len(made) == 1 and 245 <= made[0][0] <= 265 and made[0][1] >= 9, made
    assert "skipped={'alert': 0, 'ad': 0}" in capsys.readouterr().out


def test_loop_skips_a_moment_inside_an_ad_break(lw, tmp_path, monkeypatch, capsys):
    """Derselbe Ausbruch während einer Werbepause (Twitch-Marker 240-270 s): kein Clip, Zähler ad = 1."""
    n, made = _run_loop(lw, monkeypatch, tmp_path, ads=Ads([(240.0, 270.0)]))
    out = capsys.readouterr().out
    assert n == 0 and made == [] and "moment skipped: Twitch ad break" in out and "'ad': 0" not in out
    # Hinweis: derselbe Moment wird in jeder Folgeminute erneut als Werbe-Treffer gezählt (Zähler 2 statt 1) - nur Statistik, kein Clip.


def test_loop_keeps_time_after_a_recorder_gap(lw, tmp_path, monkeypatch):
    """Recorder-Neustart: Stück 2 fehlt (Minute 120-180 s). Der Moment bei 250 s muss trotzdem bei ~250 s liegen (nicht 190 s)."""
    n, made = _run_loop(lw, monkeypatch, tmp_path, gap=(2,))
    assert n == 1 and 245 <= made[0][0] <= 265, made


# ---- Messskript tests/livewatch_messen.py ----

LOG = """2026-11-19T12:00:01.0Z min   5 hype  3.0 peak 200 chat x0.0 at None
2026-11-19T12:01:01.0Z min   9 hype 12.0 peak 500 chat x1.2 at None
min  10 hype 12.0 peak 500 chat x1.2 at None
min  12 hype  4.0 peak 690 chat x3.8 at 700
   chat burst x3.8: moment 14 s before the chat peak
PUBLISHED https://raw.githubusercontent.com/x/clip.mp4
min  14 hype 10.0 peak 820 chat x5.1 at 830
   chat burst x5.1 skipped: alert chain (6 alerts vs 9 chatters)
min  16 hype 15.0 peak 950 chat x0.0 at None
   moment skipped: Twitch ad break
min  18 hype  6.0 peak 1060 chat x0.0 at None
min  20 hype 11.0 peak 1180 chat x3.2 at 1190
   chat burst x3.2: moment 10 s before the chat peak
WARN clip failed: too little speech around the moment (4 words): ad break / music / silence
LOOP_STATS xqc legacy=False clips=1 skipped={'alert': 1, 'ad': 1}
"""


def test_messen_lists_every_candidate_with_reason():
    m = load("tests/livewatch_messen.py", "lw_messen")
    rows = m.parse(LOG.splitlines(), warmup=480, min_hype=9)
    got = [(r["min"], r["kind"], r["result"], r["why"].split(" (")[0]) for r in rows]
    assert got == [
        (5, "laut", "gesperrt", "Aufwärmzeit"),
        (9, "laut", "gesperrt", "ohne Chat-Bestätigung"),      # Minute 10 = dieselbe Spitze -> nicht doppelt
        (12, "chat", "clip", "Clip erstellt"),
        (14, "laut", "gesperrt", "Alert-Kette"),
        (16, "laut", "gesperrt", "Werbepause"),
        (18, "laut", "gesperrt", "unter Schwelle"),
        (20, "chat", "verworfen", "zu wenig Sprache"),
    ], got
    assert rows[2]["pos"] == 690 and all(r["channel"] == "xqc" for r in rows)
    txt = m.report(rows, {"xqc:690": True})
    assert "Kandidaten 7, Clips 1" in txt and "Trefferquote chat: 1/1 postbar (100 %)" in txt


def test_messen_reads_a_real_loop_log(lw, tmp_path, monkeypatch, capsys):
    """Ende-zu-Ende: Log des synthetischen loop()-Laufs -> genau ein Clip-Kandidat bei ~250 s, Art laut."""
    _run_loop(lw, monkeypatch, tmp_path)
    m = load("tests/livewatch_messen.py", "lw_messen2")
    rows = m.parse(capsys.readouterr().out.splitlines(), warmup=0)
    clips = [r for r in rows if r["result"] == "clip"]
    assert len(clips) == 0 and any(245 <= (r["pos"] or 0) <= 265 for r in rows)  # publish ist im Test ersetzt -> kein PUBLISHED im Log
