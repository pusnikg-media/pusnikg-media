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


# --- v0.6 (18.11.): Launch-Wache -------------------------------------------------------------------------------------------
def test_watch_waits_for_from(lw, tmp_path):
    import datetime
    t = datetime.datetime(2026, 11, 19, 4, 0, tzinfo=datetime.timezone.utc).timestamp()
    root = _cfg_root(tmp_path, max_minutes=330, poll_seconds=90, **{"from": "2026-11-19T04:45:00Z"}); clk = Clock(); clk.t = t; calls = []
    def watcher(r, c, te): calls.append(clk.t); return True
    lw.watch(root, sleep=clk.sleep, now=clk.now, watcher=watcher)
    assert len(calls) == 1 and calls[0] >= t + 45 * 60 and calls[0] < t + 47 * 60       # nothing recorded before 04:45 UTC, then straight in


def test_watch_from_after_end_gives_up(lw, tmp_path):
    root = _cfg_root(tmp_path, max_minutes=10, poll_seconds=90, **{"from": "2030-01-01T00:00:00Z"}); clk = Clock(); calls = []
    lw.watch(root, sleep=clk.sleep, now=clk.now, watcher=lambda r, c, t: calls.append(1) or True)
    assert calls == [] and clk.t - 1000 <= 10 * 60 + 1


def test_posted_marker_frees_the_brake(lw, tmp_path):
    import json, datetime as D
    root = _cfg_root(tmp_path); d = tmp_path / "clips" / "live-x"; (d / "posted").mkdir(parents=True)
    ch = {"name": "x", "url": "https://www.twitch.tv/x", "max_pending": 2}
    now = D.datetime.now(D.timezone.utc).isoformat()
    (d / "inbox.json").write_text(json.dumps([{"id": "a", "at": now, "posted": False}, {"id": "b", "at": now, "posted": False}]))
    assert lw.inbox_full(root, ch)
    (d / "posted" / "a.json").write_text("{}")
    assert not lw.inbox_full(root, ch)
    lw.publish(root, "live-x", {"id": "c", "at": now, "posted": False, "url": "u", "hype": 1}, False)
    box = json.load(open(d / "inbox.json"))
    assert [e["posted"] for e in box] == [True, False, False]                             # marker folded into the inbox by the runner


def test_fixed_caption_option(lw):
    import inspect
    assert 'ch.get("caption")' in inspect.getsource(lw.make_clip)


def test_watch_caps_recording_at_until(lw, tmp_path):
    import datetime
    root = _cfg_root(tmp_path, max_minutes=300, poll_seconds=60, until="2026-11-19T17:30:00Z"); seen = []
    clk = Clock(); clk.t = datetime.datetime(2026, 11, 19, 16, 0, tzinfo=datetime.timezone.utc).timestamp()
    lw.watch(root, sleep=clk.sleep, now=clk.now, watcher=lambda r, c, t_end: seen.append(t_end) or True)
    assert seen[0] == datetime.datetime(2026, 11, 19, 17, 30, tzinfo=datetime.timezone.utc).timestamp()


# ---- v0.7 (19.11.2026): chat words, voice outburst, viewer-clip cluster ----
@pytest.mark.parametrize("text,hit", [("KEKW", True), ("LULW that was insane", True), ("NO WAY bro", True), ("CLIP IT", True), ("W", True), ("L", True),
                                      ("💀💀", True), ("w", False), ("what is he doing", False), ("hello chat how are you", False), ("this is a W moment", False)])
def test_hype_msg(lw, text, hit):
    assert lw.hype_msg(text) == hit


def test_chat_boost_and_kw_share(lw):
    assert lw.chat_boost(0) == 1.0 and lw.chat_boost(1.0) == 1.6
    c = lw.Chat.__new__(lw.Chat); c._state(False)
    for k in range(100, 110):
        for i in range(4): c.add(k, f"u{k}{i}", "KEKW" if i < 2 else "ok then")
    assert 0.45 < c.kw_share(110) < 0.55
    assert c.kw_share(500) == 0.0  # fewer than 8 messages -> no claim


