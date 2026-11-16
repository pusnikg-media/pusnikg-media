"""Livewatch v0.4: Chat-Signal ohne Alerts, Profile, Werbepause, Watchdog, Sicherheitsfilter (alles offline, kein Netz)."""
import pytest
from conftest import load


@pytest.fixture(scope="module")
def lw():
    return load("pipeline/clipfabrik/livewatch.py", "livewatch_t")


def replay_chat(lw, msgs, legacy):
    c = object.__new__(lw.ReplayChat); c.ch = "t"; c.total = len(msgs); c.msgs = msgs; c._state(legacy); c._fill(); return c


@pytest.mark.parametrize("login,text,bits,kind", [
    ("viewer1", "LOL that was so funny", 0, None),
    ("viewer1", "KEKW KEKW", 0, None),
    ("StreamElements", "someone just donated $5", 0, "bot"),
    ("nightbot", "hello", 0, "bot"),
    ("viewer2", "!discord", 0, "cmd"),
    ("viewer3", "Cheer100 nice", 0, "cheer"),
    ("viewer3", "great stream", 250, "cheer"),
    ("viewer4", "Kappa500", 0, "cheer"),
    ("viewer5", "bob has just subscribed with Prime", 0, "alert"),
    ("viewer6", "alice gifted 5 subs", 0, "alert"),
    ("viewer7", "i cheered for him", 0, None),
])
def test_classify(lw, login, text, bits, kind):
    assert lw.classify(login, text, bits) == kind


def test_parse_irc(lw):
    line = b"@badge-info=;bits=100;display-name=Bob;emotes= :bob!bob@bob.tmi.twitch.tv PRIVMSG #jason :Cheer100 hi there"
    cmd, login, text, tags = lw.parse_irc(line)
    assert (cmd, login, text, tags["bits"]) == ("PRIVMSG", "bob", "Cheer100 hi there", "100")
    cmd, login, text, tags = lw.parse_irc(b"@msg-id=subgift;login=x :tmi.twitch.tv USERNOTICE #jason :")
    assert cmd == "USERNOTICE" and tags["msg-id"] in lw.USERNOTICE_ALERTS


def burst_msgs(kind):
    """600 s ruhiger Chat (1 Nachricht/s, 50 verschiedene Nutzer), dann 10 s Spitze bei Sekunde 520."""
    m = [(k, f"u{k % 50}", "hmm ok") for k in range(600)]
    for k in range(520, 530):
        for j in range(8):
            m.append((k, f"v{(k * 8 + j) % 300}", "LUL LUL") if kind == "real" else (k, f"spam{j % 3}", "Cheer100 take my bits"))
    return m


def test_alert_chain_is_no_chat_spike(lw):
    legacy = replay_chat(lw, burst_msgs("alert"), True).peak(600)
    new = replay_chat(lw, burst_msgs("alert"), False).peak(600)
    assert legacy[0] >= 4.5, legacy          # alt: Donation-/Bits-Kette gilt als Spitze (Fehlalarm im robcdee-Test)
    assert new[0] < 2.0, new                 # neu: Alerts zaehlen nicht


def test_real_burst_still_detected(lw):
    new = replay_chat(lw, burst_msgs("real"), False).peak(600)
    assert new[0] >= 4.5 and new[1] is not None and 500 <= new[1] <= 530, new


def test_alert_near_counts_alerts_and_chatters(lw):
    c = replay_chat(lw, burst_msgs("alert"), False)
    alerts, users = c.alert_near(526)
    assert alerts >= 60 and users > 0
    assert replay_chat(lw, burst_msgs("real"), False).alert_near(526)[0] == 0


def test_profile(lw):
    assert lw.with_profile({"profile": "irl"})["min_chat"] == 4.5 and lw.with_profile({"profile": "irl"})["co_chat"] == 2.5
    assert lw.with_profile({"profile": "gaming"})["min_chat"] == 3.0
    assert lw.with_profile({})["min_chat"] == 3.0                         # Standard = gaming
    assert lw.with_profile({"profile": "irl", "min_chat": 3.5})["min_chat"] == 3.5   # explizit gewinnt


def test_watchdog_stalled(lw):
    assert not lw.stalled(1000, 950, 900)           # frisch beschrieben
    assert lw.stalled(1200, 1000, 900)              # 200 s nichts geschrieben
    assert lw.stalled(1200, 0, 1000)                # nie ein Stueck seit dem Start (200 s)
    assert not lw.stalled(1100, 0, 1000)            # Start vor 100 s, noch Schonfrist


def test_fill_gap_keeps_db_aligned(lw):
    db = [0.0] * 120                                  # Stuecke 0 und 1
    assert lw.fill_gap(db, 2, 2) == 3 and len(db) == 120
    assert lw.fill_gap(db, 5, 3) == 6 and len(db) == 120 + 2 * lw.SEG   # Stuecke 3,4 fehlen (Neustart)


