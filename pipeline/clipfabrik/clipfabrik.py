"""Clipfabrik v2: campaign footage (any aspect) -> 9:16 clips, driven by a job file. Original audio only.
Runs in the GitHub Action clipfabrik.yml (scheduled Claude runs may not execute code themselves).

  python3 clipfabrik.py run  job.json REPO_ROOT [SRC]   everything the job still needs (download, scan, render, result.json)
  python3 clipfabrik.py pending REPO_ROOT outdir        list of jobs that still need work (used by the Action)
  python3 clipfabrik.py scan SRC outdir [n] [min] [max] words.json + scan.json + contact sheets cand_XX.jpg
  python3 clipfabrik.py render job.json SRC words.json outdir

job.json (clipjobs/<name>.json in the repo or clipjob-<name>.json in the Drive folder):
  name      short id, e.g. "mw4dmz" -> results in clips/<name>/
  source    URL of the official footage (GitHub release asset, public Drive file link or any direct https URL)
  pill      optional yellow line under the title (e.g. a mandatory campaign sentence)
  logo      optional watermark PNG (repo path like assets/logos/warzone_white.png, or https URL), drawn on every clip;
            logo_w width in px (default 380), logo_pos "video_bottom" (default, inside the picture) or "video_top"
  fix       optional {"heard": "Correct"} for names whisper mishears (matched per word, punctuation kept)
  whisper   optional model (default small.en)
  min_len   shortest allowed clip in s (default 10 - most campaigns demand >= 10 s)
  clips     [{"id", "a", "b", "title", optional "pill", "wide": true (show 75 % of the width, for text slates),
              "captions": false, "rev": n (raise to re-render), "layout"/"track" override the job values}]
            no "clips" yet -> scan only: the agent reads clips/<name>/scan/scan.json + cand_XX.jpg and adds them.
v3 (IRL, 14.11.): optional job fields
  layout    "framed" (default: blurred fill + sharp centre 1080x1200) or "full" (full-screen 9:16 crop, for IRL streams)
  track     true = the crop follows the biggest face (OpenCV, smoothed with a dead zone; falls back to the centre)
  max_height  download height for stream URLs (default 1080)
  sections  streams > 3 h (or "sections": true): scan at 360p, and the render phase downloads only each clip's seconds
            (frame-accurate from the HLS playlist) instead of the whole VOD -> 12 h Kick/Twitch streams fit the runner
  hot_k     number of loud "hotspot" regions examined in long sources (default 14)
  source can also be a stream/VOD page (Twitch, Kick, YouTube, TikTok, X, Rumble) -> downloaded with yt-dlp
  or a direct .m3u8 playlist (Kick VODs: use the API field "source"; the kick.com/<name>/videos/<uuid> page fails with NOT_FOUND).
  (scan phase at 480p, render phase at max_height; same VOD = same timestamps).
  Sources longer than 15 min are scanned in "hotspot" mode: per-second loudness against a rolling 3-min baseline
  (shouts, laughter, crowd) + YouTube "most replayed" heatmap when yt-dlp provides one -> only those regions are
  transcribed -> candidates carry "hype" (dB above baseline). scan.json gets "mode": "hotspots" + "regions".
v4 (15.11.): retention edits, per clip or per job
  hook      clip only: [s, e] (source seconds, 0.8-5 s) = that moment is shown FIRST as a teaser, then a white flash and the
            clip from "a". "auto" = the loudest moment after the first 5 s, snapped to whole words (none if nothing stands out).
  zoom      true/false: quick 8 % zoom punches on the loudest moments (laughs, shouts), at most one per 4 s.
            Default: on for layout "full", off for "framed".
v5 (15.11., from the reference lab: viral streamer clips keep the ORIGINAL framing and one context sentence in a white box)
  layout    "native" = the whole source picture (e.g. 16:9) in the middle of a blurred 9:16 frame, nothing cropped away,
            no karaoke captions unless the clip sets "captions": true, no zoom unless "zoom": true.
  layout    "split" = gaming clips with a facecam: streamer's face on top (1080x720), gameplay below (1080x1200), caption on the
            seam. "facecam": "auto" (default; finds the small face that stays in one place) or [x, y, w, h] as fractions of the
            source frame (0-1). No facecam found -> falls back to "native".
  caption   clip only: one context sentence in normal spelling, e.g. "Lacy did NOT expect Rug to DANCE on his stream 😭"
            (max 3 lines, ~95 characters; emojis are drawn when the runner has a colour emoji font). Drawn as a white box
            with black text right above the picture (layout native/framed) or at the top (full). Replaces the big title.
Result: clips/<name>/result.json {"ok", "sig", "attempts", "clips": [{"id", "ok", "url", "seconds", "title", "caption", "hints"}], "error"}.
"hints" = soft style checks of the caption (too short, no emoji, two sentences ...) - the clip is rendered anyway.
Layout 1080x1920: blurred fill, sharp centre crop 1080x1200 at y=400, title (+ pill) on top, karaoke captions (libass)."""
import glob, hashlib, json, math, os, re, subprocess, sys, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "..", "fonts")
ANTON = os.path.join(FONTS, "Anton-Regular.ttf")
PILL_FONTS = ["/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", ANTON]
W, H, FG_Y, FG_H = 1080, 1920, 400, 1200
RAW = "https://raw.githubusercontent.com/" + os.environ.get("GITHUB_REPOSITORY", "pusnikg-media/pusnikg-media") + "/main"


class Fail(Exception):
    pass


def run(cmd, timeout=3600):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode: raise Fail("FAIL " + " ".join(map(str, cmd))[:200] + "\n" + r.stderr[-1200:])
    return r


def probe(src):
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate:format=duration",
             "-of", "json", src])
    d = json.loads(r.stdout); s = d["streams"][0]; n, _, m = s["r_frame_rate"].partition("/")
    a = run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_name", "-of", "csv=p=0", src]).stdout.strip()
    return {"w": int(s["width"]), "h": int(s["height"]), "fps": float(n) / float(m or 1), "dur": float(d["format"]["duration"]), "audio": bool(a)}


STREAM_HOSTS = ("twitch.tv", "kick.com", "youtube.com", "youtu.be", "tiktok.com", "x.com", "twitter.com", "rumble.com", "instagram.com")


def is_stream(url):
    u = urllib.parse.urlparse(str(url)); host = (u.hostname or "").lower()
    if u.path.lower().endswith(".m3u8"): return True  # direct HLS playlist, e.g. Kick VOD "source" from kick.com/api/v2/channels/<name>/videos
    return any(host == h or host.endswith("." + h) for h in STREAM_HOSTS)


def ytdlp(url, tmp, height):
    """Stream/VOD page -> mp4 via yt-dlp. Returns (path, probe, info) - info carries duration and maybe a heatmap."""
    base = os.path.join(tmp, f"src{height}")
    for f in glob.glob(base + ".*"): os.remove(f)
    try:
        run(["yt-dlp", "--no-playlist", "--no-progress", "--retries", "5", "--fragment-retries", "10", "--concurrent-fragments", "8",
             "-f", f"bv*[height<={height}]+ba/b[height<={height}]/bv*+ba/b", "--merge-output-format", "mp4",
             "--write-info-json", "-o", base + ".%(ext)s", url], timeout=4 * 3600)
    except Fail as e:
        hint = " (YouTube often blocks cloud servers - ask the campaign for a Drive/direct link)" if "youtu" in url else ""
        raise Fail(f"yt-dlp could not download {url[:120]}{hint}: {str(e)[-500:]}")
    vids = [f for f in glob.glob(base + ".*") if f.endswith((".mp4", ".mkv", ".webm"))]
    if not vids: raise Fail("yt-dlp produced no video for " + url[:120])
    try: info = json.load(open(base + ".info.json"))
    except Exception: info = {}
    return vids[0], probe(vids[0]), info


def remote_dur(url):
    """Duration of a stream/VOD in s without downloading it (0 if unknown)."""
    try:
        d = float(json.loads(run(["yt-dlp", "-J", "--no-playlist", url], timeout=300).stdout).get("duration") or 0)
        if d: return d
    except Exception: pass
    if urllib.parse.urlparse(url).path.lower().endswith(".m3u8"):
        try: return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", url], timeout=300).stdout.strip() or 0)
        except Exception: pass
    return 0.0


def fetch_section(url, a, b, height, dst):
    """Frame-accurate piece [a, b] of a muxed HLS VOD (Kick, Twitch) at <= height, re-encoded near-lossless.
    Long streams (12 h) never get downloaded in full for rendering - only the seconds each clip needs."""
    try:
        v = [l for l in run(["yt-dlp", "-g", "--no-playlist", "-f", f"b[height<={height}]/b", url], timeout=300).stdout.split("\n") if l.startswith("http")]
    except Fail as e:
        raise Fail(f"no stream URL for {url[:100]}: {str(e)[-300:]}")
    if len(v) != 1: raise Fail("section download needs a single muxed stream (Kick/Twitch VOD): " + url[:100])
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-i", v[0], "-t", f"{b - a:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "15",
         "-c:a", "aac", "-b:a", "192k", "-avoid_negative_ts", "make_zero", dst], timeout=1800)
    return probe(dst)