def test_find_outburst_vs_last_two_minutes(lw):
    db = [-30.0] * 300 + [-12.0] * 3 + [-30.0] * 60  # scream out of a calm minute
    b, p = lw.find_outburst(db)
    assert b >= 17 and 300 <= p <= 303
    assert lw.find_outburst([-30.0] * 400)[0] == 0.0
    loud = [-12.0] * 400  # constantly loud stream: no outburst
    assert lw.find_outburst(loud)[0] == 0.0
    assert lw.find_outburst([-60.0] * 400)[1] is None  # ad gap / silence


def test_clip_cluster(lw):
    t0 = 1000.0
    assert lw.clip_cluster([t0 + 200], t0, 300) == (0, None)  # one clip is no proof
    n, pos = lw.clip_cluster([t0 + 200, t0 + 210, t0 + 215, t0 + 50], t0, 300)
    assert n == 3 and 180 <= pos <= 200
    assert lw.clip_cluster([t0 + 100, t0 + 160], t0, 300) == (0, None)  # too far apart
    assert lw.clip_cluster([t0 + 10, t0 + 12], t0, 600) == (0, None)  # older than the lookback window


def test_vod_pointers_filters_vod_window_and_dedupes(lw, monkeypatch):
    def n(o, v, vid="99", d=25, t="t"): return {"node": {"id": "x", "title": t, "viewCount": v, "durationSeconds": d, "videoOffsetSeconds": o, "video": {"id": vid}, "curator": {"login": "u"}}}
    edges = [n(1000, 50), n(1020, 80), n(5000, 10), n(300, 99), n(2000, 70, vid="12"), {"node": {"id": "y", "title": "", "viewCount": 5, "durationSeconds": 20, "videoOffsetSeconds": None, "video": None, "curator": None}}]
    monkeypatch.setattr(lw, "gql", lambda q, timeout=30: {"user": {"clips": {"edges": edges}}})
    got = lw.vod_pointers("clix", "99", 600, 3000)
    assert [(g[0], g[2]) for g in got] == [(1020, 80)]  # 300 is before the window, 5000 after, vod 12 is another broadcast, 1000 is within 45 s of the better 1020


def test_resolve_vod_from_url_and_channel(lw, monkeypatch):
    monkeypatch.setattr(lw, "gql", lambda q, timeout=30: {"video": {"createdAt": "2026-11-18T11:00:00Z"}} if "video(id" in q else
                        {"user": {"videos": {"edges": [{"node": {"id": "777", "createdAt": "2026-11-18T11:00:00Z", "lengthSeconds": 1, "title": "x"}}]}}})
    vid, created = lw.resolve_vod("https://www.twitch.tv/videos/555", "clix"); assert vid == "555" and created == 1794999600.0
    assert lw.resolve_vod("https://www.twitch.tv/clix", "clix")[0] == "777"


# ---------------------------------------------------------------- v0.8 (19.11.2026, Kai-Cenat-Auftrag): Zuschauer-Clips nach Views, Top-Clip-Modus, Cutscene-Merkmal

import datetime as _dt, json as _json, os as _os, subprocess as _sp, types as _types


def _ep(s): return _dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def _clip(id, created, views, dur=30, off=None, vid_created="2026-11-18T12:59:57Z", game="Grand Theft Auto VI", slug=None):
    return {"id": str(id), "slug": slug or f"slug{id}", "title": f"t{id}", "views": views, "created": _ep(created), "dur": dur, "off": off, "vid": "999" if off is not None else None,
            "vid_created": _ep(vid_created) if off is not None else None, "by": "viewer", "game": game}


def test_clip_query_uses_the_sort_that_works(lw):
    """19.11.: CREATED_AT_DESC -> Twitch 'server error' -> clips null -> ClipWatch war den ganzen Tag stumm (Log: NoneType object is not subscriptable)."""
    q = lw.clip_query("KaiCenat!")
    assert "VIEWS_DESC" in q and "CREATED_AT_DESC" not in q and 'login:"kaicenat"' in q and "after" not in q
    assert "videoOffsetSeconds" in q and "video{id createdAt}" in q and "viewCount" in q