def test_ad_playlist(lw):
    assert lw.is_ad_playlist('#EXT-X-DATERANGE:ID="stitched-ad-1",CLASS="twitch-stitched-ad",START-DATE="2026-11-16T10:00:00Z"')
    assert lw.is_ad_playlist('#EXT-X-DATERANGE:ID="x",CLASS="twitch-ad-quartile"')
    assert not lw.is_ad_playlist('#EXTM3U\n#EXT-X-TARGETDURATION:6\n#EXTINF:2.000,live\nsegment1.ts')
    assert not lw.is_ad_playlist("")


def test_adwatch_hit(lw):
    a = object.__new__(lw.AdWatch); a.ranges = [(100.0, 130.0)]; a.open = None; a.t0 = 0
    assert a.hit(110, 120) and a.hit(135, 140) and not a.hit(200, 210)    # 8 s Toleranz an den Raendern


@pytest.mark.parametrize("text,bad", [
    ("i just want to kill myself lol", True), ("kys", True), ("this is suicidal", True), ("i wanna die", True),
    ("he is going to kill my vibe", False), ("that was a killer play", False), ("this is so funny", False),
])
def test_selfharm(lw, text, bad):
    assert lw.selfharm(text) is bad


def test_speech_rate(lw):
    words = [{"w": "x", "s": float(i)} for i in range(10)]
    assert lw.speech_rate(words, 0, 10) == 1.0
    assert lw.speech_rate(words, 20, 30) == 0.0         # Geh-/Fahr-Szene ohne Sprache


# --- v0.5: wait for the stream instead of ending the run when every channel is offline -------------------------------------
def _cfg_root(tmp_path, **kw):
    import json
    (tmp_path / "plan").mkdir()
    (tmp_path / "plan" / "livewatch.json").write_text(json.dumps({"enabled": True, "channels": [{"name": "x", "url": "https://www.twitch.tv/x"}], **kw}))
    return str(tmp_path)


class Clock:
    def __init__(self): self.t = 1000.0; self.sleeps = []
    def now(self): return self.t
    def sleep(self, s): self.sleeps.append(s); self.t += s


def test_watch_waits_until_stream_starts(lw, tmp_path):
    root = _cfg_root(tmp_path, max_minutes=60, poll_seconds=60); clk = Clock(); calls = []
    def watcher(r, c, t_end):
        calls.append(clk.t); return len(calls) == 4          # offline three times, live on the 4th look
    lw.watch(root, sleep=clk.sleep, now=clk.now, watcher=watcher)
    assert len(calls) == 4 and clk.sleeps == [60, 60, 60]


def test_watch_gives_up_when_time_is_over(lw, tmp_path):
    root = _cfg_root(tmp_path, max_minutes=5, poll_seconds=60); clk = Clock(); calls = []
    lw.watch(root, sleep=clk.sleep, now=clk.now, watcher=lambda r, c, t: calls.append(1) or False)
    assert 4 <= len(calls) <= 6 and clk.t - 1000 <= 5 * 60


def test_watch_respects_until(lw, tmp_path):
    import datetime
    root = _cfg_root(tmp_path, max_minutes=300, poll_seconds=60, until="2026-11-19T20:00:00Z"); clk = Clock()
    clk.t = datetime.datetime(2026, 11, 19, 19, 57, tzinfo=datetime.timezone.utc).timestamp(); t0 = clk.t
    lw.watch(root, sleep=clk.sleep, now=clk.now, watcher=lambda r, c, t: False)
    assert clk.t - t0 <= 3 * 60


def test_watch_once_offline_returns_false(lw, tmp_path, monkeypatch):
    class R:
        def __init__(self, ch, rec): pass
        def start(self, n): return False
    monkeypatch.setattr(lw, "Recorder", R)
    root = _cfg_root(tmp_path)
    assert lw.watch_once(root, lw.cfg(root), 9e12) is False


def test_inbox_full_stops_recording(lw, tmp_path):
    import json, os
    root = _cfg_root(tmp_path); d = tmp_path / "clips" / "live-x"; d.mkdir(parents=True)
    ch = {"name": "x", "url": "https://www.twitch.tv/x", "max_pending": 3}
    assert not lw.inbox_full(root, ch)                                                   # no inbox yet
    import datetime as D
    now = D.datetime.now(D.timezone.utc); fresh = lambda **k: dict({"at": now.isoformat(), "posted": False}, **k); old = {"at": (now - D.timedelta(hours=30)).isoformat(), "posted": False}
    (d / "inbox.json").write_text(json.dumps([fresh(), fresh(posted=True), fresh()]))
    assert not lw.inbox_full(root, ch)                                                   # 2 unposted < 3
    (d / "inbox.json").write_text(json.dumps([fresh(), fresh(), old, old]))
    assert not lw.inbox_full(root, ch)                                                   # entries older than 24 h do not count
    (d / "inbox.json").write_text(json.dumps([fresh()] * 3))
    assert lw.inbox_full(root, ch)
    assert lw.watch_once(root, lw.cfg(root) | {"channels": [ch]}, 9e12) is True          # returns without touching the recorder
