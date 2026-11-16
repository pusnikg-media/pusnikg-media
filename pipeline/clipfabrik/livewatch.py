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
restarts ffmpeg when nothing was written for 2 minutes. Clips with self-harm wording or without speech (walking / driving) are dropped before rendering."""
import datetime, glob, json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import clipfabrik as cf

SEG = 60


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
        self.n = {}; self.u = {}; self.alerts = {}; self.kinds = {}; self.ok = False; self.legacy = legacy

    def add(self, k, login, text, bits=0, kind=None):
        kind = kind or classify(login, text, bits)
        if kind and not self.legacy:
            self.alerts[k] = self.alerts.get(k, 0) + 1; self.kinds[kind] = self.kinds.get(kind, 0) + 1; return
        self.n[k] = self.n.get(k, 0) + 1; self.u.setdefault(k, set()).add((login or "").lower()); self.ok = True

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


def make_clip(ch, root, segs, t0, peak, hype, stamp):
    """Cut 30 s before / 12 s after the peak, transcribe, pick whole sentences around the peak, render. Returns inbox entry."""
    name = "live-" + re.sub(r"[^a-z0-9-]", "", ch["name"].lower()); out = os.path.join(root, "clips", name); os.makedirs(out, exist_ok=True)
    tmp = os.path.join(os.environ.get("RUNNER_TEMP", "/tmp"), "lw_" + name); os.makedirs(tmp, exist_ok=True)
    a0, b0 = max(peak - 30, t0), peak + 12; raw = os.path.join(tmp, "moment.mp4"); p = cut(segs, t0, a0, b0, raw); pk = peak - a0
    words = []
    try: words = cf.transcribe(cf.audio16k(raw, tmp), ch.get("whisper", "small.en")) if p["audio"] else []
    except Exception as e: print("WARN no transcript:", str(e)[-200:])
    inwin = [w for w in words if pk - 20 <= w["s"] <= pk + 8]
    if len(inwin) < 12: raise cf.Fail(f"too little speech around the moment ({len(inwin)} words): ad break / music / silence")  # v0.3 16.11.: Twitch ad break fired the chat+loud signal
    if not ch.get("legacy") and selfharm(" ".join(w["w"] for w in words)): raise cf.Fail("self-harm wording in the moment")  # v0.4: campaign rule, never post these
    sents = cf.sentences(words)
    cands = [c for c in cf.candidates(sents, [], p["dur"], 6, 12, 34) if c["a"] <= pk <= c["b"]] if sents else []
    if cands: c = max(cands, key=lambda x: x["score"]); a, b = c["a"], c["b"]
    else: a, b = max(pk - 16, 0), min(pk + 8, p["dur"])
    if not ch.get("legacy") and speech_rate(words, a, b) < 0.8: raise cf.Fail("almost no speech in the cut: walking / driving scene")  # v0.4
    said = next((s["text"] for s in sents if s["s"] - 0.5 <= pk <= s["e"] + 1.5), "")
    title = ""
    for w in re.sub(r"[^A-Za-z0-9' ]", "", said).upper().split():
        if len(title) + len(w) + 1 > 26: break
        title = (title + " " + w).strip()
    # v0.2 (15.11.): viral style = whole picture + one sentence. The preview only quotes what was said; the agent writes the real
    # context sentence and re-renders through the Clipfabrik from the RAW moment (kept as raw_<stamp>.mp4, source of a clipjob).
    quote = ('"' + title.capitalize() + '"') if title else "Live moment"
    job = {"name": name, "layout": ch.get("layout", "native"), "fix": ch.get("fix") or {}, "_logo_img": None}
    clip = {"id": stamp, "a": round(a, 2), "b": round(b, 2), "caption": quote}
    r = cf.render_clip(job, clip, raw, p, words, out, tmp)
    rawname = f"raw_{stamp}.mp4"
    if ch.get("legacy"):  # comparison run (old settings): only the QA picture + text stay, no video in the repo
        os.remove(raw); os.remove(os.path.join(out, r["file"])); rawname = None
    else:
        cf.run(["ffmpeg", "-y", "-v", "error", "-i", raw, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
                os.path.join(out, rawname)]); os.remove(raw)
    return {"id": stamp, "at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "channel": ch["name"],
            "hype": round(hype, 1), "seconds": r["seconds"], "quote": quote, "a": clip["a"], "b": clip["b"], "raw": (f"{cf.RAW}/clips/{name}/{rawname}" if rawname else None), "said": " ".join(w["w"] for w in words if a <= w["s"] <= b)[:500],
            "url": f"{cf.RAW}/clips/{name}/{r['file']}", "qa": f"{cf.RAW}/clips/{name}/{r['qa']}", "posted": False}, name


def publish(root, name, entry, push):
    ip = os.path.join(root, "clips", name, "inbox.json")
    try: box = json.load(open(ip))
    except Exception: box = []
    box.append(entry); json.dump(box[-40:], open(ip, "w"), indent=1, ensure_ascii=False)
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


def loop(ch, root, rec, alive, push, t_end, chat=None, ads=None, keep=False):
    """Shared by watch and simulate: rec = folder that fills with %05d.ts pieces, alive() = recorder still running.
    ads = AdWatch (live only), keep = leave the pieces on disk (comparison runs read the same recording twice)."""
    ch = with_profile(ch); skipped = {"alert": 0, "ad": 0}; expect = 0
    db, segs, done, clips, last = [], {}, 0, [], -999.0; t0 = 0.0
    dry = bool(ch.get("log_only")); cal = {"channel": ch["name"], "started": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                                           "minutes": [], "events": []}
    min_chat = float(ch.get("min_chat", 3.0)); co_chat = float(ch.get("co_chat", 2.0))  # calibrated 15.11.2026 (98 min, 2 channels): 2.5/1.4 fired every 4.6 min
    alert_max = int(ch.get("alert_max", 3)); warm = int(ch.get("warmup_s", 480))  # no clip in the first 8 min of a recording (chat/loudness baseline still forming)
    min_hype = float(ch.get("min_hype", 9)); per_hour = int(ch.get("per_hour", 3)); max_clips = int(ch.get("max_clips", 8))
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
            if chat and chat.ok:  # with a chat signal: a chat burst decides; loudness alone needs at least a busier chat
                al, us = chat.alert_near(cp) if (cp is not None and cr >= min_chat) else (0, 0)
                if cp is not None and cr >= min_chat and not chat.legacy and al >= alert_max and al >= 0.25 * us:
                    skipped["alert"] += 1; peak = None; print(f"   chat burst x{cr} skipped: alert chain ({al} alerts vs {us} chatters)")
                elif cp is not None and cr >= min_chat:
                    # chat reacts late (stream delay + typing, measured 7-25 s, median 17): the moment is the loudest second in the 32 s before the burst
                    w0 = max(cp - 28, 0); seg_ = db[w0:cp + 5]  # measured lags 7-25 s (median 17), 25 was the old cap
                    lag = (cp + 4) - (w0 + max(range(len(seg_)), key=seg_.__getitem__)) if seg_ else 0; kind = "chat"
                    peak, hype = (max(cp + 4 - lag, 0) if seg_ else max(cp, 0)), max(hype, min_hype); print(f"   chat burst x{cr}: moment {lag:.0f} s before the chat peak")
                elif not (cp is not None and cr >= co_chat and peak is not None and abs(cp - peak) < 30): peak = None
            if dry:
                if peak is not None and hype >= min_hype and len(db) - peak >= 12 and peak - last > 90:
                    cal["events"].append({"min": done, "pos": int(peak), "kind": kind, "hype": round(hype, 1), "chat": cr, "lag": lag}); last = peak
                if done % 20 == 0: save_calib(root, ch, cal, push)
            elif peak is not None and ads and ads.hit(peak - 30, peak + 12):
                skipped["ad"] += 1; last = peak; print("   moment skipped: Twitch ad break")
            elif peak is not None and hype >= min_hype and len(db) - peak >= 12 and peak - last > 90 and len(recent) < per_hour and len(clips) < max_clips:
                stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
                try:
                    entry, name = make_clip(ch, root, segs, t0, peak, hype, stamp); entry["chat"] = cr; entry["peak_s"] = int(peak)
                    if ch.get("vod"): entry["vod"] = ch["vod"]; entry["vod_s"] = int(ch.get("vod_start", 0) + peak)
                    publish(root, name, entry, push)
                    clips.append(peak); last = peak
                except Exception as e:
                    print("WARN clip failed:", str(e)[-300:]); last = peak
            for j in [k for k in segs if k < i - 14 and not keep]:  # keep 15 minutes on disk
                try: os.remove(segs.pop(j))
                except OSError: pass
        if not run and done >= len(files): break
        time.sleep(1 if not push else 20)
    print(f"LOOP_STATS {ch['name']} legacy={bool(ch.get('legacy'))} clips={len(clips)} skipped={skipped}")
    if dry: save_calib(root, ch, cal, push); return len(cal["events"])
    return len(clips)


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
    return sum(1 for e in box if not e.get("posted") and young(e)) >= int(ch.get("max_pending", 12))


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
        try: n = loop(ch, root, rec, rc.alive, True, t_end, chat, ads)
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
    watcher = watcher or watch_once
    while True:
        if watcher(root, c, t_end): return
        stop = t_end if until is None else min(t_end, until)
        if now() + wait >= stop: break
        sleep(wait)
    print("LIVEWATCH_IDLE")


def replay(vod, start, minutes, root, min_chat=None, compare=False):
    """VOD mode: a past Twitch VOD is played through the live detection. Audio = VOD (HLS, read faster than real time),
    chat = chat replay. Clips land in clips/live-<channel>/ exactly like live clips, and are pushed one by one."""
    m = re.search(r"videos/(\d+)", vod); assert m, "VOD url needs /videos/<id>"
    c = cfg(root); ch = dict((c.get("channels") or [{}])[0]); ch.setdefault("name", "jasontheween")
    ch = {"min_hype": 9, "layout": "native", "per_hour": 8, "max_clips": 8, **ch}
    if min_chat: ch["min_chat"] = float(min_chat)
    ch.pop("log_only", None); dur = int(minutes) * 60
    hls = live_url(vod, int(ch.get("height", 720)))
    if not hls: print("VOD not readable"); return
    rec = os.path.join(os.environ.get("RUNNER_TEMP", "/tmp"), "lw_rec"); os.makedirs(rec, exist_ok=True)
    for f in glob.glob(os.path.join(rec, "*.ts")): os.remove(f)
    cf.run(["ffmpeg", "-y", "-v", "error", "-ss", str(int(start)), "-i", hls, "-t", str(dur), "-c", "copy", "-f", "segment", "-segment_time", str(SEG),
            "-reset_timestamps", "1", os.path.join(rec, "%05d.ts")], timeout=3600)
    print("VOD recorded:", len(glob.glob(os.path.join(rec, "*.ts"))), "pieces")
    chat = ReplayChat(m.group(1), int(start), dur); ch["vod"] = m.group(1); ch["vod_start"] = int(start)
    if compare:  # same recording twice: old settings (plain message count, no alert / safety filters; dir live-<name>-old holds QA pictures only), then the new ones
        old = {**ch, "legacy": True, "name": ch["name"] + "-old", "min_chat": float(min_chat or 4.5)}
        n0 = loop(old, root, rec, lambda: False, True, time.time() + 3 * 3600, chat.view(True), keep=True); print(f"COMPARE old settings: clips {n0}")
    n = loop(ch, root, rec, lambda: False, True, time.time() + 3 * 3600, chat.view(False)); print(f"LIVEWATCH_DONE replay {ch['name']} clips {n}")


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
    elif len(a) in (5, 6, 7) and a[0] == "replay": replay(a[1], a[2], a[3], a[4], (a[5] or None) if len(a) > 5 else None, len(a) == 7 and a[6] == "compare")
    else: sys.exit(__doc__)