def test_parse_clips_none_safe_and_complete(lw):
    with pytest.raises(RuntimeError): lw.parse_clips({"user": {"clips": None}})            # Twitch refused -> loud, not 'NoneType'
    with pytest.raises(RuntimeError): lw.parse_clips(None)
    assert lw.parse_clips({"user": {"clips": {"edges": []}}}) == []
    d = {"user": {"clips": {"edges": [
        {"node": {"id": "1", "slug": "A-b", "title": "o0mg", "viewCount": 3338, "createdAt": "2026-11-18T21:36:07Z", "durationSeconds": 11, "videoOffsetSeconds": 30906,
                  "video": {"id": "2932305259", "createdAt": "2026-11-18T12:59:57Z"}, "curator": {"login": "babbo"}, "game": {"name": "Grand Theft Auto VI"}}},
        {"node": {"id": "2", "slug": "C", "title": None, "viewCount": None, "createdAt": "2026-11-18T21:37:00Z", "durationSeconds": None, "videoOffsetSeconds": None, "video": None, "curator": None, "game": None}},
        {"node": {"id": "3", "createdAt": "kaputt"}}, None]}}}
    c = lw.parse_clips(d)
    assert [x["id"] for x in c] == ["1", "2"]                                              # kaputte Einträge fallen weg
    assert c[0]["views"] == 3338 and c[0]["vid"] == "2932305259" and c[0]["off"] == 30906 and c[0]["by"] == "babbo" and c[0]["game"] == "Grand Theft Auto VI"
    assert c[1]["views"] == 0 and c[1]["vid"] is None and c[1]["off"] is None and c[1]["by"] == ""


def test_clipwatch_poll_keeps_views_and_survives_refusal(lw, monkeypatch):
    cw = lw.ClipWatch("kaicenat", autostart=False)
    monkeypatch.setattr(lw, "gql", lambda q, timeout=30: {"user": {"clips": None}})
    with pytest.raises(RuntimeError): cw.poll()
    assert not cw.ok
    monkeypatch.setattr(lw, "gql", lambda q, timeout=30: {"user": {"clips": {"edges": [{"node": {"id": "7", "slug": "s", "title": "x", "viewCount": 51, "createdAt": "2026-11-19T10:00:00Z", "durationSeconds": 30}}]}}})
    cw.poll(); assert cw.ok and cw.items["7"]["views"] == 51 and "7" in cw.times
    assert cw.day(_ep("2026-11-19T12:00:00Z"))[0]["id"] == "7" and cw.day(_ep("2026-11-21T12:00:00Z")) == []


def test_clip_cluster_weighs_views_and_rate(lw):
    t0 = 1_000_000.0
    pts = [(t0 + 200, 4), (t0 + 210, 6)]
    assert lw.clip_cluster(pts, t0, 300)[0] == 2                                          # ohne Gewicht wie bisher
    assert lw.clip_cluster(pts, t0, 300, min_sum=150) == (0, None)                        # 2 Clips mit 10 Views zusammen = Rauschen bei Kais Reichweite
    big = [(t0 + 200, 90), (t0 + 210, 80)]
    assert lw.clip_cluster(big, t0, 300, min_sum=150)[0] == 2
    # ueblich 1 Clip/Minute: in 25 s sind 0,4 Clips normal, 4x davon = 2 -> 2 Clips reichen; bei 3 Clips/Minute (0,05/s) braucht es mind. 5
    assert lw.clip_cluster(big, t0, 300, base_rate=1 / 60)[0] == 2
    assert lw.clip_cluster(big, t0, 300, base_rate=0.05) == (0, None)
    assert lw.clip_cluster([t0 + 200, t0 + 210], t0, 300) == lw.clip_cluster([(t0 + 200, 0), (t0 + 210, 0)], t0, 300)   # alte Aufrufform bleibt gueltig


def test_clip_moment_studio_pair(lw):
    """Pruefung 19.11.: Zuschauer-Clip 'studio' (Klick 14:35:08, VOD-Offset 92114 s) und der Livewatch-Moment 143625 (t_rec 14:14:08 + peak 1291 s = 14:35:39) sind dieselbe Szene."""
    c = _clip(1, "2026-11-19T14:35:08Z", 51, dur=30, off=92114)
    m = lw.clip_moment(c)
    assert abs(m - _ep("2026-11-19T14:35:39Z")) <= 5, _dt.datetime.fromtimestamp(m, _dt.timezone.utc)
    # Offset passt nicht zur Klickzeit (Clip aus anderem Video / Wiederholung): Klickzeit - 4 s
    c2 = _clip(2, "2026-11-19T12:47:30Z", 112, dur=60, off=1451)
    assert lw.clip_moment(c2) == _ep("2026-11-19T12:47:30Z") - 4
    assert lw.clip_moment(_clip(3, "2026-11-19T12:00:00Z", 5)) == _ep("2026-11-19T12:00:00Z") - 4   # ohne Offset


