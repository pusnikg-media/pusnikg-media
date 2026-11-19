"""Livewatch v0 (prototype, 15.11.2026): "almost live" clipping on a free GitHub runner.
Watches the channels in plan/livewatch.json; while one is live it records the stream in 60 s pieces, measures loudness
per second against the last 10 minutes, and when a moment clearly stands out (shouting, laughter, crowd) it cuts,
captions and renders a 9:16 clip a few minutes after it happened -> clips/live-<channel>/ + inbox.json (pushed at once).
Posting is NOT done here (no platform keys on the runner): an agent reads inbox.json, looks at the QA picture,
writes title/caption and posts through vidIQ.

  python3 livewatch.py check REPO_ROOT           prints "run" when enabled and a channel is configured, else "skip"
  python3 livewatch.py watch REPO_ROOT           the watcher (used by .github/workflows/livewatch.yml)
  python3 livewatch.py simulate FILE REPO_ROOT   same detection + rendering on a local file (test without a live stream)
  python3 livewatch.py replay VOD_URL START MINUTES REPO_ROOT [min_chat] [compare]
                                                 VOD mode (v0.3, 16.11.): plays MINUTES of a past Twitch VOD from second START as if it were live -
                                                 audio from the VOD, chat from the Twitch chat replay (GQL, anonymous), same detection, same clips

plan/livewatch.json:
  {"enabled": false, "max_minutes": 330, "channels": [
     {"name": "tjr", "url": "https://kick.com/tjr", "min_hype": 9, "per_hour": 3, "max_clips": 8, "height": 720,
      "layout": "full", "track": true, "fix": {"fucking": "f*cking"}}]}
  min_hype = dB above the 10-min baseline (mean of the 4 loudest seconds in a 20 s window); 9 is strict, 6 is generous.
  "profile": "irl" | "gaming" (v0.4, 16.11.): irl = min_chat 4.5 / co_chat 2.5 (walking / talking streams, chat is calm), gaming = 3.0 / 2.0 (default).
  Explicit min_chat / co_chat in the channel entry win over the profile. "alert_max": alert events that make a chat burst count as alert-driven (default 3).

v0.4 (16.11.2026): the chat signal ignores alerts (bots, !commands, cheers/bits, bot-style donation / sub lines, USERNOTICE gift subs + raids) and counts DISTINCT
chatters per window; a burst that is mostly an alert chain is skipped. Twitch ad breaks are read from the HLS playlist (live only) and skipped. A recorder watchdog
restarts ffmpeg when nothing was written for 2 minutes. Clips with self-harm wording or without speech (walking / driving) are dropped before rendering.

v0.8 (19.11.2026, Kai-Cenat-Auftrag): (1) ClipWatch repariert - Twitch antwortet auf sort:CREATED_AT_DESC mit "server error" (clips = null), das war der "NoneType"-Fehler im Log;
jetzt VIEWS_DESC, eine Seite (ab Seite 2 verlangt Twitch einen Integrity-Token), mit Views. (2) Top-Clip-Modus: die meistgesehenen neuen Zuschauer-Clips des Kanals (relativ zum Median)
werden mit yt-dlp geladen und als Inbox-Eintrag `kind: viewer-top` abgelegt (views, clip_title, clip_id). (3) Zuschauer-Cluster zaehlen nach Views und nur ueber der ueblichen Clip-Rate.
(4) Fenster 30 s vor / 25 s nach dem Moment (Kais Reaktion kommt nach dem Ereignis). (5) Jeder Eintrag: kind, score, moment_utc, Kontaktbogen (8 Bilder), ganzes Transkript,
cutscene-Merkmal (Letterbox-Balken / dichter Spielton; nur Abwertung im score, nie Verwerfen). (6) Die Vorschau-mp4 kommt nicht mehr ins Repo (halbiert die Bytes je Eintrag).
  python3 livewatch.py probe REPO_ROOT           druckt nur: Zuschauer-Clips per GQL + ein Test-Download (keine Datei im Repo, kein git)"""
import datetime, glob, json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import clipfabrik as cf

SEG = 60
PRE_S, POST_S = 30, 25  # v0.8: raw window around the peak; the reaction comes AFTER the event


def cfg(root):
    try: return json.load(open(os.path.join(root, "plan", "livewatch.json")))
    except Exception: return {}


def live_url(url, height):
    """Direct HLS URL when the channel is live right now, else None."""
    try:
        r = subprocess.run(["yt-dlp", "-g", "--no-playlist", "-f", f"b[height<={height}]/b", url], capture_output=True, text=True, timeout=120)
    except Exception: return None
    u = [l for l in r.stdout.split("\n") if l.startswith("http")]
    if r.returncode == 0 and u: return u[0]
    print("   ", (r.stderr.strip().split("\n") or [""])[-1][:160]); return None  # why not: offline, blocked, login wall ...


def seg_db(path):
    try: return cf.loudness(path).tolist()
    except Exception: return []


def find_peak(db, win=20, base=600):
    """(hype, peak second) of the best 20 s window in the newest 3 minutes, against the median of the last `base` s."""
    import numpy as np
    d = np.array(db[-base:], dtype=np.float32); n = len(d)
    if n < 150: return 0.0, None  # needs 2.5 min of baseline first
    ex = np.clip(d - float(np.median(d)), 0, 30); ex[d < -50] = 0
    lo = max(n - 180, 0); best, bt = 0.0, None
    for t in range(lo, n - win + 1):
        s = float(np.sort(ex[t:t + win])[-4:].mean())
        if s > best: best, bt = s, t + int(np.argmax(ex[t:t + win]))
    return best, (len(db) - n + bt if bt is not None else None)


PROFILES = {"irl": {"min_chat": 4.5, "co_chat": 2.5}, "gaming": {"min_chat": 3.0, "co_chat": 2.0}}


HYPE_RE = re.compile(r"(?i)(?:\bkekw\w*|\blul\w*|\bomegalul\w*|\blmf?ao\b|\bclip (?:it|that)\b|\bno ?way\b|\bbro+\b|\bwtf\b|\bpog\w*|\bomg\b|\bicant\b|\bhol[yl]\b|\blets? ?go+\b|\bcracked\b|\binsane\b|\bcrazy\b|💀|😂|🤣|😭|🔥)")
HYPE_RE_CS = re.compile(r"^(?:W+|L+)$")  # a bare "W" / "L" counts only as a whole message (case-sensitive: lowercase w/l is noise)


def hype_msg(text):
    """v0.7: chat CONTENT signal - KEKW / LUL / OMEGALUL / LMAO / skulls / laughing / 'CLIP IT' / W / L / 'NO WAY' / BRO."""
    t = (text or "").strip()
    if HYPE_RE_CS.match(t): return True
    return bool(HYPE_RE.search(re.sub(r"\b[WL]\b", "", t)))


def chat_boost(share):
    """Share of hype messages (0-1) in the burst window -> multiplier for the chat ratio (1.0 ... 1.6)."""
    return 1.0 + min(max(share, 0.0), 0.6)


def find_outburst(db, short=4, ref=120, look=180):
    """v0.7: sudden voice outburst (scream, laughter) against the last `ref` seconds only (not the 10 min baseline): best (dB, position) of the newest `look` s,
    where dB = mean of the 2 loudest seconds in a `short` s window minus the median of the `ref` s before it (silence / ad gaps ignored)."""
    import numpy as np
    d = np.array(db, dtype=np.float32); n = len(d); best, bp = 0.0, None
    for t in range(max(ref, n - look), n - short + 1):
        w = d[t - ref:t]; w = w[w > -50]
        if len(w) < ref // 2: continue
        cur = d[t:t + short]
        if (cur < -50).any(): continue
        s = float(np.sort(cur)[-2:].mean() - np.median(w))
        if s > best: best, bp = s, t + int(np.argmax(cur))
    return round(best, 1), bp


def clip_cluster(times, t0, upto, near=25, need=2, look=240, min_sum=0, base_rate=0.0, rate_mult=4.0):
    """v0.7: viewers' Twitch clips created at (almost) the same time = strongest sign of a moment. times = clip creation epochs, t0 = recording start epoch,
    upto = recording seconds so far. Returns (n, position): the biggest group of >= need clips within `near` s in the newest `look` s; the moment is ~14 s
    before the click (a clip holds ~25 s before + 5 s after the click, and people click after the reaction).
    v0.8: an item may also be (epoch, views). min_sum = the group's views must add up to at least this (views weigh the group: with Kai's reach 2 clips of 5 views are noise);
    base_rate = the channel's usual clips per second, the group must hold at least rate_mult x the clips that rate gives in `near` s (a busy channel needs bigger groups)."""
    import math
    pts = sorted((x, 0) if isinstance(x, (int, float)) else (x[0], x[1]) for x in times)
    pts = [(x - t0, v) for x, v in pts if upto - look <= x - t0 <= upto]
    need = max(need, math.ceil(rate_mult * base_rate * near)) if base_rate > 0 else need
    best, mid = 0, None
    for i, (a, _) in enumerate(pts):
        grp = [(x, v) for x, v in pts[i:] if x - a <= near]
        if len(grp) > best and sum(v for _, v in grp) >= min_sum: best, mid = len(grp), sum(x for x, _ in grp) / len(grp)
    if best < need: return 0, None
    return best, max(int(mid) - 14, 0)


def clip_query(login, first=100):
    """v0.8: the ONLY sort that works anonymously is VIEWS_DESC (CREATED_AT_DESC answers 'server error' -> clips null, 19.11. log: "'NoneType' object is not subscriptable");
    ONE page (an `after` cursor fails Twitch's integrity check). Result = the ~70 best viewed clips of the last 24 h (floor ~20 views on a big channel)."""
    return ('query{user(login:"%s"){clips(first:%d, criteria:{period:LAST_DAY, sort:VIEWS_DESC}){edges{node{id slug title viewCount createdAt durationSeconds '
            'videoOffsetSeconds video{id createdAt} curator{login} game{name}}}}}}' % (re.sub(r"[^a-z0-9_]", "", login.lower()), first))