def download(url, dst):
    """Release assets / direct links as they are; Drive share links via the direct-download endpoint (works for big files)."""
    m = re.search(r"drive\.google\.com/(?:file/d/|open\?id=|uc\?(?:export=download&)?id=)([\w-]{20,})", url)
    if m: url = f"https://drive.usercontent.google.com/download?id={m.group(1)}&export=download&confirm=t"
    if urllib.parse.urlparse(url).scheme != "https": raise Fail(f"source must be an https URL: {url[:120]}")
    run(["curl", "-fsSL", "--retry", "3", "--max-time", "1500", "-A", "Mozilla/5.0", "-o", dst, url], timeout=1600)
    try: p = probe(dst)
    except Exception: raise Fail("source is not a video (login page? Drive file not shared 'anyone with the link'?): " + url[:120])
    return p


# ---------------------------------------------------------------- scan
def audio16k(src, tmp):
    import numpy as np, scipy.io.wavfile as wavf
    wav = os.path.join(tmp, "_scan.wav")
    run(["ffmpeg", "-y", "-v", "error", "-i", src, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", wav])
    _, a = wavf.read(wav); os.remove(wav)
    return a.astype(np.float32) / 32768  # numpy array: decoding through `av` inside faster-whisper raised metadata errors


def transcribe(a, model):
    from faster_whisper import WhisperModel
    m = WhisperModel(model, device="cpu", compute_type="int8")
    segs, _ = m.transcribe(a, word_timestamps=True, beam_size=5, vad_filter=True, condition_on_previous_text=False)
    out = []
    for s in segs:
        for w in s.words or []:
            t = w.word.strip()
            if t: out.append({"w": t, "s": round(float(w.start), 3), "e": round(float(w.end), 3)})
    return out


def sentences(words):
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        gap = words[i + 1]["s"] - w["e"] if i + 1 < len(words) else 9
        if re.search(r"[.?!]$", w["w"]) or gap > 0.8:
            out.append({"s": cur[0]["s"], "e": cur[-1]["e"], "text": " ".join(x["w"] for x in cur)}); cur = []
    return out


def scene_cuts(src):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", src, "-an", "-vf", "scale=320:-2,select='gt(scene,0.32)',showinfo", "-f", "null", "-"],
                       capture_output=True, text=True)
    return [round(float(m), 2) for m in re.findall(r"pts_time:([0-9.]+)", r.stderr)]


def candidates(sents, cuts, dur, n, lo, hi):
    """Runs of whole sentences lasting lo..hi s (never cut mid-sentence); without speech: windows between scene cuts."""
    c = []
    for i in range(len(sents)):
        for j in range(i, len(sents)):
            a, b = max(sents[i]["s"] - 0.15, 0), min(sents[j]["e"] + 0.3, dur)
            if b - a > hi: break
            if b - a < lo: continue
            talk = sum(x["e"] - x["s"] for x in sents[i:j + 1]) / (b - a)
            nc = sum(1 for t in cuts if a < t < b)
            score = 0.5 * talk + 0.3 * min(nc / ((b - a) / 3), 1) + 0.2 * (1 - abs((b - a) - 16) / 16)
            c.append({"a": round(a, 2), "b": round(b, 2), "len": round(b - a, 1), "score": round(score, 3), "cuts": nc,
                      "text": " ".join(x["text"] for x in sents[i:j + 1])[:400]})
    if not c:
        pts = [0.0] + [t for t in cuts if 1 < t < dur - 1] + [dur]
        for i, a in enumerate(pts):
            ends = [b for b in pts[i + 1:] if lo <= b - a <= hi]
            if ends: c.append({"a": round(a, 2), "b": round(ends[-1], 2), "len": round(ends[-1] - a, 1), "score": 0.1, "cuts": 0, "text": ""})
        if not c and dur >= lo: c.append({"a": 0.0, "b": round(min(dur, hi), 2), "len": round(min(dur, hi), 1), "score": 0.1, "cuts": 0, "text": ""})
    c.sort(key=lambda x: -x["score"]); pick = []
    for x in c:
        if all(x["b"] <= p["a"] + 0.5 or x["a"] >= p["b"] - 0.5 for p in pick): pick.append(x)
        if len(pick) >= n: break
    return sorted(pick, key=lambda x: x["a"])


def loudness(src):
    """Per-second RMS in dB from an 8 kHz mono pipe, read in 60 s chunks (a 4 h stream never sits in memory)."""
    import numpy as np
    pr = subprocess.Popen(["ffmpeg", "-v", "error", "-i", src, "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"], stdout=subprocess.PIPE)
    out, buf = [], b""
    while True:
        chunk = pr.stdout.read(16000 * 60)
        if not chunk: break
        buf += chunk; k = len(buf) // 16000 * 16000
        if k:
            a = np.frombuffer(buf[:k], np.int16).astype(np.float32).reshape(-1, 8000) / 32768; buf = buf[k:]
            out.extend((20 * np.log10(np.sqrt((a ** 2).mean(1)) + 1e-5)).tolist())
    pr.wait()
    return np.array(out, dtype=np.float32)


def hot_regions(db, heat=None, k=14, win=20, ctx=25):
    """Loudest moments relative to the local baseline (rolling 3-min median) -> [{"a","b","peak","hype"}], best first.
    heat = YouTube 'most replayed' [{start_time, end_time, value 0..1}] adds up to +6 dB."""
    import numpy as np
    from scipy.ndimage import median_filter
    n = len(db)
    if n < win: return [{"a": 0.0, "b": float(n), "peak": 0.0, "hype": 0.0}]
    base = median_filter(db, size=min(181, n | 1), mode="nearest")
    ex = np.clip(db - base, 0, 30); ex[db < -50] = 0  # silence is never a highlight
    if heat:
        for h in heat:
            s, e = int(h.get("start_time", 0)), int(math.ceil(h.get("end_time", 0)))
            ex[max(s, 0):min(e, n)] += 6 * float(h.get("value", 0))
    sc = np.array([np.sort(ex[t:t + win])[-4:].mean() for t in range(n - win + 1)])
    used = np.zeros(len(sc), bool); out = []
    while len(out) < k and not used.all():
        t = int(np.argmax(np.where(used, -1, sc)))
        if sc[t] <= 0.5 or (sc[t] < 1.5 and len(out) >= 3): break  # nothing stands out any more (quiet streams keep their best 3)
        out.append({"a": float(max(t - ctx, 0)), "b": float(min(t + win + ctx, n)), "peak": float(t + int(np.argmax(ex[t:t + win]))),
                    "hype": round(float(sc[t]), 2)})
        used[max(t - win - 2 * ctx, 0):t + win + 2 * ctx] = True
    return out


def scan_long(src, out, p, n, lo, hi, model, heat=None, k=14):
    """Hotspot scan for long streams: only the loud regions get transcribed and turned into candidates."""
    import numpy as np
    db = loudness(src); regs = hot_regions(db, heat, k=k)
    words, sents, cands = [], [], []
    for r in regs:
        ws = []
        if p["audio"]:
            wav = os.path.join(out, "_r.wav")
            run(["ffmpeg", "-y", "-v", "error", "-ss", f"{r['a']:.2f}", "-t", f"{r['b'] - r['a']:.2f}", "-i", src, "-vn", "-ac", "1",
                 "-ar", "16000", "-c:a", "pcm_s16le", wav])
            import scipy.io.wavfile as wavf
            _, a = wavf.read(wav); os.remove(wav)
            ws = [dict(w, s=round(w["s"] + r["a"], 3), e=round(w["e"] + r["a"], 3)) for w in transcribe(a.astype(np.float32) / 32768, model)]
        ss = sentences(ws); words += ws; sents += ss
        rc = [c for c in candidates(ss, [], r["b"], 3, lo, hi) if c["text"]] if ss else []
        if not rc:  # no usable speech (screaming, music, crowd): a window around the peak
            a = max(r["a"], r["peak"] - lo * 0.6); b = min(r["b"], a + max(lo + 2, 14))
            rc = [{"a": round(a, 2), "b": round(b, 2), "len": round(b - a, 1), "score": 0.1, "cuts": 0,
                   "text": " ".join(w["w"] for w in ws if a <= w["s"] < b)[:400]}]
        for c in rc:
            c["hype"] = r["hype"]; c["peak_in"] = c["a"] <= r["peak"] <= c["b"]
            c["score"] = round(c["score"] + 0.06 * r["hype"] + (0.25 if c["peak_in"] else 0), 3)
        hit = [c for c in rc if c["peak_in"]]
        cands += sorted(hit, key=lambda x: -x["score"])[:2] if hit else sorted(rc, key=lambda x: -x["score"])[:1]
    cands = sorted(sorted(cands, key=lambda x: -x["score"])[:n], key=lambda x: x["a"])
    return words, sents, cands, regs


def scan(src, out, n=6, lo=10.0, hi=24.0, model="small.en", heat=None, long_after=900, hot_k=14):
    os.makedirs(out, exist_ok=True); p = probe(src); mode, regs = "full", []
    if p["dur"] > long_after:
        mode = "hotspots"; cuts = []
        words, sents, cands, regs = scan_long(src, out, p, max(n, 10), lo, hi, model, heat, hot_k)
    else:
        words = transcribe(audio16k(src, out), model) if p["audio"] else []
        sents = sentences(words); cuts = scene_cuts(src)
        cands = candidates(sents, cuts, p["dur"], n, lo, hi)
    for i, c in enumerate(cands):  # 4 frames per candidate so the agent can LOOK before writing an honest title
        fr = []
        for k, f in enumerate((0.05, 0.35, 0.65, 0.95)):
            fp = os.path.join(out, f"_f{k}.jpg"); fr.append(fp)
            run(["ffmpeg", "-y", "-v", "error", "-ss", f"{c['a'] + (c['b'] - c['a']) * f:.2f}", "-i", src, "-frames:v", "1", "-vf", "scale=480:-2", fp])
        c["sheet"] = f"cand_{i:02d}.jpg"
        run(["ffmpeg", "-y", "-v", "error", *sum([["-i", f] for f in fr], []), "-filter_complex", "hstack=inputs=4", "-q:v", "5", os.path.join(out, c["sheet"])])
        for f in fr: os.remove(f)
    json.dump(words, open(os.path.join(out, "words.json"), "w"))
    json.dump({"duration": round(p["dur"], 2), "width": p["w"], "height": p["h"], "fps": round(p["fps"], 2), "mode": mode,
               "regions": regs, "cuts": cuts, "sentences": sents, "candidates": cands},
              open(os.path.join(out, "scan.json"), "w"), indent=1, ensure_ascii=False)
    print(f"SCAN_OK {mode} {p['dur']:.1f}s {len(words)} words {len(sents)} sentences {len(regs)} regions {len(cands)} candidates")


# ---------------------------------------------------------------- render
def pfont(size):
    from PIL import ImageFont
    for f in PILL_FONTS:
        try: return ImageFont.truetype(f, size)
        except OSError: pass
    raise Fail("no font found")


def load_logo(src, root):
    """Campaign logo as RGBA image (repo-relative path or https URL); None if no logo."""
    if not src: return None
    from PIL import Image
    import io, urllib.request
    if re.match(r"https?://", src):
        data = urllib.request.urlopen(urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
        return Image.open(io.BytesIO(data)).convert("RGBA")
    path = src if os.path.isabs(src) else os.path.join(root, src)
    if not os.path.exists(path): raise Fail(f"logo not found: {src}")
    return Image.open(path).convert("RGBA")


def paste_logo(img, logo, width, y_top=None, y_bottom=None):
    """Logo centred horizontally (clear of TikTok's side buttons) with a soft dark halo so it reads on bright footage."""
    from PIL import Image, ImageFilter
    lw = int(width); lh = int(logo.height * lw / logo.width); lg = logo.resize((lw, lh), Image.LANCZOS)
    x = (W - lw) // 2; y = int(y_top if y_top is not None else y_bottom - lh)
    halo = Image.new("RGBA", img.size, (0, 0, 0, 0)); a = lg.split()[3].point(lambda v: min(255, int(v * 0.85)))
    halo.paste(Image.new("RGBA", lg.size, (0, 0, 0, 255)), (x, y), a)
    halo = halo.filter(ImageFilter.GaussianBlur(14))
    img.alpha_composite(halo); img.alpha_composite(lg, (x, y))


EMOJI_FONTS = ["/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf", "/usr/share/fonts/noto/NotoColorEmoji.ttf"]


def is_emoji(ch):
    o = ord(ch); return o >= 0x1F000 or 0x2600 <= o <= 0x27BF or o in (0x2B50, 0x2B55, 0x203C, 0x2049)


def caption_hints(text, seconds=None):
    """Soft checks against the house style of viral clip captions (reel-scout 16.11.2026). Hints only - nothing fails.
    The agent reads them in result.json ("hints") and fixes the job once if a hint is justified."""
    t = re.sub(r"\s+", " ", text or "").strip(); h = []
    if not t: return h
    words = [w for w in re.findall(r"[A-Za-z0-9$'’%.,-]+", t) if re.search(r"[A-Za-z0-9]", w)]
    emo = [c for c in t if is_emoji(c)]
    if len(words) < 8: h.append(f"Kontextsatz hat nur {len(words)} Wörter – Ziel ist ein ganzer Erzählsatz mit 9–15 Wörtern")
    if len(words) > 17: h.append(f"Kontextsatz hat {len(words)} Wörter – auf höchstens 15 kürzen")
    if not emo: h.append("kein Emoji am Ende (üblich: 😭 😂 👀 💰)")
    elif len(emo) > 3: h.append("mehr als 3 Emojis")
    elif not is_emoji(t.replace("\ufe0f", "")[-1]): h.append("Emoji gehört ans Satzende")
    if "..." not in t and "…" not in t: h.append("Satz endet nicht offen („...“ vor dem Emoji hält die Auflösung zurück)")
    caps = [w for w in words if len(w) > 2 and w.isupper() and re.search(r"[A-Z]", w)]
    if len(caps) > 3: h.append(f"{len(caps)} Wörter in Großbuchstaben – höchstens 1–2 (das überraschende Wort)")
    if t.isupper(): h.append("alles in Großbuchstaben – normale Schreibweise verwenden")
    if words and not words[0][0].isupper(): h.append("Satz beginnt nicht mit dem Namen")
    if re.search(r"[.!?] +[A-Z]", re.sub(r"\.\.\.|…", "", t)): h.append("zwei Sätze – nur EIN Satz")
    if seconds is not None and seconds > 40: h.append(f"Clip dauert {seconds:.0f} s – virale Clips liegen bei 10–38 s")
    return h


def caption_wrap(d, text, f, size, maxw):
    """Greedy wrap, then pull the lines to similar widths (a last line with one lonely word looks cheap)."""
    wlen = lambda t: sum(size * 1.08 if is_emoji(c) else d.textlength(c, font=f) for c in t)
    def wrap(mw):
        lines, cur = [], ""
        for w in text.split():
            t = (cur + " " + w).strip()
            if wlen(t) <= mw or not cur: cur = t
            else: lines.append(cur); cur = w
        return lines + ([cur] if cur else [])
    lines = wrap(maxw); n = len(lines)
    if n > 1:
        for mw in range(int(maxw * 0.62), int(maxw), 20):  # narrowest width that keeps the same number of lines
            alt = wrap(mw)
            if len(alt) == n and max(wlen(l) for l in alt) <= maxw: lines = alt; break
    return lines, wlen


def caption_box(img, text, bottom, size=46, maxw=920):
    """TikTok-style label: white rounded box, black bold text, centred, its lower edge at `bottom`.
    Short labels: 46 px, up to 3 lines. A whole story sentence (9-15 words, reel-scout 16.11.2026): shrinks to 42/38 px, up to 4 lines."""
    from PIL import Image, ImageDraw, ImageFont
    d = ImageDraw.Draw(img); ef = None
    for p_ in EMOJI_FONTS:
        try: ef = ImageFont.truetype(p_, 109); break
        except OSError: pass
    text = "".join(c for c in text if c not in "\ufe0f\u200d")
    if ef is None: text = re.sub(r"\s+", " ", "".join(c for c in text if not is_emoji(c))).strip()
    for size, maxl in ((size, 3), (42, 3), (38, 4)):
        f = pfont(size); lines, wlen = caption_wrap(d, text, f, size, maxw)
        if len(lines) <= maxl and all(wlen(l) <= maxw + 40 for l in lines): break
    else:
        raise Fail(f"caption too long ({len(text)} chars, max ~150 / 4 lines): {text!r}")
    lh = int(size * 1.28); bw = int(max(wlen(l) for l in lines)) + 52; bh = lh * len(lines) + 30
    x0 = (W - bw) // 2; y0 = int(bottom - bh)
    d.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=22, fill=(255, 255, 255, 255))
    for i, l in enumerate(lines):
        x = (W - wlen(l)) / 2; y = y0 + 15 + i * lh
        for c in l:
            if is_emoji(c):
                try:
                    g = Image.new("RGBA", (136, 128), (0, 0, 0, 0)); ImageDraw.Draw(g).text((0, 0), c, font=ef, embedded_color=True)
                    bb = g.getbbox()
                    if bb: g = g.crop(bb).resize((size, size), Image.LANCZOS); img.alpha_composite(g, (int(x + size * 0.04), int(y + size * 0.14)))
                except Exception: pass
                x += size * 1.08
            else:
                d.text((x, y), c, font=f, fill=(0, 0, 0, 255)); x += d.textlength(c, font=f)
    return y0


def overlay(title, pill, path, logo=None, logo_w=380, logo_pos="video_bottom", fg=(400, 1200), shade=False, caption=None, cap_bottom=None):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if shade:  # full-screen layout: dark top gradient keeps the title readable on bright IRL footage
        g = Image.new("L", (1, H))
        for y in range(H): g.putpixel((0, y), int(170 * max(0.0, 1 - y / 520)))
        img.putalpha(g.resize((W, H)))
    d = ImageDraw.Draw(img)
    if caption:  # context sentence instead of the big title (reference-lab style)
        caption_box(img, caption, cap_bottom if cap_bottom is not None else 330)
        if logo is not None: paste_logo(img, logo, logo_w, y_bottom=fg[0] + fg[1] - 40)
        img.save(path); return
    fs = 118
    while fs > 56 and d.textlength(title, font=ImageFont.truetype(ANTON, fs)) > W - 110: fs -= 2
    f = ImageFont.truetype(ANTON, fs); tw = d.textlength(title, font=f)
    if tw > W - 60: raise Fail(f"title too long ({len(title)} chars): {title!r}")
    head, sep, tail = title.partition(":")  # part before ':' in yellow
    x, y = (W - tw) / 2, (262 if pill else 330) - fs
    st = dict(font=f, stroke_width=7, stroke_fill=(0, 0, 0, 255))
    if sep:
        d.text((x, y), head + ":", fill=(255, 230, 0, 255), **st); x += d.textlength(head + ":", font=f)
        d.text((x, y), tail, fill=(255, 255, 255, 255), **st)
    else:
        d.text((x, y), title, fill=(255, 255, 255, 255), **st)
    if pill:
        ps = 40
        while ps > 24 and d.textlength(pill, font=pfont(ps)) > W - 130: ps -= 2
        pf = pfont(ps); pw = d.textlength(pill, font=pf); px = (W - pw) / 2 - 28
        if pw > W - 100: raise Fail(f"pill too long ({len(pill)} chars)")
        d.rounded_rectangle([px, 306, px + pw + 56, 376], radius=16, fill=(255, 230, 0, 255))
        bb = d.textbbox((0, 0), pill, font=pf)
        d.text((px + 28, 341 - (bb[1] + bb[3]) / 2), pill, font=pf, fill=(0, 0, 0, 255))
    if logo is not None:
        if logo_pos == "video_top": paste_logo(img, logo, logo_w, y_top=fg[0] + 34)
        else: paste_logo(img, logo, logo_w, y_bottom=fg[0] + fg[1] - 40)
    img.save(path)


def ts(t):
    t = max(t, 0); return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def fix_word(w, fix):
    if w in fix: return fix[w]
    m = re.match(r"^(.*?)([.,!?;:]*)$", w)
    return fix[m.group(1)] + m.group(2) if m.group(1) in fix else w


def ass(words, a, b, path, fix, margin_v=450):
    ws = [dict(w, w=fix_word(w["w"], fix)) for w in words if w["s"] >= a - 0.05 and w["e"] <= b + 0.3]
    groups, cur = [], []
    for i, w in enumerate(ws):
        cur.append(w)
        gap = ws[i + 1]["s"] - w["e"] > 0.45 if i + 1 < len(ws) else True
        if len(cur) >= 3 or re.search(r"[,.?!]$", w["w"]) or gap: groups.append(cur); cur = []
    from PIL import ImageFont
    f100 = ImageFont.truetype(ANTON, 100)
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 2\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            f"Style: C,Anton,150,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,0,0,0,0,100,100,1,0,1,9,3,2,40,40,{margin_v},1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    ev = []
    for gi, g in enumerate(groups):
        gend = g[-1]["e"] + 0.4
        if gi + 1 < len(groups): gend = min(gend, groups[gi + 1][0]["s"])
        gend = min(gend, b)
        txt = [re.sub(r"[.,]$", "", x["w"]).upper() for x in g]
        # ASS size 150 ~ Anton at 113 px; a group wider than the frame (no wrapping) gets a smaller size
        wide = f100.getlength(" ".join(txt)) * 1.13 + len(" ".join(txt)) + 18
        size = "" if wide <= W - 90 else "{\\fs%d}" % int(150 * (W - 90) / wide)
        for k, w in enumerate(g):
            s = max(w["s"], g[k - 1]["s"] + 0.08) if k else w["s"]
            e = g[k + 1]["s"] if k + 1 < len(g) else gend
            e = max(e, s + 0.08)
            line = " ".join(("{\\c&H00E6FF&}" if j == k else "{\\c&HFFFFFF&}") + t for j, t in enumerate(txt))
            ev.append(f"Dialogue: 0,{ts(s - a)},{ts(e - a)},C,,0,0,0,,{size}{line}")
    open(path, "w").write(head + "\n".join(ev) + "\n")
    return len(groups)


def check_clips(job, dur):
    lo = float(job.get("min_len", 10)); seen = set(); errs = []
    for c in job.get("clips", []):
        cid = str(c.get("id", ""))
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", cid) or cid in seen: errs.append(f"clip id {cid!r} invalid or twice"); continue
        seen.add(cid)
        try: a, b = float(c["a"]), float(c["b"])
        except Exception: errs.append(f"{cid}: a/b missing"); continue
        if not 0 <= a < b <= dur + 0.05: errs.append(f"{cid}: {a}-{b} outside the source (0-{dur:.1f} s)")
        elif b - a < lo: errs.append(f"{cid}: {b - a:.1f} s is shorter than min_len {lo:g} s")
        elif b - a > 180: errs.append(f"{cid}: longer than 180 s")
        if not str(c.get("title", "")).strip() and not str(c.get("caption", "")).strip(): errs.append(f"{cid}: title (or caption) missing")
        hk = c.get("hook")
        if hk not in (None, False, "auto"):
            try:
                hs, he = float(hk[0]), float(hk[1])
                if not (0 <= hs < he <= dur + 0.05 and 0.8 <= he - hs <= 5): errs.append(f"{cid}: hook must be 0.8-5 s inside the source")
            except Exception: errs.append(f'{cid}: hook must be [start, end] or "auto"')
    return errs


def face_track(src, a, dur, p, cw, step=0.5):
    """Left edge of a cw-wide crop (source px) every `step` s, following the biggest face; None without OpenCV/faces.
    Dead zone: the frame holds still until the face drifts > 15 % of the crop width from centre, then glides."""
    try:
        import cv2, numpy as np
        if not hasattr(cv2, "CascadeClassifier"): raise ImportError("opencv >= 5 has no CascadeClassifier (workflows pin <5)")
    except ImportError:
        print("WARN opencv missing - centre crop"); return None
    if cw >= p["w"] - 2: return None
    sw = 960; sh = max(2, int(round(p["h"] * sw / p["w"] / 2)) * 2); k = p["w"] / sw
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{dur:.3f}", "-i", src, "-an",
                        "-vf", f"fps={1 / step:g},scale={sw}:{sh},format=gray", "-f", "rawvideo", "-"], capture_output=True, timeout=900)
    nf = len(r.stdout) // (sw * sh)
    if not nf: return None
    frames = np.frombuffer(r.stdout[:nf * sw * sh], np.uint8).reshape(nf, sh, sw)
    cas = [cv2.CascadeClassifier(cv2.data.haarcascades + f) for f in ("haarcascade_frontalface_default.xml", "haarcascade_profileface.xml")]
    if cas[0].empty():  # OpenCV 5 ships no Haar files - the workflow pins opencv-python-headless<5
        print("WARN haar cascades missing - centre crop"); return None
    cas = [cc for cc in cas if not cc.empty()]
    xs, prev = [], None
    for g in frames:
        found = []
        for ci, cc in enumerate(cas):
            for img, flip in ((g, False), (cv2.flip(g, 1), True)) if ci else ((g, False),):  # profile cascade only sees left profiles
                for (x, y, w, h) in cc.detectMultiScale(img, 1.1, 5, minSize=(sh // 22, sh // 22)):
                    cx = sw - (x + w / 2) if flip else x + w / 2
                    found.append((cx, float(w * h)))
        if found:
            best = max(found, key=lambda f: f[1] * (1 - 0.5 * min(abs(f[0] - prev) / sw, 1) if prev is not None else 1))
            prev = best[0]; xs.append(best[0] * k)
        else:
            xs.append(None)
    hits = [x for x in xs if x is not None]
    if len(hits) < max(2, 0.15 * len(xs)): return None  # too few detections to trust - centre crop
    for i in range(len(xs)):  # hold the last seen position (first gap: the next one)
        if xs[i] is None: xs[i] = xs[i - 1] if i else next(x for x in xs if x is not None)
    cam = [xs[0]]; dz = 0.15 * cw
    for x in xs[1:]:
        c = cam[-1]; d = x - c
        if abs(d) > dz: c += (d - math.copysign(dz, d)) * 0.5
        cam.append(c)
    return [(round(i * step, 2), round(min(max(c - cw / 2, 0), p["w"] - cw), 1)) for i, c in enumerate(cam)]


FACECAM_PICK = "v2"   # "v1" = old median-of-everything pick (camtest compares both)


def face_clusters(d, F, nf, sw, sh):
    """d rows (cx, cy, w, frame). Greedy clusters of detections that sit in one place -> list of dicts
    {cx, cy, w, cov (share of frames with a hit), mot (median frame-to-frame change inside the box; a picture or a still character ~0)}."""
    import numpy as np
    cl = []
    for row in d:
        for c in cl:
            if abs(row[0] - c["cx"]) < 0.06 * sw and abs(row[1] - c["cy"]) < 0.09 * sh: c["rows"].append(row); c["cx"], c["cy"] = np.mean([r[:2] for r in c["rows"]], axis=0); break
        else: cl.append({"cx": row[0], "cy": row[1], "rows": [row]})
    out = []
    for c in cl:
        R = np.array(c["rows"]); cx, cy, fw = np.median(R[:, :3], axis=0); mot = None
        x0, x1, y0, y1 = max(int(cx - fw / 2), 0), min(int(cx + fw / 2), sw), max(int(cy - fw / 2), 0), min(int(cy + fw / 2), sh)
        if nf >= 4 and x1 - x0 > 4 and y1 - y0 > 4:
            mot = float(np.median(np.abs(np.diff(F[:, y0:y1, x0:x1].astype(np.int16), axis=0)).mean(axis=(1, 2))))
        out.append({"cx": float(cx), "cy": float(cy), "w": float(fw), "cov": len(set(R[:, 3].tolist())) / max(nf, 1), "n": len(R), "mot": mot})
    return out


def choose_face(cl, nf, sw, dbg_to=None):
    """Selection rules on face clusters (dicts from face_clusters) -> (cx, cy, w) or (None, None, None). Pure, so camtest reports can be replayed."""
    for c in cl:
        c["side"] = c["cx"] < 0.36 * sw or c["cx"] > 0.64 * sw
        c["small"] = c["w"] <= 0.10 * sw or (c["w"] <= 0.13 * sw and c["cov"] >= 0.6)    # jynxzi: a big cam face (11 %) seen in 70 % of the frames is real; sykkuno's 12 % corner 'face' (50 %) was not
        c["ok"] = c["cov"] >= max(3 / max(nf, 1), 0.2) and (c["mot"] is None or c["mot"] >= 1.5) and c["side"] and c["small"]
    if dbg_to is not None: dbg_to.dbg = [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in c.items() if k != "rows"} for c in cl]
    ok = sorted((c for c in cl if c["ok"]), key=lambda c: -c["cov"])
    if not ok:
        if dbg_to is not None: dbg_to.last = "no side face" if cl else None
        return None, None, None
    if len(ok) > 1 and ok[1]["cov"] > 0.6 * ok[0]["cov"] and abs(ok[1]["cx"] - ok[0]["cx"]) > 0.15 * sw:
        if dbg_to is not None: dbg_to.last = "ambiguous (two side faces)"
        return None, None, None
    c = ok[0]; return c["cx"], c["cy"], c["w"]


def pick_face(d, F, nf, sw, sh, dbg_to=None):
    """The facecam among all face clusters, or (None, None, None) = no cam found -> caller falls back to native (never a wrong crop).
    GTA/RP footage (tfue test 16.11.): the player's character is a face too, and sits in the middle of the picture, while a facecam is
    pinned to a side. So a cam cluster must (1) cover >= 20 % of the frames, (2) move (a poster or a frozen character does not),
    (3) sit in the left/right third (centre x outside 0.36-0.64 of the width), (4) have a face no wider than 10 % of the picture width
    (13 % if seen in >= 60 % of the frames; camtest 16.11.: a 12 % 'face' in a minimap corner was no cam, real cams measured 3-11 %;
    a face that big means a fullscreen cam or a texture - native is the safe layout), and (5) not be one of several comparably strong
    side clusters (a second cam / guest / false hit at > 60 % of the best one: we cannot tell which is the streamer's cam, native is safe).
    Among the rest the one seen most often wins. Measured 16.11. on 37 real Twitch clips: see pipeline/README.md."""
    return choose_face(face_clusters(d, F, nf, sw, sh), nf, sw, dbg_to)


def facecam_rect(src, a, dur, p, spec="auto"):
    """Facecam area in source px (3:2), or None. spec = [x, y, w, h] fractions, or "auto": the small face that stays put."""
    def fit(cx, cy, w):
        w = min(max(w, 0.22 * p["w"]), p["w"], p["h"] * 1.5); h = w / 1.5
        x = min(max(cx - w / 2, 0), p["w"] - w); y = min(max(cy - h / 2, 0), p["h"] - h)
        return [int(x) // 2 * 2, int(y) // 2 * 2, int(w) // 2 * 2, int(h) // 2 * 2]
    if isinstance(spec, (list, tuple)) and len(spec) == 4:
        x, y, w, h = (float(v) for v in spec)
        return fit((x + w / 2) * p["w"], (y + h / 2) * p["h"], max(w * p["w"], h * p["h"] * 1.5))
    try:
        import cv2, numpy as np
        if not hasattr(cv2, "CascadeClassifier"): raise ImportError("opencv >= 5 has no CascadeClassifier (workflows pin <5)")
    except ImportError: return None
    sw = 960; sh = max(2, int(round(p["h"] * sw / p["w"] / 2)) * 2); k = p["w"] / sw
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{dur:.3f}", "-i", src, "-an",
                        "-vf", f"fps={24 / max(dur, 1):.4f},scale={sw}:{sh},format=gray", "-f", "rawvideo", "-"], capture_output=True, timeout=600)
    nf = len(r.stdout) // (sw * sh)
    if not nf: return None
    cc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    pc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")  # streamers look at their second screen a lot
    if cc.empty(): return None
    det = []; F = np.frombuffer(r.stdout[:nf * sw * sh], np.uint8).reshape(nf, sh, sw); facecam_rect.last = None; facecam_rect.dbg = []
    for fi, g in enumerate(F):
        det += [(x + w / 2, y + h / 2, w, fi) for (x, y, w, h) in cc.detectMultiScale(g, 1.1, 5, minSize=(sh // 24, sh // 24)) if w < 0.2 * sw]
        if not pc.empty():
            det += [(x + w / 2, y + h / 2, w, fi) for (x, y, w, h) in pc.detectMultiScale(g, 1.1, 5, minSize=(sh // 24, sh // 24)) if w < 0.2 * sw]
            det += [(sw - (x + w / 2), y + h / 2, w, fi) for (x, y, w, h) in pc.detectMultiScale(cv2.flip(g, 1), 1.1, 5, minSize=(sh // 24, sh // 24)) if w < 0.2 * sw]
    if len(det) < 3: return None
    d = np.array(det)
    if FACECAM_PICK == "v2":
        cx, cy, fw = pick_face(d, F, nf, sw, sh, facecam_rect)
        if cx is None: return None
    else:  # v1 (camtest 15.11./16.11.): the median of ALL detections; with a game character in the picture it lands between character and cam
        med = np.median(d[:, :3], axis=0)
        near = d[(abs(d[:, 0] - med[0]) < 0.08 * sw) & (abs(d[:, 1] - med[1]) < 0.12 * sh)]  # a facecam does not move
        if len(near) < max(3, 0.2 * nf): return None
        cx, cy, fw = np.median(near[:, :3], axis=0)
    # camtest 15.11.2026 (16 real Twitch clips): the place was right in 13, but a poster on the wall counted as a face and the box
    # was cut around the face instead of along the cam's own border. So: (1) a real face changes between frames, a picture does not
    fx0, fx1 = max(int(cx - fw / 2), 0), min(int(cx + fw / 2), sw); fy0, fy1 = max(int(cy - fw / 2), 0), min(int(cy + fw / 2), sh)
    if nf >= 4 and fx1 - fx0 > 4 and fy1 - fy0 > 4:
        mot = float(np.median(np.abs(np.diff(F[:, fy0:fy1, fx0:fx1].astype(np.int16), axis=0)).mean(axis=(1, 2))))
        if mot < 1.5: facecam_rect.last = f"static face ({mot:.1f})"; return None
    # (2) the cam's border is an edge that is there in EVERY frame; gameplay edges come and go -> low percentile over time
    try:
        Fi = F.astype(np.int16)
        ex = np.percentile(np.abs(np.diff(Fi, axis=2)), 25, axis=0); ey = np.percentile(np.abs(np.diff(Fi, axis=1)), 25, axis=0)

        def edge(prof, lo, hi, limit, outer, cov=None):
            """Lasting edge in [lo, hi): of the strong ones the one farthest from the face (outer = -1 towards 0, +1 towards the end) -
            the room behind the streamer has lasting edges too, the cam's border lies outside them (camtest run 2).
            The picture's own edge counts when the range runs into it."""
            lo_, hi_ = max(int(lo), 0), min(int(hi), len(prof))
            if hi_ - lo_ >= 3:
                seg = prof[lo_:hi_]; base = float(np.median(prof)) + 1e-6
                if cov is not None: seg = np.where(cov[lo_:hi_] >= 0.7, seg, 0.0)  # the cam border runs along the whole side; a HUD badge / room edge covers only part of it (ninja test 16.11.)
                top = float(seg.max())
                if top >= max(6.0, 3.0 * base):
                    idx = np.nonzero(seg >= max(6.0, 3.0 * base, 0.6 * top))[0]
                    return lo_ + int(idx[0] if outer < 0 else idx[-1]) + 1
            if cov is not None: return None  # strict pass found no full-width edge: the caller falls back to the plain search
            if lo < 2: return 0
            if hi > limit - 2: return limit
            return None
        r0, r1 = max(int(cy - 0.8 * fw), 0), min(int(cy + 1.2 * fw), sh)
        px = ex[r0:r1].mean(axis=0)
        L = edge(px, cx - 3.6 * fw, cx - 0.6 * fw, sw, -1); R = edge(px, cx + 0.6 * fw, cx + 3.6 * fw, sw, 1)
        if L is not None and R is not None and R - L >= 1.6 * fw:
            cs = slice(max(L + 2, 0), max(R - 2, L + 3)); py = ey[:, cs].mean(axis=1); pyc = (ey[:, cs] >= 2.0).mean(axis=1)
            tl, bl = (cy - 2.6 * fw, cy - 0.6 * fw), (cy + 0.8 * fw, cy + 3.4 * fw)
            T = edge(py, *tl, sh, -1, pyc); B = edge(py, *bl, sh, 1, pyc)
            if T is None: T = edge(py, *tl, sh, -1)
            if B is None: B = edge(py, *bl, sh, 1)
            if T is not None and B is not None and B - T >= 1.4 * fw:
                w = min(R - L, (B - T) * 1.5)
                if 1.8 * fw <= w <= 4.6 * fw:  # wider = not a cam border but something behind a cut-out streamer (camtest run 3)
                    h = w / 1.5; x = min(max(cx - w / 2, L), R - w); y = min(max(cy + 0.15 * fw - h / 2, T), B - h)
                    facecam_rect.last = "border"
                    return [int(x * k) // 2 * 2, int(y * k) // 2 * 2, int(w * k) // 2 * 2, int(h * k) // 2 * 2]
    except Exception as e: print("WARN facecam border:", str(e)[-200:])
    if FACECAM_PICK == "v2" and 0.30 * sw <= cx <= 0.70 * sw:  # no border found AND not at a side: nothing marks this as a cam (camtest 16.11.)
        facecam_rect.last = "face without border near the centre"; return None
    facecam_rect.last = "face"
    return fit(cx * k, (cy + 0.3 * fw) * k, min(4.4 * fw, 0.42 * sw) * k)


def x_expr(keys):
    """[(t, x)] -> ffmpeg expression in t (piecewise linear, holds collapsed). Single-quoted inside the filtergraph."""
    pts = [keys[0]]
    for i, kk in enumerate(keys[1:], 1):
        nxt = keys[i + 1] if i + 1 < len(keys) else None
        if abs(kk[1] - pts[-1][1]) < 1.5 and nxt and abs(nxt[1] - kk[1]) < 1.5: continue  # inside a hold
        pts.append(kk)
    if len(pts) > 90: pts = pts[::math.ceil(len(pts) / 90)] + [pts[-1]]
    e = f"{pts[-1][1]:.1f}"
    for (t0, x0), (t1, x1) in reversed(list(zip(pts, pts[1:]))):
        e = f"if(lt(t,{t1:.2f}),{x0:.1f}+({x1 - x0:.1f})*(t-{t0:.2f})/{max(t1 - t0, 0.01):.2f},{e})"
    return e


def energy(src, a, dur, step=0.1):
    """RMS in dB every `step` s of [a, a+dur] (smoothed over 0.3 s); empty array without audio."""
    import numpy as np
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{dur:.3f}", "-i", src, "-vn", "-ac", "1", "-ar", "8000",
                        "-f", "s16le", "-"], capture_output=True, timeout=600)
    n = int(8000 * step); k = len(r.stdout) // 2 // n
    if k < 10: return np.zeros(0, dtype=np.float32)
    x = np.frombuffer(r.stdout[:k * n * 2], np.int16).astype(np.float32).reshape(k, n) / 32768
    db = 20 * np.log10(np.sqrt((x ** 2).mean(1)) + 1e-5)
    return np.convolve(db, np.ones(3) / 3, mode="same").astype(np.float32)


def punch_times(db, step=0.1, every=4.0, lead=1.2, tail=1.0, min_db=6.0):
    """Moments (s) that stand out >= min_db above the clip's median loudness: best first, >= 3 s apart, max one per `every` s."""
    import numpy as np
    if not len(db): return []
    ex = db - float(np.median(db)); dur = len(db) * step; out = []
    for i in np.argsort(-ex):
        t = float(i) * step
        if ex[i] < min_db or len(out) >= max(1, int(dur / every)): break
        if t < lead or t > dur - tail or any(abs(t - o) < 3.0 for o in out): continue
        out.append(round(t, 2))
    return sorted(out)


def zoom_expr(times, amount=0.08):
    """ffmpeg expression in t: 1 + quick punch-ins (0.12 s in, hold, 0.35 s out) at the given moments."""
    return "1" + "".join(f"+{amount}*clip(min((t-{max(t0 - 0.1, 0):.2f})/0.12,({t0 + 0.85:.2f}-t)/0.35),0,1)" for t0 in times)


def auto_hook(db, words, a, b, step=0.1, min_db=5.0):
    """Loudest moment after the first 5 s of the clip, snapped to whole words -> [s, e] in source seconds, or None."""
    import numpy as np
    if len(db) < int(8 / step): return None
    ex = db - float(np.median(db)); lo = int(5 / step); hi = len(db) - int(1 / step)
    if hi <= lo: return None
    i = lo + int(np.argmax(ex[lo:hi]))
    if ex[i] < min_db: return None
    pk = a + i * step
    ws = [w for w in words if w["e"] > pk - 0.9 and w["s"] < pk + 1.3 and w["s"] >= a and w["e"] <= b]
    s, e = (ws[0]["s"] - 0.05, ws[-1]["e"] + 0.12) if ws else (pk - 0.8, pk + 1.2)
    if not 1.2 <= e - s <= 3.4: s, e = pk - 0.8, pk + 1.2
    s, e = max(s, a), min(e, b)
    return [round(s, 2), round(e, 2)] if e - s >= 1.0 else None


def render_clip(job, c, src, p, words, out, tmp):
    a, b = float(c["a"]), min(float(c["b"]), p["dur"]); cid = c["id"]
    capt = str(c.get("caption") or "").strip()
    title = str(c.get("title") or capt[:40]).strip().upper(); pill = c.get("pill", job.get("pill")) or ""
    layout = c.get("layout", job.get("layout", "framed")); track = c.get("track", job.get("track", False))
    cam = facecam_rect(src, a, b - a, p, c.get("facecam", job.get("facecam", "auto"))) if layout == "split" else None
    if layout == "split" and not cam: layout = "native"; print(f"WARN {cid}: no facecam found - layout native")
    full = layout == "full"; native = layout == "native"; split = layout == "split"
    zoom = bool(c.get("zoom", job.get("zoom", full))) and p["audio"]
    ov = os.path.join(tmp, cid + ".png")
    caps = c.get("captions", not (native or split)) and bool(words); capb = None
    if split:  # facecam 1080x720 on top, gameplay 1080x1200 (centre of the picture) below
        fg_y, fg_h = 720, 1200; ch = p["h"] // 2 * 2; cw = min(p["w"], int(ch * W / fg_h / 2) * 2); mv = 150; capb = 786; track = False
        gx = (p["w"] - cw) // 2 // 2 * 2  # gameplay window: centre of the picture, nudged sideways (at most 20 %) when that clears the cam completely (tarik test 16.11.)
        if cam[0] + cam[2] > gx and cam[0] < gx + cw:
            g2 = cam[0] + cam[2] if cam[0] + cam[2] / 2 < p["w"] / 2 else cam[0] - cw
            if 0 <= g2 <= p["w"] - cw and abs(g2 - gx) <= 0.2 * cw: gx = g2 // 2 * 2
    elif native:  # whole picture, nothing cropped away (how viral streamer clips are posted)
        fg_h = min(FG_H, int(W * p["h"] / p["w"] / 2) * 2); fg_y = (H - fg_h) // 2
        cw = p["w"] // 2 * 2; ch = min(p["h"], int(cw * fg_h / W / 2) * 2); mv = H - (fg_y + fg_h) + 60
    elif full:  # whole frame 9:16 out of the source, captions in the lower third
        ch = p["h"] // 2 * 2; cw = min(p["w"], int(ch * W / H / 2) * 2); ch = min(ch, int(cw * H / W / 2) * 2)
        fg_y, fg_h = 0, H; mv = 520
    else:
        fg_h = FG_H if not c.get("wide") else int(W / (0.75 * p["w"] / p["h"]) / 2) * 2  # wide: 75 % of the source width visible
        fg_h = min(fg_h, FG_H); fg_y = FG_Y + (FG_H - fg_h) // 2
        cw = min(p["w"], int(p["h"] * W / fg_h / 2) * 2); ch = min(p["h"], int(cw * fg_h / W / 2) * 2)  # also fits portrait sources
        mv = H - (fg_y + fg_h) + 130
    overlay(title, pill, ov, logo=job.get("_logo_img"), logo_w=int(c.get("logo_w", job.get("logo_w", 380))),
            logo_pos=c.get("logo_pos", job.get("logo_pos", "video_bottom")), fg=(fg_y, fg_h), shade=full and not capt,
            caption=capt or None, cap_bottom=capb if split else (None if full else fg_y - 18))
    fps = min(60, max(24, round(p["fps"])))
    db = energy(src, a, b - a) if p["audio"] and (zoom or c.get("hook") == "auto") else []
    hook = c.get("hook")
    if hook == "auto": hook = auto_hook(db, words, a, b)
    if hook and not p["audio"]: hook = None
    parts = ([("hook", float(hook[0]), float(hook[1]))] if hook else []) + [("main", a, b)]
    stats = {"groups": 0, "tracked": False, "punches": 0}; files = []
    for tag, pa, pb in parts:
        dur = pb - pa; sub = os.path.join(tmp, f"{cid}_{tag}.ass"); n = 0
        keys = face_track(src, pa, dur, p, cw) if track else None
        xpos = f":x='{x_expr(keys)}':y={(p['h'] - ch) // 2}" if keys else ""
        if caps: n = ass(words, pa, pb, sub, job.get("fix") or {}, margin_v=mv)
        pts = punch_times(db) if zoom and tag == "main" else []
        zw, zh = (W, H) if full else (W, fg_h)
        zf = (f",scale=w='2*trunc({zw}*({zoom_expr(pts)})/2)':h='2*trunc({zh}*({zoom_expr(pts)})/2)':eval=frame:flags=bilinear,"
              f"crop={zw}:{zh}:x='(iw-ow)/2':y='(ih-oh)*0.42'") if pts else ""
        if split:
            fl = (f"[0:v]split=2[c0][g0];[c0]crop={cam[2]}:{cam[3]}:{cam[0]}:{cam[1]},scale={W}:720:flags=lanczos,setsar=1[top];"
                  f"[g0]crop={cw}:{ch}:{gx}:{(p['h'] - ch) // 2},scale={W}:{fg_h}:flags=lanczos{zf},setsar=1[bot];[top][bot]vstack[v1];[v1][1:v]overlay=0:0[v2];[v2]")
        elif full:
            fl = f"[0:v]crop={cw}:{ch}{xpos},scale={W}:{H}:flags=lanczos{zf},setsar=1[v1];[v1][1:v]overlay=0:0[v2];[v2]"
        else:
            fl = (f"[0:v]split=2[b0][f0];"
                  f"[b0]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=6:2,scale={W}:{H},eq=brightness=-0.22:saturation=1.1[bg];"
                  f"[f0]crop={cw}:{ch}{xpos},scale={W}:{fg_h}:flags=lanczos{zf}[fg];"
                  f"[bg][fg]overlay=0:{fg_y}[v1];[v1][1:v]overlay=0:0[v2];[v2]")
        fl += (f"subtitles={sub}:fontsdir={FONTS}," if caps and n else "") + f"fps={fps},format=yuv420p"
        if hook and tag == "main": fl += ",fade=t=in:st=0:d=0.14:color=white"  # flash cut from the teaser into the clip
        fl += "[v]"
        amap = ["-an"]
        if p["audio"]:
            fi, fo = (0.04, 0.08) if tag == "hook" else ((0.08 if hook else 0.12), 0.35)
            fl += f";[0:a]afade=t=in:d={fi},afade=t=out:st={dur - fo:.2f}:d={fo}[a]"
            amap = ["-map", "[a]", "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
        pf = os.path.join(tmp, f"{cid}_{tag}.mp4") if len(parts) > 1 else os.path.join(out, f"{job['name']}_{cid}.mp4")
        q = ["-preset", "veryfast", "-crf", "14"] if len(parts) > 1 else ["-preset", "medium", "-crf", "19", "-maxrate", "9M", "-bufsize", "18M"]
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{pa:.3f}", "-t", f"{dur:.3f}", "-i", src, "-i", ov, "-filter_complex", fl,
             "-map", "[v]", *amap, "-t", f"{dur:.3f}", "-c:v", "libx264", *q, "-movflags", "+faststart", pf])
        files.append(pf)
        if tag == "main": stats.update(groups=n, tracked=bool(keys), punches=len(pts))
    dst = os.path.join(out, f"{job['name']}_{cid}.mp4"); total = sum(pb - pa for _, pa, pb in parts)
    if len(files) > 1:  # teaser + clip -> one file (re-encode once: exact A/V sync at the join)
        ins = sum([["-i", f] for f in files], [])
        cf = "".join(f"[{i}:v][{i}:a]" for i in range(len(files))) + f"concat=n={len(files)}:v=1:a=1[v][a]"
        run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", cf, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium",
             "-crf", "19", "-maxrate", "9M", "-bufsize", "18M", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", dst])
        for f in files: os.remove(f)
    q = probe(dst)
    if (q["w"], q["h"]) != (W, H) or abs(q["dur"] - total) > 0.6: raise Fail(f"{cid}: output check failed {q}")
    png = os.path.join(out, "qa", f"{job['name']}_{cid}.jpg"); os.makedirs(os.path.dirname(png), exist_ok=True)
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{total * 0.4:.2f}", "-i", dst, "-frames:v", "1", "-vf", "scale=540:-2", "-q:v", "4", png])
    print(f"CLIP_OK {dst} {total:.1f}s caption groups {stats['groups']} layout {layout} tracked {stats['tracked']} "
          f"punches {stats['punches']} hook {hook}")
    r = {"id": cid, "ok": True, "seconds": round(q["dur"], 2), "title": title, "file": os.path.basename(dst), "qa": "qa/" + os.path.basename(png),
         "layout": layout, "tracked": stats["tracked"], "punches": stats["punches"]}
    if hook: r["hook"] = [round(float(hook[0]), 2), round(float(hook[1]), 2)]
    if capt:
        r["caption"] = capt; hints = caption_hints(capt, q["dur"])
        if hints: r["hints"] = hints; print(f"HINT {cid}: " + "; ".join(hints))
    return r


def sig(*parts):
    return hashlib.sha1(json.dumps(parts, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


V3_KEYS = ("layout", "track", "max_height", "hot_k", "zoom", "facecam")


def v3(job):
    """New job fields - only part of the signatures when set, so v2 jobs keep their old signature (no re-render)."""
    return [{k: job[k] for k in V3_KEYS if k in job}] if any(k in job for k in V3_KEYS) else []


def job_sig(job):
    return sig(job.get("source"), job.get("pill"), job.get("fix"), job.get("clips"), job.get("min_len"),
               *([job.get("logo"), job.get("logo_w"), job.get("logo_pos")] if job.get("logo") else []), *v3(job))


def pending(root, outdir):
    """Jobs that still need work: clipjobs/*.json in the repo + clipjob-*.json in the public Drive folder (DRIVE_FOLDER).
    Prints a JSON list of spec paths (max 4 per run)."""
    import glob, html, urllib.request
    os.makedirs(outdir, exist_ok=True); specs = []
    for f in sorted(glob.glob(os.path.join(root, "clipjobs", "*.json"))):
        try: specs.append((json.load(open(f)), f))
        except Exception as e: print(f"skip {f}: {e}", file=sys.stderr)
    folder = os.environ.get("DRIVE_FOLDER", "").strip()
    if folder:
        try:
            ua = {"User-Agent": "Mozilla/5.0"}; get = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers=ua), timeout=30).read().decode("utf-8", "replace")
            page = get(f"https://drive.google.com/embeddedfolderview?id={folder}")
            for fid, title in re.findall(r'href="https://drive\.google\.com/file/d/([\w-]{20,})/[^"]*"[^>]*>.*?flip-entry-title">([^<]+)<', page, re.S):
                if not re.match(r"clipjob-.*\.json$", html.unescape(title).strip()): continue
                m = re.search(r"\{.*\}", get(f"https://drive.google.com/uc?export=download&id={fid}"), re.S)
                if m: specs.append((json.loads(m.group(0)), "drive:" + title))
        except Exception as e:
            print(f"drive folder not readable ({e})", file=sys.stderr)
    out, seen = [], set()
    for job, src in reversed(specs):  # Drive version (newer, written by the agent) wins over the repo file of the same name
        name = re.sub(r"[^a-z0-9_-]", "", str(job.get("name", "")).lower())
        if not name or name in seen or not job.get("source"): continue
        seen.add(name)
        try: prev = json.load(open(os.path.join(root, "clips", name, "result.json")))
        except Exception: prev = {}
        if prev.get("sig") == job_sig(job) and (prev.get("ok") or prev.get("attempts", 1) >= 3): continue
        p = os.path.join(outdir, name + ".json"); json.dump(job, open(p, "w"), ensure_ascii=False); out.append(p)
        print(f"pending: {name} ({src})", file=sys.stderr)
    print(json.dumps(out[:4]))


def run_job(spec_path, root, src=None):
    """Do what the job still needs. Always writes clips/<name>/result.json; exit code 0 so the workflow publishes it."""
    job = json.load(open(spec_path)); name = re.sub(r"[^a-z0-9_-]", "", str(job.get("name", "")).lower())
    if not name: sys.exit("job without name")
    job["name"] = name; out = os.path.join(root, "clips", name); sc = os.path.join(out, "scan"); os.makedirs(sc, exist_ok=True)
    tmp = os.path.join(os.environ.get("RUNNER_TEMP", "/tmp"), "cf_" + name); os.makedirs(tmp, exist_ok=True)
    rp = os.path.join(out, "result.json")
    try: prev = json.load(open(rp))
    except Exception: prev = {}
    jsig = job_sig(job)
    res = {"ok": False, "name": name, "sig": jsig, "attempts": prev.get("attempts", 0) + 1 if prev.get("sig") == jsig else 1,
           "source": job.get("source"), "scan": f"{RAW}/clips/{name}/scan/scan.json", "clips": []}
    try:
        heat = None; url = str(job.get("source", "")); sect = False
        try: old = json.load(open(os.path.join(sc, "scan.json")))
        except Exception: old = {}
        have_scan = old.get("source") == job.get("source") and os.path.exists(os.path.join(sc, "words.json"))
        if not src and is_stream(url):  # VOD page: low resolution is enough for the scan, renders get max_height
            d_ = remote_dur(url); long_ = bool(job.get("sections", d_ > 3 * 3600))  # > 3 h: scan at 360p, render clip sections only
            h = 360 if long_ else 480
            if job.get("clips"):
                h = int(job.get("max_height", 0) or 0) or 1080
                sect = long_ and have_scan
            if sect:
                p = {"dur": float(old.get("duration") or d_), "w": old.get("width"), "h": old.get("height"), "fps": old.get("fps") or 30, "audio": True}
            else:
                if job.get("clips") and long_: h = min(h, 720)  # no scan yet + long stream: full download must fit the runner disk
                src, p, info = ytdlp(url, tmp, h); heat = info.get("heatmap")
        elif not src:
            src = os.path.join(tmp, "source.mp4"); p = download(url, src)
        else: p = probe(src)
        if not have_scan:
            for f in os.listdir(sc): os.remove(os.path.join(sc, f))
            scan(src, sc, lo=float(job.get("min_len", 10)), model=job.get("whisper", "small.en"), heat=heat, hot_k=int(job.get("hot_k", 14)))
            d = json.load(open(os.path.join(sc, "scan.json"))); d["source"] = job.get("source")
            json.dump(d, open(os.path.join(sc, "scan.json"), "w"), indent=1, ensure_ascii=False)
        words = json.load(open(os.path.join(sc, "words.json")))
        errs = check_clips(job, p["dur"])
        if errs: raise Fail("job rejected: " + "; ".join(errs))
        job["_logo_img"] = load_logo(job.get("logo"), root)
        done = {c["id"]: c for c in prev.get("clips", []) if c.get("ok")}
        for c in job.get("clips", []):
            csig = sig(job.get("source"), c.get("pill", job.get("pill")), job.get("fix"), c,
                       *([job.get("logo"), job.get("logo_w"), job.get("logo_pos")] if job.get("logo") else []),
                       *v3({k: job[k] for k in ("layout", "track", "zoom", "facecam") if k in job}))
            d = done.get(c["id"])
            if d and d.get("sig") == csig and os.path.exists(os.path.join(out, d["file"])):
                res["clips"].append(d); continue
            try:
                if sect:  # long stream: fetch only this clip (+3 s margin) and render it on its own timeline
                    hk = c.get("hook") if isinstance(c.get("hook"), (list, tuple)) else None
                    lo_ = min(float(c["a"]), float(hk[0])) if hk else float(c["a"]); hi_ = max(float(c["b"]), float(hk[1])) if hk else float(c["b"])
                    if hi_ - lo_ > 300: raise Fail(f"{c['id']}: hook is more than 5 min away from the clip (long-stream mode)")
                    a0 = max(0.0, lo_ - 3); seg = os.path.join(tmp, f"sec_{c['id']}.mp4")
                    ps = fetch_section(url, a0, min(hi_ + 3, p["dur"]), h, seg)
                    c2 = dict(c, a=float(c["a"]) - a0, b=float(c["b"]) - a0)
                    if hk: c2["hook"] = [float(hk[0]) - a0, float(hk[1]) - a0]
                    w2 = [dict(w, s=round(w["s"] - a0, 3), e=round(w["e"] - a0, 3)) for w in words if a0 <= w["s"] and w["e"] <= hi_ + 3]
                    r = render_clip(job, c2, seg, ps, w2, out, tmp); os.remove(seg)
                else:
                    r = render_clip(job, c, src, p, words, out, tmp)
                r["sig"] = csig
                r["url"] = f"{RAW}/clips/{name}/{r['file']}"; r["qa"] = f"{RAW}/clips/{name}/{r['qa']}"
            except Exception as e:
                r = {"id": c["id"], "ok": False, "error": str(e)[-600:]}
            res["clips"].append(r)
        keep = {c.get("file") for c in res["clips"]} | {os.path.basename(c.get("qa", "")) for c in res["clips"]}
        for d_, pre in ((out, f"{name}_"), (os.path.join(out, "qa"), f"{name}_")):  # drop clips that left the job
            for f in (os.listdir(d_) if os.path.isdir(d_) else []):
                if f.startswith(pre) and f.endswith((".mp4", ".jpg")) and f not in keep: os.remove(os.path.join(d_, f))
        bad = [c["id"] for c in res["clips"] if not c.get("ok")]
        res["ok"] = not bad
        res["phase"] = "rendered" if job.get("clips") else "scanned"  # scanned = waiting for the agent to add clips
        if bad: res["error"] = "failed clips: " + ", ".join(bad)
    except Exception as e:
        res["error"] = str(e)[-900:]
    json.dump(res, open(rp, "w"), indent=1, ensure_ascii=False)
    print(("CLIPFABRIK_OK " if res["ok"] else "CLIPFABRIK_FAIL ") + name + " " + res.get("phase", "") + " " + res.get("error", ""))


if __name__ == "__main__":
    a = sys.argv[1:]
    try:
        if len(a) >= 3 and a[0] == "run": run_job(a[1], a[2], a[3] if len(a) > 3 else None)
        elif len(a) == 3 and a[0] == "pending": pending(a[1], a[2])
        elif len(a) >= 3 and a[0] == "scan": scan(a[1], a[2], *(float(x) if i else int(x) for i, x in enumerate(a[3:6])))
        elif len(a) == 5 and a[0] == "render":
            job = json.load(open(a[1])); p = probe(a[2]); os.makedirs(a[4], exist_ok=True)
            job["_logo_img"] = load_logo(job.get("logo"), os.getcwd())
            errs = check_clips(job, p["dur"])
            if errs: raise Fail("; ".join(errs))
            for c in job["clips"]: render_clip(job, c, a[2], p, json.load(open(a[3])), a[4], a[4])
        else: sys.exit(__doc__)
    except Fail as e:
        sys.exit(str(e))