def test_entry_moment_new_and_legacy(lw):
    assert lw.entry_moment({"id": "x", "moment_utc": "2026-11-19T14:35:39+00:00"}) == (_ep("2026-11-19T14:35:39Z"), 0)
    t, tol = lw.entry_moment({"id": "20261119-143625"}); assert tol == 120 and abs(t - (_ep("2026-11-19T14:36:25Z") - 60)) < 1
    assert lw.entry_moment({"id": "kaputt"}) == (None, 0)


NOW = _ep("2026-11-19T19:00:00Z")


def _day():
    base = [_clip(100 + i, f"2026-11-19T{9 + i // 6:02d}:{(i % 6) * 9:02d}:00Z", 20 + i % 25) for i in range(24)]   # ruhiger Tag, Median ~32
    return base


def test_top_candidates_threshold_is_relative_to_the_median(lw):
    items = _day() + [_clip(1, "2026-11-19T18:05:00Z", 287, dur=5), _clip(2, "2026-11-19T17:40:00Z", 45), _clip(3, "2026-11-19T17:20:00Z", 130)]
    out = lw.top_candidates(items, NOW, [])
    assert [c["id"] for c in out] == ["1", "3"]                                           # 45 Views liegen unter 1,5 x Median (~48)
    assert out[0]["rel"] > 5 and out[0]["median"] > 0
    quiet = lw.top_candidates([_clip(1, "2026-11-19T18:05:00Z", 30)] + _day(), NOW, [])
    assert quiet == []                                                                   # 30 Views: unter min_views 40
    assert lw.top_candidates([_clip(1, "2026-11-19T18:05:00Z", 90)], NOW, [])[0]["id"] == "1"   # < 8 Clips: kein Median, nur min_views


def test_top_candidates_window_age_game_and_dedupe(lw):
    items = _day() + [_clip(1, "2026-11-19T18:05:00Z", 300),                              # ok
                      _clip(2, "2026-11-19T13:00:00Z", 900),                              # aelter als 4 h
                      _clip(3, "2026-11-19T18:59:00Z", 500),                              # 60 s alt: Views kommen spaet, erst ab 90 s
                      _clip(4, "2026-11-19T18:30:00Z", 400, game="Just Chatting"),
                      _clip(5, "2026-11-19T18:10:00Z", 350),                              # 5 min spaeter: eigener Moment
                      _clip(6, "2026-11-19T18:05:20Z", 200)]                              # +20 s von Clip 1: ein Cluster, der bestbesuchte gewinnt
    ids = [c["id"] for c in lw.top_candidates(items, NOW, [])]
    assert ids == ["5", "1"], ids                                                          # beste Views zuerst; 6 ist Dublette von 1
    # schon in der Inbox (clip_id) oder Moment +-60 s zu einem vorhandenen Eintrag
    box = [{"id": "20261119-180600", "clip_id": "1", "moment_utc": "2026-11-19T18:04:40+00:00"}]
    assert [c["id"] for c in lw.top_candidates(items, NOW, box)] == ["5"]
    box = [{"id": "20261119-180900", "moment_utc": "2026-11-19T18:10:50+00:00"}]          # 5 liegt 46 s daneben -> Dublette
    assert [c["id"] for c in lw.top_candidates(items, NOW, box)] == ["1"]
    legacy = [{"id": "20261119-180500"}]                                                  # alter Eintrag ohne moment_utc: Stempel - 60 s, +-120 s Toleranz
    assert [c["id"] for c in lw.top_candidates(items, NOW, legacy)] == ["5"]
    assert lw.top_candidates(items, NOW, [], done_ids={"1", "5", "6"}) == []                   # Marker/Prozess-Gedaechtnis