def parse_clips(data):
    """GQL data -> list of clip dicts {id, slug, title, views, created, dur, off, vid, vid_created, by, game}. None-safe; raises when Twitch refused (clips null)."""
    clips = ((data or {}).get("user") or {}).get("clips")
    if clips is None: raise RuntimeError("clips: null (Twitch refused the query)")
    out = []
    for e in (clips.get("edges") or []):
        n = (e or {}).get("node") or {}
        try: created = iso_epoch(n["createdAt"])
        except Exception: continue
        v = n.get("video") or {}
        try: vc = iso_epoch(v["createdAt"]) if v.get("createdAt") else None
        except Exception: vc = None
        out.append({"id": str(n.get("id")), "slug": n.get("slug") or "", "title": n.get("title") or "", "views": int(n.get("viewCount") or 0), "created": created,
                    "dur": int(n.get("durationSeconds") or 0), "off": n.get("videoOffsetSeconds"), "vid": (str(v["id"]) if v.get("id") else None), "vid_created": vc,
                    "by": ((n.get("curator") or {}).get("login") or ""), "game": ((n.get("game") or {}).get("name") or "")})
    return out


class ClipWatch:
    """v0.7: polls the viewers' Twitch clips of the channel (anonymous GQL, like the chat replay). Silent when Twitch refuses.
    v0.8: sort VIEWS_DESC (the old CREATED_AT_DESC never worked), keeps views + VOD offset: .items = {id: clip dict}, .times = {id: creation epoch}."""
    def __init__(self, channel, autostart=True):
        import threading
        self.ch = channel.lower(); self.times = {}; self.items = {}; self.ok = False; self.err = 0
        if autostart: threading.Thread(target=self.run, daemon=True).start()

    def poll(self):
        for c in parse_clips(gql(clip_query(self.ch))):
            self.items[c["id"]] = c; self.times[c["id"]] = c["created"]
        self.ok = True

    def run(self):
        while True:
            try: self.poll(); self.err = 0
            except Exception as e:
                self.err += 1
                if self.err in (1, 20): print("clipwatch:", str(e)[-80:])
            time.sleep(45)

    def day(self, now=None):
        """Clips of the last 24 h as list (the median / clip rate of the session come from here)."""
        now = now or time.time(); return [c for c in self.items.values() if now - c["created"] <= 86400]


def with_profile(ch):
    """Channel entry + profile defaults (explicit fields in the entry win)."""
    return {**PROFILES.get(str(ch.get("profile", "gaming")).lower(), PROFILES["gaming"]), **ch}


BOT_NAMES = {"streamlabs", "streamelements", "nightbot", "moobot", "fossabot", "wizebot", "sery_bot", "soundalerts", "pretzelrocks", "botrix", "lumiastream",
             "coebot", "deepbot", "ankhbot", "vivbot", "restreambot", "tangiabot", "streamcaptainbot", "commanderroot", "stay_hydrated_bot", "streamholics"}
CHEER_RE = re.compile(r"(?i)\b(?:cheer|doodlecheer|biblethump|corgo|uni|showlove|party|pride|bitboss|charity|holidaycheer|streamlabs|muxy|kappa|4head|trihard|kreygasm|swiftrage|seemsgood|cheerwhal|shamrock|anon)\d{1,6}\b")
ALERT_RE = re.compile(r"(?i)\b(?:just (?:subscribed|resubscribed|donated|tipped|followed|cheered)|(?:has|have) (?:subscribed|gifted|donated|tipped|cheered)|gifted \d+ (?:subs?|subscriptions?)|is gifting \d+|donated \$|tipped \$|cheered \d+ bits|is now raiding)\b")
USERNOTICE_ALERTS = {"subgift", "submysterygift", "anonsubgift", "anonsubmysterygift", "raid", "giftpaidupgrade", "anongiftpaidupgrade"}  # plain sub/resub are too frequent in big chats


def classify(login, text, bits=0):
    """None = ordinary viewer message. Else the alert type: bot (alert bot / chat bot), cmd (!command), cheer (bits), alert (bot-style sub / donation line)."""
    l = (login or "").lower().strip(); t = (text or "").strip()
    if l in BOT_NAMES or l.endswith("bot"): return "bot"
    if t.startswith("!"): return "cmd"
    if bits or CHEER_RE.search(t): return "cheer"
    if ALERT_RE.search(t): return "alert"
    return None


def parse_irc(line):
    """One raw IRC line (bytes, with the twitch.tv/tags capability) -> (command, login, text, tags)."""
    s = line.decode("utf-8", "replace"); tags = {}
    if s.startswith("@"):
        raw, _, s = s.partition(" "); tags = dict(x.partition("=")[::2] for x in raw[1:].split(";"))
    login = ""
    if s.startswith(":"):
        pre, _, s = s.partition(" "); login = pre[1:].split("!")[0]
    cmd, _, rest = s.partition(" ")
    return cmd, login, (rest.partition(" :")[2] if " :" in rest else ""), tags


def stalled(now, newest_mtime, started, stall=120):
    """Recorder watchdog: True when nothing was written for `stall` seconds (newest piece untouched, or no piece at all since the start)."""
    return now - max(newest_mtime or 0.0, started) > stall


AD_RE = re.compile(r'stitched-ad|X-TV-TWITCH-AD|twitch-ad-quartile|CLASS="twitch-ad|twitch-ad-signal', re.I)


def is_ad_playlist(text):
    """Twitch marks server-side inserted ads in the live HLS media playlist (DATERANGE class twitch-stitched-ad ...). Live streams only."""
    return bool(AD_RE.search(text or ""))


class AdWatch:
    """Polls the HLS media playlist every 5 s; ranges = recording seconds (since t0) during which an ad break ran."""
    def __init__(self, url, t0=None):
        import threading
        self.url = url; self.t0 = t0 or time.time(); self.ranges = []; self.open = None
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        import urllib.request
        while True:
            try:
                ad = is_ad_playlist(urllib.request.urlopen(self.url() if callable(self.url) else self.url, timeout=15).read().decode("utf-8", "replace")); k = time.time() - self.t0
                if ad and self.open is None: self.open = k; print(f"   ad break started at {k:.0f} s")
                elif not ad and self.open is not None: self.ranges.append((self.open, k)); print(f"   ad break ended ({k - self.open:.0f} s)"); self.open = None
            except Exception: pass
            time.sleep(5)

    def hit(self, a, b, pad=8):
        r = self.ranges + ([(self.open, time.time() - self.t0)] if self.open is not None else [])
        return any(x - pad <= b and y + pad >= a for x, y in r)


SELFHARM_RE = re.compile(r"(?i)\b(?:kill(?:ing)? my ?self|kill your ?self|kys|kms|suicid\w*|end it all|end my life|cut(?:ting)? my ?self|hang(?:ing)? my ?self|self[- ]?harm\w*|(?:want|wanna|going) to die|wanna die|off my ?self|slit my)\b")


def selfharm(text):
    return bool(SELFHARM_RE.search(text or ""))


def speech_rate(words, a, b):
    """Spoken words per second in [a, b] of the moment."""
    return sum(1 for w in words if a <= w["s"] <= b) / max(b - a, 1.0)


def fill_gap(db, idx, expect):
    """A piece with number idx arrived while `expect` was next: the recorder was restarted, pad the lost minutes with silence so db stays time-aligned."""
    if idx > expect: db += [-60.0] * (SEG * (idx - expect))
    return max(expect, idx + 1)