def _fake_top_env(lw, monkeypatch, tmp_path, items):
    made = []
    cw = lw.ClipWatch("kaicenat", autostart=False); cw.ok = True; cw.items = {c["id"]: c for c in items}
    monkeypatch.setattr(lw, "viewer_raw", lambda c, tmp, rec=None, vod=False: (str(tmp_path / "x.mp4"), 3.5, "clip"))
    monkeypatch.setattr(lw, "make_clip", lambda ch, root, segs, t0, peak, hype, stamp, **k: made.append(k) or ({"id": stamp, "at": "2026-11-19T19:00:00+00:00", **k["extra"]}, "live-kaicenat"))
    pub = []
    monkeypatch.setattr(lw, "publish", lambda root, name, entry, push: pub.append(entry))
    return cw, made, pub


def test_top_pass_files_viewer_top_entry(lw, tmp_path, monkeypatch):
    items = _day() + [_clip(1, "2026-11-19T18:05:00Z", 300, dur=12, slug="Bug-abc")]
    cw, made, pub = _fake_top_env(lw, monkeypatch, tmp_path, items)
    state = {"last": 0.0, "failed": set(), "made": set()}
    n = lw.top_pass({"name": "kaicenat"}, str(tmp_path), cw, False, state, now=NOW)
    assert n == 1 and len(pub) == 1
    e = pub[0]
    assert e["kind"] == "viewer-top" and e["views"] == 300 and e["clip_id"] == "1" and e["clip_title"] == "t1" and e["clip_url"].endswith("/Bug-abc") and e["moment_utc"]
    assert e["raw_from"] == "clip" and e["score"] > 3 and made[0]["gates"] is False and made[0]["raw_in"].endswith("x.mp4")
    assert lw.top_pass({"name": "kaicenat"}, str(tmp_path), cw, False, state, now=NOW) == 0     # gleicher Clip nicht noch einmal (Prozess-Gedaechtnis)


def test_top_pass_failures_are_not_retried_and_hourly_cap(lw, tmp_path, monkeypatch):
    items = _day() + [_clip(1, "2026-11-19T18:05:00Z", 300), _clip(2, "2026-11-19T17:30:00Z", 200)]
    cw, made, pub = _fake_top_env(lw, monkeypatch, tmp_path, items)
    def boom(*a, **k): raise RuntimeError("clip download: 404")
    monkeypatch.setattr(lw, "viewer_raw", boom)
    state = {"last": 0.0, "failed": set(), "made": set()}
    assert lw.top_pass({"name": "kaicenat"}, str(tmp_path), cw, False, state, now=NOW) == 0 and state["failed"] == {"1"}
    monkeypatch.setattr(lw, "viewer_raw", lambda c, tmp, rec=None, vod=False: ("x.mp4", 3.0, "clip"))
    assert lw.top_pass({"name": "kaicenat"}, str(tmp_path), cw, False, state, now=NOW) == 1 and pub[0]["clip_id"] == "2"   # der kaputte wird uebersprungen
    d = tmp_path / "clips" / "live-kaicenat"; d.mkdir(parents=True)
    (d / "inbox.json").write_text(_json.dumps([{"id": f"2026111917000{i}", "kind": "viewer-top", "at": "2026-11-19T18:40:00+00:00"} for i in range(4)]))
    assert lw.top_pass({"name": "kaicenat", "top_per_hour": 4}, str(tmp_path), cw, False, {"last": 0.0, "failed": set(), "made": set()}, now=NOW) == 0   # 4 pro Stunde voll


def test_viewer_raw_prefers_the_recording_buffer(lw, tmp_path, monkeypatch):
    c = {"moment": 5000.0 + 700, "slug": "s", "vid": None, "off": None}
    calls = []
    monkeypatch.setattr(lw, "cut", lambda segs, t0, a, b, dst: calls.append((t0, a, b)) or dst)
    monkeypatch.setattr(lw, "fetch_clip", lambda slug, dst, timeout=150: (_ for _ in ()).throw(AssertionError("clip must not be downloaded")))
    raw, pk, src = lw.viewer_raw(c, str(tmp_path), rec=({}, 5000.0, 900))                # Moment 700 s nach Aufnahmestart, 900 s aufgenommen
    assert src == "recording" and pk == lw.PRE_S and calls == [(0.0, 700 - lw.PRE_S, 700 + lw.POST_S)]
    monkeypatch.setattr(lw, "fetch_clip", lambda slug, dst, timeout=150: dst)
    monkeypatch.setattr(lw.cf, "probe", lambda f: {"dur": 20.0})
    assert lw.viewer_raw(c, str(tmp_path), rec=({}, 5000.0, 710))[2] == "clip"          # Moment + POST_S noch nicht aufgenommen -> Clip selbst
    assert lw.viewer_raw(c, str(tmp_path), rec=({}, 6000.0, 900))[2] == "clip"          # Moment vor Aufnahmestart
    monkeypatch.setattr(lw, "cut", lambda *a: (_ for _ in ()).throw(RuntimeError("gap")))
    assert lw.viewer_raw(c, str(tmp_path), rec=({}, 5000.0, 900))[2] == "clip"          # Luecke / Puffer weg -> Clip selbst


def _ff(tmp_path, name, vf, secs=6):
    dst = str(tmp_path / name)
    _sp.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc2=s=1280x720:r=10:d={secs}", "-vf", vf, "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast", dst], check=True)
    return dst


def test_letterbox_share_separates_cutscene_bars_from_dark_scenes(lw, tmp_path):
    bars = _ff(tmp_path, "bars.mp4", "drawbox=x=0:y=0:w=iw:h=40:color=black:t=fill,drawbox=x=0:y=ih-40:w=iw:h=40:color=black:t=fill")
    plain = _ff(tmp_path, "plain.mp4", "null")
    night = _ff(tmp_path, "night.mp4", "eq=brightness=-0.75")                           # sehr dunkel, aber ohne Balken
    assert lw.letterbox_share(bars) >= 0.9 and lw.letterbox_share(plain) == 0.0
    assert lw.letterbox_share(night) <= 0.1, lw.letterbox_share(night)
    assert lw.letterbox_share(str(tmp_path / "gibt_es_nicht.mp4")) == 0.0               # Fehler -> 0, kein Absturz


def test_cutscene_flags_and_speech_density(lw):
    w = [{"w": "x", "s": 0.3 * i} for i in range(40)]                                    # 40 Woerter in 12 s
    assert lw.speech_density(w, 0, 12) == pytest.approx(3.33, abs=0.05) and lw.speech_density([], 0, 12) == 0.0
    assert lw.cutscene_flags(0.0, 1.0) == 0 and lw.cutscene_flags(0.5, 1.0) == 1 and lw.cutscene_flags(0.0, 3.2) == 1 and lw.cutscene_flags(0.8, 3.2) == 2


def test_contact_sheet_and_transcript(lw, tmp_path):
    src = _ff(tmp_path, "src.mp4", "null", 20)
    dst = str(tmp_path / "sheet.jpg")
    assert lw.contact_sheet(src, dst, 20.0) and _os.path.getsize(dst) > 5000
    from PIL import Image
    assert Image.open(dst).size[0] >= 4 * 480
    assert not lw.contact_sheet(str(tmp_path / "fehlt.mp4"), str(tmp_path / "s2.jpg"), 20.0)
    t = lw.transcript_text([{"s": 1.2, "e": 3, "text": "Hello there"}, {"s": 15.7, "e": 18, "text": "Why why why"}])
    assert t == "1: Hello there | 15: Why why why"
    assert len(lw.transcript_text([{"s": 1, "e": 2, "text": "word " * 900}])) == 2400


def test_kai_testset_cutscene_flag_catches_rejections_not_the_good_ones(lw):
    """Beschriftetes Testset (19.11., 23 Momente, Beschriftung nach Kontaktbogen): das Cutscene-Merkmal darf kein 'yes' abwerten und soll einen Teil der Neins fangen."""
    ts = _json.load(open(_os.path.join(_os.path.dirname(__file__), "fixtures", "kai_testset_20261119.json")))["moments"]
    assert len(ts) == 23 and sum(1 for m in ts if m["wache_old"] == "posted") == 1
    flag = {m["id"]: lw.cutscene_flags(m["letterbox"], m["speech_density"]) for m in ts}
    yes = [m["id"] for m in ts if m["label_new_rubric"] == "yes"]; no = [m["id"] for m in ts if m["label_new_rubric"] == "no"]
    assert len(yes) == 5 and len(no) == 15
    assert all(flag[i] == 0 for i in yes), {i: flag[i] for i in yes}                     # Alligator & Co. bleiben unberuehrt
    caught = [i for i in no if flag[i] >= 1]
    assert len(caught) >= 6, caught                                                      # 6 von 15 Neins (Zwischensequenzen / reiner Spieldialog)