class Chat:
    """Twitch chat speed, read anonymously (no login, read-only): chatters per second since the recording started.
    A burst of chat is the classic sign that something clip-worthy just happened - but alerts (bits, donations, gift subs, bots) also make bursts.
    v0.4: alert / bot / command messages are NOT counted (kept in .alerts), and a window counts DISTINCT chatters. legacy=True = the old plain message count."""
    def __init__(self, channel, legacy=False):
        import threading
        self.t0 = time.time(); self.ch = channel.lower(); self._state(legacy)
        threading.Thread(target=self.run, daemon=True).start()

    def _state(self, legacy=False):
        self.n = {}; self.u = {}; self.kw = {}; self.alerts = {}; self.kinds = {}; self.ok = False; self.legacy = legacy

    def add(self, k, login, text, bits=0, kind=None):
        kind = kind or classify(login, text, bits)
        if kind and not self.legacy:
            self.alerts[k] = self.alerts.get(k, 0) + 1; self.kinds[kind] = self.kinds.get(kind, 0) + 1; return
        self.n[k] = self.n.get(k, 0) + 1; self.u.setdefault(k, set()).add((login or "").lower()); self.ok = True
        if hype_msg(text): self.kw[k] = self.kw.get(k, 0) + 1

    def run(self):
        import socket
        while True:
            try:
                so = socket.create_connection(("irc.chat.twitch.tv", 6667), timeout=30); so.settimeout(330)
                so.sendall(f"CAP REQ :twitch.tv/tags twitch.tv/commands\r\nNICK justinfan{int(time.time()) % 89999 + 10000}\r\nJOIN #{self.ch}\r\n".encode()); buf = b""
                while True:
                    d = so.recv(4096)
                    if not d: break
                    buf += d; lines = buf.split(b"\r\n"); buf = lines.pop()
                    for l in lines:
                        if l.startswith(b"PING"): so.sendall(b"PONG :tmi.twitch.tv\r\n"); continue
                        k = int(time.time() - self.t0)
                        if b" PRIVMSG #" in l:
                            _, login, text, tags = parse_irc(l)
                            try: bits = int(tags.get("bits") or 0)
                            except ValueError: bits = 0
                            self.add(k, login, text, bits)
                        elif b" USERNOTICE #" in l:
                            _, login, text, tags = parse_irc(l)
                            if tags.get("msg-id") in USERNOTICE_ALERTS: self.add(k, login, text, kind="usernotice")
            except Exception as e:
                print("chat reconnect:", str(e)[-80:])
            time.sleep(5)

    def _windows(self, lo, upto, win):
        import numpy as np
        if self.legacy:
            c = np.array([self.n.get(k, 0) for k in range(lo, upto)], dtype=np.float32); return np.convolve(c, np.ones(win), mode="valid")
        out = []
        for i in range(lo, upto - win + 1):
            s = set()
            for k in range(i, i + win): s.update(self.u.get(k, ()))
            out.append(len(s))
        return np.array(out, dtype=np.float32)

    def peak(self, upto, win=15, base=600):
        """(ratio, position): busiest 15 s of the newest 3 minutes against the median 15 s of the last 10 minutes (distinct chatters, alerts excluded)."""
        import numpy as np
        if not self.ok or upto < 150: return 0.0, None
        lo = max(0, upto - base); w = self._windows(lo, upto, win)
        if len(w) < 60: return 0.0, None
        med = float(np.median(w))
        if med < 3: return 0.0, None  # chat too quiet to say anything
        k0 = max(0, len(w) - 180); i = k0 + int(np.argmax(w[k0:]))
        return round(float(w[i]) / med, 2), lo + i - 4  # people type a few seconds after the moment

    def kw_share(self, cp, before=20, after=5):
        """v0.7: share of the messages in [cp - before, cp + after] that carry hype words (KEKW, LUL, 💀, CLIP IT, W ...)."""
        r = range(max(cp - before, 0), cp + after); m = sum(self.n.get(k, 0) for k in r)
        return (sum(self.kw.get(k, 0) for k in r) / m) if m >= 8 else 0.0

    def alert_near(self, cp, before=35, after=5):
        """(alert events, distinct chatters) in [cp - before, cp + after]: a burst that is mostly an alert chain is no moment."""
        a = sum(self.alerts.get(k, 0) for k in range(max(cp - before, 0), cp + after)); s = set()
        for k in range(max(cp - before, 0), cp + after): s.update(self.u.get(k, ()))
        return a, len(s)


class ReplayChat(Chat):
    """Chat of a past Twitch VOD (GQL "VideoCommentsByOffsetOrCursor", anonymous): n[k] = messages in second k of the recording
    (recording second 0 = VOD second `start`). Same interface as Chat, so the detection code does not know the difference.
    .msgs keeps every message, view(legacy) rebuilds the counters (old plain count vs v0.4 filtered) without a second download."""
    HASH = "b70a3591ff0f4e0313d126c6a1502d79a1c02baebb288227c582044aa76adf6a"

    def __init__(self, vid, start, dur, legacy=False):
        self._state(legacy); self.ch = "vod" + str(vid); self.total = 0; self.msgs = []
        import urllib.request
        end = start + dur; offs = int(start); seen = set(); tries = 0  # cursor paging fails the integrity check, offset paging works (~58 msgs per call)
        while offs < end and tries < 3000:
            body = json.dumps([{"operationName": "VideoCommentsByOffsetOrCursor", "variables": {"videoID": str(vid), "contentOffsetSeconds": int(offs)},
                                "extensions": {"persistedQuery": {"version": 1, "sha256Hash": self.HASH}}}]).encode()
            try:
                r = urllib.request.Request("https://gql.twitch.tv/gql", body, {"Client-ID": "kimne78kx3ncx6brgo4mv6wki5h1ko", "Content-Type": "application/json"})
                c = json.load(urllib.request.urlopen(r, timeout=30))[0]["data"]["video"]["comments"]
                ed = c["edges"] or []
            except Exception as e:
                tries += 20; print("chat replay retry:", str(e)[-80:]); time.sleep(3); continue
            tries += 1; last = offs
            for e in ed:
                nd = e["node"]; o = nd["contentOffsetSeconds"]; last = max(last, o)
                if nd["id"] in seen: continue
                seen.add(nd["id"])
                if start <= o < end:
                    self.msgs.append((int(o - start), ((nd.get("commenter") or {}).get("login") or ""),
                                      "".join(f.get("text") or "" for f in ((nd.get("message") or {}).get("fragments") or []))))
                    self.total += 1
            if not ed: offs += 30
            else: offs = last if last > offs else offs + 1
        self._fill(); print(f"chat replay: {self.total} messages in {dur} s ({tries} requests); alerts/bots filtered: {sum(self.kinds.values())} {self.kinds}")

    def _fill(self):
        for k, l, t in self.msgs: self.add(k, l, t)
        self.ok = self.total > 0

    def view(self, legacy):
        c = object.__new__(ReplayChat); c.ch = self.ch; c.total = self.total; c.msgs = self.msgs; c._state(legacy); c._fill(); return c


def iso_utc(epoch):
    return datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).isoformat(timespec="seconds")


def clip_moment(c, lag=12.0):
    """Recording-clock epoch of the moment inside a viewer clip (same clock as t_rec + peak of a live entry).
    Stream time of the clip start = VOD creation + videoOffsetSeconds (checked 19.11. on the pair 'studio' 14:35:11 vs live moment 14:35:39: they overlap);
    the moment sits ~70 % into the clip; the recorded stream runs ~`lag` s behind stream time. Without a consistent VOD offset: click time - 4 s."""
    cr, dur = c["created"], max(int(c.get("dur") or 0), 5)
    if c.get("vid_created") and c.get("off") is not None:
        st = c["vid_created"] + float(c["off"])
        if abs((st + dur) - cr) <= 180: return st + 0.7 * min(dur, 30) + lag
    return cr - 4


def entry_moment(e):
    """(epoch, tolerance in s) of an inbox entry on the recording clock. New entries carry moment_utc; old ones (19.11.) only the stamp: ~60 s before it, +-120 s."""
    try: return iso_epoch(e["moment_utc"]), 0
    except Exception: pass
    try: return datetime.datetime.strptime(str(e["id"])[:15], "%Y%m%d-%H%M%S").replace(tzinfo=datetime.timezone.utc).timestamp() - 60, 120
    except Exception: return None, 0


def top_candidates(items, now, entries, done_ids=(), rel=1.5, min_views=40, window_h=4.0, min_age=90, game="grand theft auto", dedupe_s=60, lag=12.0, min_day=8):
    """v0.8 top-clip mode: the viewers' clips worth taking, best viewed first. items = ClipWatch clip dicts, entries = inbox.json.
    A clip counts when it is <= window_h old (views arrive late: it is re-checked on every pass), older than min_age s, of the right game, has
    views >= max(min_views, rel x median views of the channel's clips of the last 24 h) (relative to the session, not absolute), is not in the inbox yet
    (clip_id), and its moment is not within +-dedupe_s of a moment we already have. One per cluster (the best viewed)."""
    import statistics
    day = [c for c in items if now - c["created"] <= 86400]
    med = statistics.median([c["views"] for c in day]) if len(day) >= min_day else 0.0
    need = max(min_views, rel * med)
    known = {str(e.get("clip_id")) for e in entries if e.get("clip_id")} | {str(x) for x in done_ids}
    have = [m for m in (entry_moment(e) for e in entries) if m[0] is not None]
    out = []
    for c in sorted(day, key=lambda x: -x["views"]):
        age = now - c["created"]
        if age > window_h * 3600 or age < min_age or c["views"] < need or c["id"] in known: continue
        if game and c.get("game") and game not in c["game"].lower(): continue
        m = clip_moment(c, lag)
        if any(abs(m - t) <= dedupe_s + tol for t, tol in have + [(o["moment"], 0) for o in out]): continue
        out.append({**c, "moment": m, "rel": round(c["views"] / med, 2) if med else None, "median": med})
    return out


def _gray_frames(path, vf, w, h, fps):
    import numpy as np
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-an", "-vf", f"fps={fps},{vf},scale={w}:{h}:flags=area,format=gray", "-f", "rawvideo", "-"], capture_output=True, timeout=300)
    a = np.frombuffer(r.stdout, dtype=np.uint8); n = len(a) // (w * h)
    return a[:n * w * h].reshape(n, h, w).astype(np.float32)


def letterbox_share(path):
    """Share (0-1) of sampled frames (2 per second, centre columns - Kai's cam and the chat sit at the left edge) with cinematic black bars at the top or bottom edge.
    Measured 19.11. on the 23 raws: cutscenes 0.48-0.82, alligator 0.18, everything else <= 0.15. Dark night scenes must not count: the picture just inside the bar has to be clearly brighter."""
    try: f = _gray_frames(path, "crop=iw*0.62:ih:iw*0.22:0", 124, 108, 2)
    except Exception: return 0.0
    if not len(f): return 0.0
    top, bot = f[:, 0:4, :].mean(axis=(1, 2)), f[:, -4:, :].mean(axis=(1, 2)); ti, bi = f[:, 9:15, :].mean(axis=(1, 2)), f[:, -15:-9, :].mean(axis=(1, 2))
    return round(float((((top < 5) & (ti > top + 14)) | ((bot < 5) & (bi > bot + 14))).mean()), 2)


def speech_density(words, a, b):
    """Words per second in [a, b]. Scripted game dialogue / monologue is dense (>= 2.9 w/s on the 19.11. testset), Kai's own talking is looser."""
    return round(sum(1 for w in words if a <= w["s"] <= b) / max(b - a, 1.0), 2)


def cutscene_flags(lbx, dens, lbx_min=0.4, dens_min=2.9):
    """0-2: cinematic bars + dense speech. A score penalty and a hint for the agent, never a reason to drop an entry."""
    return int(lbx >= lbx_min) + int(dens >= dens_min)


def contact_sheet(path, dst, dur, n=8, cols=4, w=480):
    """One picture with n frames spread over the raw clip (4 x 2 tiles). The hourly agent looks at this instead of a single QA frame."""
    rows = -(-n // cols)
    try:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", path, "-vf", f"fps={n}/{max(dur, 1.0):.3f},scale={w}:-2,tile={cols}x{rows}:padding=3:color=black", "-frames:v", "1", "-q:v", "4", dst], check=True, timeout=120)
        return os.path.exists(dst)
    except Exception as e:
        print("WARN no contact sheet:", str(e)[-120:]); return False


def transcript_text(sents, limit=2400):
    """Whole transcript of the raw clip with raw-relative seconds ('12: sentence | 15: ...'), cut at `limit` characters."""
    t = " | ".join(f"{int(s['s'])}: {s['text']}" for s in sents)
    return t if len(t) <= limit else t[:limit - 1] + "…"


def fetch_clip(slug, dst, timeout=150):
    """Viewer clip (clips.twitch.tv/<slug>) -> dst (mp4, <= 720p, with sound) through yt-dlp. Raises on failure."""
    slug = re.sub(r"[^A-Za-z0-9_-]", "", slug or "")
    if not slug: raise RuntimeError("no clip slug")
    r = subprocess.run(["yt-dlp", "--no-warnings", "-q", "--no-playlist", "-f", "best[height<=720]/best", "-o", dst, f"https://clips.twitch.tv/{slug}"], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0 or not os.path.exists(dst) or os.path.getsize(dst) < 20000: raise RuntimeError("clip download: " + (r.stderr.strip().split("\n") or [""])[-1][:160])
    return dst


def vod_section(vid, a, b, dst, timeout=120):
    """Seconds [a, b] of a Twitch VOD (also the running broadcast's archive) -> dst (h264). False when it fails or is too slow (seeking far into a long playlist can take minutes)."""
    try:
        hls = live_url(f"https://www.twitch.tv/videos/{vid}", 720)
        if not hls: return False
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{max(a, 0):.2f}", "-i", hls, "-t", f"{b - a:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                        "-c:a", "aac", "-b:a", "128k", dst], check=True, timeout=timeout)
        return os.path.exists(dst) and os.path.getsize(dst) > 50000
    except Exception as e:
        print("WARN vod section failed:", str(e)[-120:])
        if os.path.exists(dst): os.remove(dst)
        return False


def viewer_raw(c, tmp, rec=None, vod=False, extend_below=22, pre=12, post=15):
    """Raw for a new inbox entry from a viewer clip. Order: (1) the moment lies inside the running recording (the 35 min buffer): cut PRE_S before / POST_S after from it - fast, exact,
    and Kai's reaction is in; (2) the viewer clip itself (yt-dlp, <= 720p); (3) only with vod=True and a clip shorter than `extend_below` s: stretched from the VOD
    (measured 19.11.: a section far into a long running VOD took > 100 s, so it is off by default). rec = (segs, t_rec, seconds recorded so far[, AdWatch]):
    the runner sees Twitch's ad breaks (about a sixth of the time on 19.11.), so a window that touches one is NOT cut from the recording - the viewer clip is taken instead.
    Returns (raw path, position of the moment inside it, source)."""
    if rec:
        segs, t_rec, ready = rec[:3]; ads = rec[3] if len(rec) > 3 else None; pos = c["moment"] - t_rec
        if ads is not None and pos - PRE_S >= 0 and ads.hit(pos - PRE_S, pos + POST_S): print("   top clip: ad break in the recording window -> viewer clip itself")
        elif pos - PRE_S >= 0 and pos + POST_S <= ready:
            try:
                dst = os.path.join(tmp, "viewer_rec.mp4"); cut(segs, 0.0, pos - PRE_S, pos + POST_S, dst); return dst, float(PRE_S), "recording"
            except Exception as e: print("   top clip: recording cut not possible:", str(e)[-100:])
    clip = fetch_clip(c["slug"], os.path.join(tmp, "viewer_clip.mp4")); p = cf.probe(clip); dur = p["dur"]
    if vod and dur < extend_below and c.get("vid") and c.get("off") is not None:
        sec = os.path.join(tmp, "viewer_vod.mp4"); o = float(c["off"])
        if vod_section(c["vid"], o - pre, o + dur + post, sec):
            os.remove(clip); return sec, pre + 0.7 * dur, "vod"
    return clip, 0.7 * dur, "clip"


def cut(segs, t0, a, b, dst):
    """Seconds [a, b] of the recording (segment i holds [t0 + i*SEG, ...)) -> one mp4."""
    i0, i1 = int((a - t0) // SEG), int((b - t0) // SEG); files = [segs[i] for i in range(i0, i1 + 1) if i in segs]
    if not files: raise cf.Fail("recording for that moment is gone")
    if i0 not in segs or any(i not in segs for i in range(i0, i1)):  # 16.11. review: a hole shifted the timecode silently (recorder restart)
        raise cf.Fail("recording gap at the moment")
    lst = dst + ".txt"; open(lst, "w").write("".join(f"file '{f}'\n" for f in files))
    off = a - (t0 + i0 * SEG)
    cf.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-ss", f"{off:.2f}", "-t", f"{b - a:.2f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-c:a", "aac", "-b:a", "192k", dst], timeout=900)
    os.remove(lst); return cf.probe(dst)


def make_clip(ch, root, segs, t0, peak, hype, stamp, raw_in=None, pk_in=None, gates=True, extra=None):
    """Cut PRE_S before / POST_S after the peak (v0.8: the reaction comes after the event), transcribe, pick whole sentences around the peak, render. Returns inbox entry.
    raw_in = a ready file (viewer clip) with the moment at pk_in s: no cutting, and gates=False skips the speech gates (a viewer clip is proof enough); self-harm stays checked.
    extra = fields for the entry (kind, score, ...). Per entry the repo gets: the raw (h264 crf 24), the QA picture, a contact sheet; NO preview mp4 any more (v0.8, halves the bytes)."""
    name = "live-" + re.sub(r"[^a-z0-9-]", "", ch["name"].lower()); out = os.path.join(root, "clips", name); os.makedirs(out, exist_ok=True)
    tmp = os.path.join(os.environ.get("RUNNER_TEMP", "/tmp"), "lw_" + name); os.makedirs(tmp, exist_ok=True)
    if raw_in:
        raw = raw_in; p = cf.probe(raw); pk = float(pk_in if pk_in is not None else p["dur"] * 0.7)
        if p["dur"] < 10: raise cf.Fail(f"viewer clip too short ({p['dur']:.0f} s)")
    else:
        a0, b0 = max(peak - int(ch.get("pre_s", PRE_S)), t0), peak + int(ch.get("post_s", POST_S)); raw = os.path.join(tmp, "moment.mp4"); p = cut(segs, t0, a0, b0, raw); pk = peak - a0
    words = []
    try: words = cf.transcribe(cf.audio16k(raw, tmp), ch.get("whisper", "small.en")) if p["audio"] else []
    except Exception as e: print("WARN no transcript:", str(e)[-200:])
    inwin = [w for w in words if pk - 20 <= w["s"] <= pk + 12]
    if gates and len(inwin) < 12: raise cf.Fail(f"too little speech around the moment ({len(inwin)} words): ad break / music / silence")  # v0.3 16.11.: Twitch ad break fired the chat+loud signal
    if not ch.get("legacy") and selfharm(" ".join(w["w"] for w in words)): raise cf.Fail("self-harm wording in the moment")  # v0.4: campaign rule, never post these
    sents = cf.sentences(words)
    cands = [c for c in cf.candidates(sents, [], p["dur"], 6, 12, 34) if c["a"] <= pk <= c["b"]] if sents else []
    if cands: c = max(cands, key=lambda x: x["score"]); a, b = c["a"], c["b"]
    else: a, b = max(pk - 12, 0), min(pk + 20, p["dur"])
    if b - a < 10: a, b = max(min(a, p["dur"] - 10), 0), min(max(b, 10), p["dur"])  # clipfabrik wants >= 10 s
    if gates and not ch.get("legacy") and speech_rate(words, a, b) < 0.8: raise cf.Fail("almost no speech in the cut: walking / driving scene")  # v0.4
    said = next((s["text"] for s in sents if s["s"] - 0.5 <= pk <= s["e"] + 1.5), "")
    title = ""
    for w in re.sub(r"[^A-Za-z0-9' ]", "", said).upper().split():
        if len(title) + len(w) + 1 > 26: break
        title = (title + " " + w).strip()
    # v0.2 (15.11.): viral style = whole picture + one sentence. The preview only quotes what was said; the agent writes the real
    # context sentence and re-renders through the Clipfabrik from the RAW moment (kept as raw_<stamp>.mp4, source of a clipjob).
    quote = ('"' + title.capitalize() + '"') if title else "Live moment"
    cap = ch.get("caption")  # v0.6 (18.11.): fixed fallback sentence per channel (campaign rule: streamer name in the overlay); a list rotates by clip
    if cap: quote = cap if isinstance(cap, str) else cap[sum(map(ord, stamp)) % len(cap)]
    job = {"name": name, "layout": ch.get("layout", "native"), "fix": ch.get("fix") or {}, "_logo_img": None}
    if ch.get("crop"): job["crop"] = ch["crop"]  # v0.6: [x, y, w, h] fractions that stay (clipfabrik v6) - cuts an overlay at the edge off the direct clip too
    clip = {"id": stamp, "a": round(a, 2), "b": round(b, 2), "caption": quote}
    r = cf.render_clip(job, clip, raw, p, words, out, tmp)
    lbx = letterbox_share(raw); dens = speech_density(words, a, b); cut_flag = cutscene_flags(lbx, dens)
    sheet = f"sheet_{stamp}.jpg" if (not ch.get("legacy") and contact_sheet(raw, os.path.join(out, f"sheet_{stamp}.jpg"), p["dur"])) else None
    rawname = f"raw_{stamp}.mp4"
    if not ch.get("keep_preview"): os.remove(os.path.join(out, r["file"]))  # v0.8: the preview (a standard line, never posted) was ~half of the bytes per entry
    if ch.get("legacy"):  # comparison run (old settings): only the QA picture + text stay, no video in the repo
        os.remove(raw); rawname = None
    else:
        cf.run(["ffmpeg", "-y", "-v", "error", "-i", raw, "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart",
                os.path.join(out, rawname)]); os.remove(raw)
    rawurl = f"{cf.RAW}/clips/{name}/{rawname}" if rawname else None
    entry = {"id": stamp, "at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "channel": ch["name"],
             "hype": round(hype, 1), "seconds": r["seconds"], "quote": quote, "a": clip["a"], "b": clip["b"], "raw": rawurl, "said": " ".join(w["w"] for w in words if a <= w["s"] <= b)[:500],
             "url": (f"{cf.RAW}/clips/{name}/{r['file']}" if ch.get("keep_preview") else rawurl), "qa": f"{cf.RAW}/clips/{name}/{r['qa']}", "posted": False,
             "sheet": (f"{cf.RAW}/clips/{name}/{sheet}" if sheet else None), "transcript": transcript_text(sents), "raw_seconds": round(p["dur"], 1),
             "letterbox": lbx, "speech_density": dens, "cutscene": cut_flag}
    entry.update(extra or {})
    if "score" in entry: entry["score_raw"] = entry["score"]; entry["score"] = round(float(entry["score"]) - 1.5 * cut_flag, 2)  # cutscene = demoted, not dropped
    return entry, name


def posted_ids(root, name):
    """v0.6: the launch watch (an agent) never edits inbox.json (the runner appends to it every few minutes -> merge conflicts); it drops
    clips/live-<name>/posted/<id>.json instead. A clip counts as posted when its entry says so OR such a marker exists."""
    d = os.path.join(root, "clips", name, "posted")
    try: return {os.path.splitext(f)[0] for f in os.listdir(d) if f.endswith(".json")}
    except OSError: return set()


def publish(root, name, entry, push):
    ip = os.path.join(root, "clips", name, "inbox.json")
    try: box = json.load(open(ip))
    except Exception: box = []
    done = posted_ids(root, name)
    for e in box:
        if e.get("id") in done: e["posted"] = True  # fold the markers into the inbox (the runner is its only writer)
    box.append(entry); json.dump(box[-100:], open(ip, "w"), indent=1, ensure_ascii=False)  # v0.8: 100 (was 40): the top-clip dedupe (clip_id, moment_utc) reads this list; 40 covered < 4 h at 10+ entries/h
    if not push: return
    g = lambda *a: subprocess.run(["git", "-C", root, *a], capture_output=True, text=True)
    g("add", "-A", f"clips/{name}"); g("commit", "-q", "-m", f"livewatch: {name} {entry['id']} (hype {entry['hype']})")
    for i in range(4):
        if g("pull", "-q", "--rebase", "origin", "main").returncode == 0 and g("push", "-q", "origin", "HEAD:main").returncode == 0:
            print("PUBLISHED", entry["url"]); return
        time.sleep(6)
    print("WARN push failed for", entry["id"])


def save_calib(root, ch, data, push):
    """Calibration run ("log_only": true): no clips, only what was measured -> clips/live-<name>/calib.json."""
    name = "live-" + re.sub(r"[^a-z0-9-]", "", ch["name"].lower()); d = os.path.join(root, "clips", name); os.makedirs(d, exist_ok=True)
    json.dump(data, open(os.path.join(d, "calib.json"), "w"), indent=1)
    if not push: return
    g = lambda *a: subprocess.run(["git", "-C", root, *a], capture_output=True, text=True)
    g("add", "-A", f"clips/{name}"); g("commit", "-q", "-m", f"livewatch: calibration {name} ({len(data['events'])} events)")
    for i in range(3):
        if g("pull", "-q", "--rebase", "origin", "main").returncode == 0 and g("push", "-q", "origin", "HEAD:main").returncode == 0: return
        time.sleep(6)


def top_pass(ch, root, clipw, push, state, now=None, rec=None):
    """v0.8 top-clip mode, one pass: takes the best viewed NEW viewer clip(s) of the channel (see top_candidates), downloads them (yt-dlp, stretched from the VOD when short)
    and files them as inbox entries `kind: viewer-top` (views, clip_title, clip_id ...). Returns how many entries were made. Never raises."""
    now = now or time.time(); name = "live-" + re.sub(r"[^a-z0-9-]", "", ch["name"].lower()); made = 0
    try:
        try: box = json.load(open(os.path.join(root, "clips", name, "inbox.json")))
        except Exception: box = []
        hour = sum(1 for e in box if e.get("kind") == "viewer-top" and now - iso_epoch(e.get("at", "1970-01-01T00:00:00+00:00")) < 3600)
        room = int(ch.get("top_per_hour", 4)) - hour
        if room <= 0: return 0
        cands = top_candidates(clipw.day(now), now, box, state["made"], rel=float(ch.get("top_rel", 1.5)), min_views=int(ch.get("top_min_views", 40)),
                               window_h=float(ch.get("top_window_h", 4.0)), lag=float(ch.get("stream_lag_s", 12.0)))
        cands = [c for c in cands if c["id"] not in state["failed"]]
        if cands: print(f"   top clips: {len(cands)} candidate(s), best '{cands[0]['title'][:40]}' {cands[0]['views']} views (x{cands[0]['rel']} median)")
        tmp = os.path.join(os.environ.get("RUNNER_TEMP", "/tmp"), "lw_top"); os.makedirs(tmp, exist_ok=True)
        for c in cands[:min(room, int(ch.get("top_per_pass", 1)))]:
            stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
            try:
                raw, pk, src = viewer_raw(c, tmp, rec=rec, vod=bool(ch.get("top_vod", False)))
                entry, nm = make_clip(ch, root, {}, 0.0, 0.0, 0.0, stamp, raw_in=raw, pk_in=pk, gates=False,
                                      extra={"kind": "viewer-top", "score": round(3.0 + min(c["rel"] or 0, 10) / 2, 2), "views": c["views"], "clip_title": c["title"], "clip_id": c["id"],
                                             "clip_url": f"https://clips.twitch.tv/{c['slug']}", "clip_by": c["by"], "clip_s": c["dur"], "moment_utc": iso_utc(c["moment"]), "chat": 0.0, "raw_from": src})
                publish(root, nm, entry, push); state["made"].add(c["id"]); made += 1
            except Exception as e:
                state["failed"].add(c["id"]); print("WARN top clip failed:", c["id"], str(e)[-240:])
            finally:
                for f in glob.glob(os.path.join(tmp, "*")):
                    try: os.remove(f)
                    except OSError: pass
    except Exception as e: print("WARN top pass:", str(e)[-200:])
    return made


def loop(ch, root, rec, alive, push, t_end, chat=None, ads=None, keep=False, clipw=None, t_rec=None):
    """Shared by watch and simulate: rec = folder that fills with %05d.ts pieces, alive() = recorder still running.
    ads = AdWatch (live only), keep = leave the pieces on disk (comparison runs read the same recording twice).
    v0.7 (19.11.): clipw = ClipWatch (viewers' clips, live only), t_rec = recording start epoch; chat words, voice outburst, safety net (see below)."""
    ch = with_profile(ch); skipped = {"alert": 0, "ad": 0}; expect = 0
    db, segs, done, clips, last = [], {}, 0, [], -999.0; t0 = 0.0; safe_last = -999
    dry = bool(ch.get("log_only")); cal = {"channel": ch["name"], "started": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                                           "minutes": [], "events": []}
    min_chat = float(ch.get("min_chat", 3.0)); co_chat = float(ch.get("co_chat", 2.0))  # calibrated 15.11.2026 (98 min, 2 channels): 2.5/1.4 fired every 4.6 min
    alert_max = int(ch.get("alert_max", 3)); warm = int(ch.get("warmup_s", 480))  # no clip in the first 8 min of a recording (chat/loudness baseline still forming)
    safety_s = int(ch.get("safety_s", 1800)); cands = []; keep_min = 35 if safety_s else 15  # v0.7: nothing for safety_s -> best-scored moment of that time
    min_burst = float(ch.get("min_burst", 9.0)); post_s = int(ch.get("post_s", POST_S))
    min_hype = float(ch.get("min_hype", 9)); per_hour = int(ch.get("per_hour", 3)); max_clips = int(ch.get("max_clips", 8))
    top_n = 0; top_state = {"last": 0.0, "failed": set(), "made": set()}; top_every = int(ch.get("top_every_s", 240))  # v0.8 top-clip mode (viewer clips by views)
    while time.time() < t_end:
        files = sorted(glob.glob(os.path.join(rec, "*.ts"))); run = alive()
        ready = files if not run else files[:-1]  # the newest piece is still being written
        for f in ready[done:]:
            i = int(os.path.basename(f)[:5]); segs[i] = f; d = seg_db(f); expect = fill_gap(db, i, expect)  # restarted recorder: keep db time-aligned
            db += d + [-60.0] * max(0, SEG - len(d)) if run or f != files[-1] else d
            done += 1
            hype, peak = find_peak(db)
            recent = [c for c in clips if c > len(db) - 3600]
            cr, cp = chat.peak(len(db)) if chat else (0.0, None); lag = None; kind = "loud"
            cal["minutes"].append({"min": done, "hype": round(hype, 1), "chat": cr, "msgs": sum(chat.n.get(k, 0) for k in range(len(db) - 60, len(db))) if chat else None})
            print(f"min {done:3d} hype {hype:4.1f} peak {peak} chat x{cr} at {cp}")
            if len(db) < warm and not ch.get("legacy"):  # live test 16.11.: 3 clips in the first 9 min (baseline of the young recording is unstable, expected ~0.5 at 3/h)
                hype, peak, cr, cp = 0.0, None, 0.0, None
            burst, bp = (find_outburst(db) if not ch.get("legacy") else (0.0, None)); vcn, vcp = 0, None; score = 0.0
            if len(db) < warm and not ch.get("legacy"): burst, bp = 0.0, None
            if clipw and clipw.ok and t_rec and not ch.get("legacy") and len(db) >= warm:  # v0.8: weighed by views and against the channel's usual clip rate
                day = clipw.day(); med = sorted(c["views"] for c in day)[len(day) // 2] if len(day) >= 8 else 0
                rate = len([c for c in day if time.time() - c["created"] <= 6 * 3600]) / (6 * 3600.0)
                vcn, vcp = clip_cluster([(c["created"], c["views"]) for c in day], t_rec, len(db), min_sum=float(ch.get("vc_rel", 3.0)) * med, base_rate=rate)
            if chat and chat.ok and cp is not None and not chat.legacy:  # v0.7: hype words in the chat raise the ratio (up to x1.6)
                sh = chat.kw_share(cp); cr = round(cr * chat_boost(sh), 2)
                if sh >= 0.25: print(f"   chat words {sh:.0%} hype -> ratio x{cr}")
            if not ch.get("legacy"):  # v0.7: one comparable total score per minute (safety net + log)
                score = round(hype / max(min_hype, 1) + cr / max(min_chat, 0.1) + burst / max(min_burst, 1) + 2.0 * (vcn >= 2), 2)
                if peak is not None and len(db) >= warm: cands.append((score, int(peak), done))
                if burst >= min_burst or vcn >= 2: print(f"   outburst {burst} dB at {bp} | viewer clips x{vcn} at {vcp} | score {score}")
            if vcn >= 2 and vcp is not None:  # strongest proof: several viewers clipped the same moment
                cr = max(cr, min_chat); cp = vcp + 18; peak, hype = vcp, max(hype, min_hype); kind = "viewer-clips"; print(f"   viewers clipped it x{vcn}: moment at {vcp}")
            elif chat and chat.ok:  # with a chat signal: a chat burst decides; loudness alone needs at least a busier chat
                al, us = chat.alert_near(cp) if (cp is not None and cr >= min_chat) else (0, 0)
                if cp is not None and cr >= min_chat and not chat.legacy and al >= alert_max and al >= 0.25 * us:
                    skipped["alert"] += 1; peak = None; print(f"   chat burst x{cr} skipped: alert chain ({al} alerts vs {us} chatters)")
                elif cp is not None and cr >= min_chat:
                    # chat reacts late (stream delay + typing, measured 7-25 s, median 17): the moment is the loudest second in the 32 s before the burst
                    w0 = max(cp - 28, 0); seg_ = db[w0:cp + 5]  # measured lags 7-25 s (median 17), 25 was the old cap
                    lag = (cp + 4) - (w0 + max(range(len(seg_)), key=seg_.__getitem__)) if seg_ else 0; kind = "chat"
                    peak, hype = (max(cp + 4 - lag, 0) if seg_ else max(cp, 0)), max(hype, min_hype); print(f"   chat burst x{cr}: moment {lag:.0f} s before the chat peak")
                elif cp is not None and burst >= min_burst and bp is not None and cr >= 0.8 * co_chat and abs(cp - bp) < 30:  # v0.7: a sudden scream/laugh + a lively chat
                    peak, hype, kind = bp, max(hype, min_hype), "outburst"; print(f"   voice outburst {burst} dB + chat x{cr}: moment at {bp}")
                elif not (cp is not None and cr >= co_chat and peak is not None and abs(cp - peak) < 30): peak = None
            if dry:
                if peak is not None and hype >= min_hype and len(db) - peak >= post_s + 1 and peak - last > 90:
                    cal["events"].append({"min": done, "pos": int(peak), "kind": kind, "hype": round(hype, 1), "chat": cr, "lag": lag}); last = peak
                if done % 20 == 0: save_calib(root, ch, cal, push)
            elif peak is not None and ads and ads.hit(peak - PRE_S, peak + post_s):
                skipped["ad"] += 1; last = peak; print("   moment skipped: Twitch ad break")
            elif peak is not None and hype >= min_hype and len(db) - peak >= post_s + 1 and peak - last > 90 and len(recent) < per_hour and len(clips) < max_clips:
                stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
                try:
                    entry, name = make_clip(ch, root, segs, t0, peak, hype, stamp, extra={"kind": kind, "score": score, "chat": cr, "peak_s": int(peak),
                                                                                            **({"moment_utc": iso_utc(t_rec + peak)} if t_rec else {})}); entry["peak_s"] = int(peak)
                    if ch.get("vod"): entry["vod"] = ch["vod"]; entry["vod_s"] = int(ch.get("vod_start", 0) + peak)
                    publish(root, name, entry, push)
                    clips.append(peak); last = peak
                except Exception as e:
                    print("WARN clip failed:", str(e)[-300:]); last = peak
            anchor = max(last, warm, safe_last)  # v0.7 safety net: safety_s (30 min) without a clip -> the best-scored moment of that time becomes a candidate (the agent still looks at it)
            if safety_s and not dry and not ch.get("legacy") and len(clips) < max_clips and len(db) - anchor >= safety_s:
                pool = [c for c in cands if len(db) - safety_s <= c[1] <= len(db) - (post_s + 1) and c[1] - last > 90 and (c[1] - PRE_S) // SEG in segs]
                safe_last = len(db)
                if pool:
                    sc, sp, _ = max(pool); stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
                    print(f"   SAFETY NET: {safety_s // 60} min without a trigger -> best moment {sp} (score {sc})")
                    try:
                        entry, name = make_clip(ch, root, segs, t0, sp, max(hype, 0.0), stamp, extra={"kind": "safety", "score": sc, "chat": cr, "peak_s": int(sp), "safety": True,
                                                                                                **({"moment_utc": iso_utc(t_rec + sp)} if t_rec else {})})
                        publish(root, name, entry, push); clips.append(sp); last = sp
                    except Exception as e: print("WARN safety clip failed:", str(e)[-300:])
            if clipw and clipw.ok and not dry and not ch.get("legacy") and ch.get("top_clips", True) and len(clips) + top_n < max_clips and time.time() - top_state["last"] >= top_every:
                top_state["last"] = time.time(); top_n += top_pass(ch, root, clipw, push, top_state, rec=((segs, t_rec, len(db), ads) if t_rec else None))  # v0.8: viewer clips by views (does not need the recording)
            for j in [k for k in segs if k < i - (keep_min - 1) and not keep]:  # keep 15 minutes on disk (v0.7: 35 for the safety net)
                try: os.remove(segs.pop(j))
                except OSError: pass
        if not run and done >= len(files): break
        time.sleep(1 if not push else 20)
    print(f"LOOP_STATS {ch['name']} legacy={bool(ch.get('legacy'))} clips={len(clips)} viewer_top={top_n} skipped={skipped}")
    if dry: save_calib(root, ch, cal, push); return len(cal["events"])
    return len(clips) + top_n


class Recorder:
    """ffmpeg HLS recorder in 60 s pieces with a watchdog (v0.4): nothing written for `stall` s (ffmpeg hung after a stream restart / game switch) ->
    kill it, fetch a fresh HLS url and carry on with the piece number of the current stream time (loop pads the lost minutes)."""
    def __init__(self, ch, rec, stall=120, max_restarts=6):
        self.ch = ch; self.rec = rec; self.stall = stall; self.max = max_restarts; self.restarts = 0
        self.t_start = time.time(); self.pr = None; self.hls = None; self.started = 0.0

    def start(self, idx=0):
        self.hls = live_url(self.ch["url"], int(self.ch.get("height", 720)))
        if not self.hls: return False
        self.pr = subprocess.Popen(["ffmpeg", "-v", "error", "-i", self.hls, "-c", "copy", "-f", "segment", "-segment_time", str(SEG), "-reset_timestamps", "1",
                                    "-segment_start_number", str(idx), os.path.join(self.rec, "%05d.ts")])
        self.started = time.time(); return True

    def files(self): return sorted(glob.glob(os.path.join(self.rec, "*.ts")))

    def alive(self):
        if self.pr is None: return False
        files = self.files(); newest = max((os.path.getmtime(f) for f in files), default=0.0)
        if self.pr.poll() is None and not stalled(time.time(), newest, self.started, self.stall): return True
        hung = self.pr.poll() is None
        if hung: self.pr.terminate()
        try: self.pr.wait(timeout=20)
        except Exception: self.pr.kill()
        if self.restarts >= self.max: return False
        self.restarts += 1; time.sleep(10)
        last = int(os.path.basename(files[-1])[:5]) if files else -1
        idx = max(last + 1, round((time.time() - self.t_start) / SEG))
        print(f"WATCHDOG: recorder {'hung (no data for ' + str(self.stall) + ' s)' if hung else 'stopped'} - restart #{self.restarts} at piece {idx}")
        return self.start(idx)

    def stop(self):
        if self.pr and self.pr.poll() is None: self.pr.terminate()


def inbox_full(root, ch):
    """Repo guard (16.11.): every clip costs ~10 MB (clip + raw moment) and the runs follow each other. More than `max_pending` (default 12)
    entries (last 24 h) with posted=false in clips/live-<name>/inbox.json = stop recording until older ones age out of the 24 h window."""
    name = "live-" + re.sub(r"[^a-z0-9-]", "", ch["name"].lower())
    try: box = json.load(open(os.path.join(root, "clips", name, "inbox.json")))
    except Exception: return False
    now = datetime.datetime.now(datetime.timezone.utc)
    def young(e):  # only the last 24 h count: the guard frees itself, nobody has to clean up (the agent may only write clipjobs/ + postplan)
        try: return (now - datetime.datetime.fromisoformat(e["at"])).total_seconds() < 86400
        except Exception: return True
    done = posted_ids(root, name)
    return sum(1 for e in box if not e.get("posted") and e.get("id") not in done and young(e)) >= int(ch.get("max_pending", 12))


def watch_once(root, c, t_end):
    """One pass over the channels: records the first one that is live and returns True when it was watched, False when all are offline."""
    for ch in c.get("channels", []):
        if inbox_full(root, ch): print("LIVEWATCH_FULL", ch["name"], "- inbox has too many unposted clips, not recording"); return True
        rec = os.path.join(os.environ.get("RUNNER_TEMP", "/tmp"), "lw_rec"); os.makedirs(rec, exist_ok=True)
        for f in glob.glob(os.path.join(rec, "*.ts")): os.remove(f)
        rc = Recorder(ch, rec)
        if not rc.start(0): print("offline:", ch["name"]); continue
        print("LIVE:", ch["name"])
        m = re.search(r"twitch\.tv/([A-Za-z0-9_]+)", ch["url"]); chat = Chat(m.group(1)) if m else None
        ads = AdWatch(lambda: rc.hls, rc.t_start) if m else None  # ad markers exist on Twitch HLS only
        clipw = ClipWatch(m.group(1)) if m else None
        try: n = loop(ch, root, rec, rc.alive, True, t_end, chat, ads, clipw=clipw, t_rec=rc.t_start)
        finally: rc.stop()
        print(f"LIVEWATCH_DONE {ch['name']} clips {n}"); return True
    return False


def watch(root, sleep=time.sleep, now=time.time, watcher=None):
    """v0.5 (16.11.): while every channel is offline, ask again every `poll_seconds` (default 90) until `max_minutes` / `until` run out.
    Before: one offline pass ended the run and the next scheduled start came 20 min to 3 h later (GitHub delays crons), so a stream start went unseen."""
    c = cfg(root); t_end = now() + 60 * int(c.get("max_minutes", 330)); wait = max(30, int(c.get("poll_seconds", 90)))
    until = None
    try:
        if c.get("until"): until = datetime.datetime.fromisoformat(str(c["until"]).replace("Z", "+00:00")).timestamp()
    except Exception: until = None
    if until is not None: t_end = min(t_end, until)  # v0.6: a run that started before `until` stops recording at `until` (was: ran to max_minutes)
    start = None  # v0.6: "from" (ISO, UTC) = do not record before this time (the run may start earlier and just waits; keeps the inbox free of pre-launch junk)
    try:
        if c.get("from"): start = datetime.datetime.fromisoformat(str(c["from"]).replace("Z", "+00:00")).timestamp()
    except Exception: start = None
    watcher = watcher or watch_once
    while True:
        if start is not None and now() < start:
            stop = t_end if until is None else min(t_end, until)
            if now() + wait >= stop and start >= stop: break
            sleep(min(wait, max(1, start - now()))); continue
        if watcher(root, c, t_end): return
        stop = t_end if until is None else min(t_end, until)
        if now() + wait >= stop: break
        sleep(wait)
    print("LIVEWATCH_IDLE")


GQL_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"


def gql(query, timeout=30):
    """One anonymous Twitch GQL query (same public web client as the chat replay). Raises on any problem."""
    import urllib.request
    r = urllib.request.Request("https://gql.twitch.tv/gql", json.dumps({"query": query}).encode(), {"Client-ID": GQL_ID, "Content-Type": "application/json"})
    d = json.load(urllib.request.urlopen(r, timeout=timeout))
    if d.get("errors") and not d.get("data"): raise RuntimeError(str(d["errors"])[:200])
    return d["data"]


def iso_epoch(x):
    return datetime.datetime.fromisoformat(str(x).replace("Z", "+00:00")).timestamp()


def _ytdlp_json(args, timeout=240):
    r = subprocess.run(["yt-dlp", "-J", "--no-warnings", *args], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0 or not r.stdout.strip(): raise RuntimeError("yt-dlp: " + (r.stderr.strip().split("\n") or [""])[-1][:200])
    return json.loads(r.stdout)


def resolve_vod(vod, login):
    """v0.7 replay: 'videos/<id>' url -> (id, created epoch or None). Else the channel's newest archive (running broadcasts are archives, too).
    GQL first, yt-dlp as the second way (19.11.: the GQL video list answered with null on the first live try)."""
    m = re.search(r"videos/(\d+)", vod or ""); vid = m.group(1) if m else None; created = None; errs = []
    try:
        if vid: created = iso_epoch(gql('query{video(id:"%s"){createdAt}}' % vid)["video"]["createdAt"])
        else:
            n = gql('query{user(login:"%s"){videos(first:3, type:ARCHIVE, sort:TIME){edges{node{id createdAt lengthSeconds title}}}}}' % re.sub(r"[^a-z0-9_]", "", login.lower()))["user"]["videos"]["edges"][0]["node"]
            print("VOD resolved (gql):", n); return n["id"], iso_epoch(n["createdAt"])
    except Exception as e: errs.append("gql: " + str(e)[-120:])
    try:
        if not vid:
            d = _ytdlp_json(["--flat-playlist", "--playlist-end", "3", f"https://www.twitch.tv/{re.sub(r'[^A-Za-z0-9_]', '', login)}/videos?filter=archives&sort=time"])
            e0 = (d.get("entries") or [])[0]; vid = re.sub(r"\D", "", str(e0.get("id") or e0.get("url") or "")) or None
            if not vid: raise RuntimeError("no archive in list")
        if created is None:
            ts = _ytdlp_json(["--no-playlist", f"https://www.twitch.tv/videos/{vid}"], 300).get("timestamp"); created = float(ts) if ts else None
        print("VOD resolved (yt-dlp):", vid, created); return vid, created
    except Exception as e: errs.append("yt-dlp: " + str(e)[-160:])
    if vid: return vid, created
    raise RuntimeError(" | ".join(errs))


def vod_pointers(login, vid, lo, hi, top=8):
    """v0.7 replay: viewers' Twitch clips of this VOD inside [lo, hi] VOD seconds, best viewed first, one per 45 s. = (offset, duration, views, title, curator)."""
    q = ('query{user(login:"%s"){clips(first:100, criteria:{period:LAST_DAY, sort:VIEWS_DESC}){edges{node{id title viewCount durationSeconds videoOffsetSeconds video{id} curator{login}}}}}}'
         % re.sub(r"[^a-z0-9_]", "", login.lower()))
    out = []
    for e in gql(q)["user"]["clips"]["edges"]:
        n = e["node"]
        if not n.get("video") or str(n["video"]["id"]) != str(vid) or n.get("videoOffsetSeconds") is None: continue
        o = int(n["videoOffsetSeconds"])
        if lo <= o <= hi: out.append((o, int(n.get("durationSeconds") or 25), int(n.get("viewCount") or 0), n.get("title") or "", ((n.get("curator") or {}).get("login") or "")))
    keep = []
    for c in sorted(out, key=lambda x: -x[2]):
        if all(abs(c[0] - k[0]) > 45 for k in keep): keep.append(c)
    return keep[:top]


def clip_list(login, since=0.0, top=30):
    """19.11.: the viewers' Twitch clips of the last 24 h, best viewed first (GQL, then yt-dlp's channel clip list). Written to replay_info.json so an agent can pick
    sources. Each = {slug, url, title, views, created, dur, vod, vod_s, by}. Raises when both ways fail."""
    lg = re.sub(r"[^a-z0-9_]", "", login.lower()); errs = []
    try:
        q = ('query{user(login:"%s"){clips(first:100, criteria:{period:LAST_DAY, sort:VIEWS_DESC}){edges{node{id slug title viewCount createdAt durationSeconds videoOffsetSeconds video{id} curator{login}}}}}}' % lg)
        out = []
        for e in gql(q)["user"]["clips"]["edges"]:
            n = e["node"]; cr = iso_epoch(n["createdAt"])
            if cr < since: continue
            out.append({"slug": n["slug"], "url": f"https://clips.twitch.tv/{n['slug']}", "title": n.get("title") or "", "views": int(n.get("viewCount") or 0), "created": n["createdAt"],
                        "dur": int(n.get("durationSeconds") or 0), "vod": (n.get("video") or {}).get("id"), "vod_s": n.get("videoOffsetSeconds"), "by": (n.get("curator") or {}).get("login") or ""})
        return sorted(out, key=lambda x: -x["views"])[:top]
    except Exception as e: errs.append("gql: " + str(e)[-120:])
    try:
        d = _ytdlp_json(["--flat-playlist", "--playlist-end", "40", f"https://www.twitch.tv/{lg}/clips?filter=clips&range=24hr"])
        return [{"slug": str(x.get("id")), "url": x.get("url") or f"https://clips.twitch.tv/{x.get('id')}", "title": x.get("title") or "", "views": int(x.get("view_count") or 0), "created": x.get("timestamp"),
                 "dur": int(x.get("duration") or 0), "vod": None, "vod_s": None, "by": ""} for x in (d.get("entries") or [])][:top]
    except Exception as e: errs.append("yt-dlp: " + str(e)[-160:])
    raise RuntimeError(" | ".join(errs))


def push_paths(root, paths, msg):
    g = lambda *a: subprocess.run(["git", "-C", root, *a], capture_output=True, text=True)
    for p in paths: g("add", p)
    g("commit", "-q", "-m", msg)
    for i in range(4):
        if g("pull", "-q", "--rebase", "origin", "main").returncode == 0 and g("push", "-q", "origin", "HEAD:main").returncode == 0: return True
        time.sleep(6)
    return False


def replay(vod, start, minutes, root, min_chat=None, compare=False):
    """VOD mode: a past Twitch VOD is played through the live detection. Audio = VOD (HLS, read faster than real time),
    chat = chat replay. Clips land in clips/live-<channel>/ exactly like live clips, and are pushed one by one.
    v0.7 (19.11.): `vod` may be a channel url / name (-> newest archive), `start` may be an ISO time (UTC, e.g. 2026-11-19T05:00:00Z), and the clips that
    viewers made on Twitch in that window mark the moments first (own cut from the VOD at their timestamps, no repost); the detection runs afterwards when
    fewer than 6 of those worked. replay_info.json in the channel folder tells what was resolved (the logs of a running job are not readable)."""
    c = cfg(root); ch = dict((c.get("channels") or [{}])[0]); ch.setdefault("name", "jasontheween")
    ch = {"min_hype": 9, "layout": "native", "per_hour": 8, "max_clips": 8, **ch}
    if min_chat: ch["min_chat"] = float(min_chat)
    ch.pop("log_only", None); dur = int(minutes) * 60
    name = "live-" + re.sub(r"[^a-z0-9-]", "", ch["name"].lower()); info = {"vod_arg": vod, "start_arg": start, "minutes": int(minutes), "pointers": [], "made": [], "errors": []}
    infop = os.path.join(root, "clips", name, "replay_info.json"); os.makedirs(os.path.dirname(infop), exist_ok=True)
    def save(): json.dump(info, open(infop, "w"), indent=1, ensure_ascii=False)
    mm = re.search(r"twitch\.tv/([A-Za-z0-9_]+)", ch.get("url", "")); login = mm.group(1) if mm else ch["name"]
    t_since = 0.0
    try: t_since = iso_epoch(start)
    except Exception: pass
    try: info["clips_all"] = clip_list(login, t_since)
    except Exception as e: info["errors"].append("cliplist: " + str(e)[-240:])
    save(); push_paths(root, [infop], "livewatch: replay_info (%d clips listed)" % len(info.get("clips_all", [])))
    try: vid, created = resolve_vod(vod if re.search(r"videos/\d+|twitch\.tv/", vod or "") else f"https://www.twitch.tv/{vod}", login)
    except Exception as e:
        info["errors"].append("resolve: " + str(e)[-200:]); save(); push_paths(root, [infop], "livewatch: replay_info (resolve failed)"); print("VOD not resolvable:", e); return
    vod = f"https://www.twitch.tv/videos/{vid}"
    try: start = int(start)
    except ValueError:
        if created is None: info["errors"].append("ISO start needs the VOD creation time"); save(); push_paths(root, [infop], "livewatch: replay_info (no start)"); return
        start = max(0, int(iso_epoch(start) - created))
    info.update({"vod": vid, "vod_created": created, "start_s": start}); save()
    ptr = []
    try: ptr = vod_pointers(login, vid, start, start + dur)
    except Exception as e: info["errors"].append("clips: " + str(e)[-200:])
    info["pointers"] = [{"offset": o, "dur": d, "views": v, "title": t, "by": b} for o, d, v, t, b in ptr]; save()
    push_paths(root, [infop], "livewatch: replay_info %d viewer clips" % len(ptr))
    hls = live_url(vod, int(ch.get("height", 720)))
    if not hls:
        info["errors"].append("VOD not readable"); save(); push_paths(root, [infop], "livewatch: replay_info (VOD not readable)"); print("VOD not readable"); return
    rec = os.path.join(os.environ.get("RUNNER_TEMP", "/tmp"), "lw_rec"); os.makedirs(rec, exist_ok=True)
    for f in glob.glob(os.path.join(rec, "*.ts")): os.remove(f)
    cf.run(["ffmpeg", "-y", "-v", "error", "-ss", str(int(start)), "-i", hls, "-t", str(dur), "-c", "copy", "-f", "segment", "-segment_time", str(SEG),
            "-reset_timestamps", "1", os.path.join(rec, "%05d.ts")], timeout=3600)
    print("VOD recorded:", len(glob.glob(os.path.join(rec, "*.ts"))), "pieces")
    segs = {int(os.path.basename(f)[:5]): f for f in glob.glob(os.path.join(rec, "*.ts"))}
    for i, (o, d, v, t, b) in enumerate(ptr):  # viewers' clips first: the moment is ~70 % into the viewer clip
        pk = (o - start) + min(d, 30) * 0.7; stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S") + f"v{i}"
        try:
            entry, nm = make_clip(ch, root, segs, 0.0, pk, 0.0, stamp); entry.update({"viewer_clip": True, "views": v, "title": t, "peak_s": int(pk), "vod": vid, "vod_s": int(o), "chat": 0.0})
            publish(root, nm, entry, True); info["made"].append({"id": stamp, "views": v, "title": t, "vod_s": o})
        except Exception as e: info["errors"].append(f"clip {i} @{o}: " + str(e)[-160:]); print("WARN viewer clip failed:", str(e)[-200:])
    save(); push_paths(root, [infop], "livewatch: replay_info (%d clips made)" % len(info["made"]))
    if len(info["made"]) >= 6: print("enough viewer clips, detection skipped"); return
    chat = ReplayChat(vid, int(start), dur); ch["vod"] = vid; ch["vod_start"] = int(start)
    if compare:  # same recording twice: old settings (plain message count, no alert / safety filters; dir live-<name>-old holds QA pictures only), then the new ones
        old = {**ch, "legacy": True, "name": ch["name"] + "-old", "min_chat": float(min_chat or 4.5)}
        n0 = loop(old, root, rec, lambda: False, True, time.time() + 3 * 3600, chat.view(True), keep=True); print(f"COMPARE old settings: clips {n0}")
    n = loop(ch, root, rec, lambda: False, True, time.time() + 3 * 3600, chat.view(False)); print(f"LIVEWATCH_DONE replay {ch['name']} clips {n}")


def probe(root):
    """v0.8: prints what the top-clip mode would do right now - the channel's viewer clips (GQL), the median, the candidates, and ONE test download. Writes nothing into the repo, no git."""
    c = cfg(root); ch = with_profile((c.get("channels") or [{}])[0]); mm = re.search(r"twitch\.tv/([A-Za-z0-9_]+)", ch.get("url", ""))
    login = mm.group(1) if mm else ch.get("name", "kaicenat")
    cw = ClipWatch(login, autostart=False)
    try: cw.poll()
    except Exception as e: print("PROBE gql FAILED:", str(e)[-200:]); return 1
    day = cw.day(); now = time.time(); print(f"PROBE gql ok: {len(day)} clips in the last 24 h, best {max((x['views'] for x in day), default=0)} views")
    cands = top_candidates(day, now, [], rel=float(ch.get("top_rel", 1.5)), min_views=int(ch.get("top_min_views", 40)), window_h=float(ch.get("top_window_h", 4.0)))
    print(f"PROBE candidates (<= {ch.get('top_window_h', 4.0)} h old, relative threshold): {len(cands)}")
    for x in cands[:5]: print(f"   {x['views']:5d} views x{x['rel']} {x['dur']:2d} s '{x['title'][:40]}' moment {iso_utc(x['moment'])}")
    pick = (cands or sorted(day, key=lambda x: -x["views"]))[:1]
    if not pick: print("PROBE no clip to download"); return 0
    tmp = os.path.join(os.environ.get("RUNNER_TEMP", "/tmp"), "lw_probe"); os.makedirs(tmp, exist_ok=True); t0 = time.time()
    try:
        f = fetch_clip(pick[0]["slug"], os.path.join(tmp, "probe.mp4")); p = cf.probe(f)
        print(f"PROBE download ok: {os.path.getsize(f) / 1e6:.1f} MB, {p['dur']:.0f} s, {p['w']}x{p['h']} {p['fps']:.0f} fps, audio {p['audio']}, {time.time() - t0:.0f} s")
        if pick[0].get("vid") and pick[0].get("off") is not None:
            t1 = time.time(); ok = vod_section(pick[0]["vid"], float(pick[0]["off"]) - 12, float(pick[0]["off"]) + 20, os.path.join(tmp, "probe_vod.mp4"), timeout=100)
            print(f"PROBE vod section: {'ok' if ok else 'failed/too slow'} ({time.time() - t1:.0f} s)")
    except Exception as e: print("PROBE download FAILED:", str(e)[-200:]); return 1
    return 0


def simulate(src, root):
    rec = "/tmp/lw_sim"; os.makedirs(rec, exist_ok=True)
    for f in glob.glob(os.path.join(rec, "*.ts")): os.remove(f)
    cf.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-c", "copy", "-f", "segment", "-segment_time", str(SEG), "-reset_timestamps", "1", os.path.join(rec, "%05d.ts")])
    ch = (cfg(root).get("channels") or [{}])[0]; ch = {"min_hype": 9, **ch, "name": "sim"}
    print("SIM clips", loop(ch, root, rec, lambda: False, False, time.time() + 3600))


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) == 2 and a[0] == "check":
        c = cfg(a[1]); print("run" if c.get("enabled") and c.get("channels") else "skip")
    elif len(a) == 2 and a[0] == "watch": watch(a[1])
    elif len(a) == 3 and a[0] == "simulate": simulate(a[1], a[2])
    elif len(a) == 2 and a[0] == "probe": sys.exit(probe(a[1]))
    elif len(a) in (5, 6, 7) and a[0] == "replay": replay(a[1], a[2], a[3], a[4], (a[5] or None) if len(a) > 5 else None, len(a) == 7 and a[6] == "compare")
    else: sys.exit(__doc__)
