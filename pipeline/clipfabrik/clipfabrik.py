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
              "captions": false, "rev": n (raise to re-render)}]
            no "clips" yet -> scan only: the agent reads clips/<name>/scan/scan.json + cand_XX.jpg and adds them.
Result: clips/<name>/result.json {"ok", "sig", "attempts", "clips": [{"id", "ok", "url", "seconds", "title"}], "error"}.
Layout 1080x1920: blurred fill, sharp centre crop 1080x1200 at y=400, title (+ pill) on top, karaoke captions (libass)."""
import hashlib, json, os, re, subprocess, sys, urllib.parse

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


def scan(src, out, n=6, lo=10.0, hi=24.0, model="small.en"):
    os.makedirs(out, exist_ok=True); p = probe(src)
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
    json.dump({"duration": round(p["dur"], 2), "width": p["w"], "height": p["h"], "fps": round(p["fps"], 2), "cuts": cuts,
               "sentences": sents, "candidates": cands}, open(os.path.join(out, "scan.json"), "w"), indent=1, ensure_ascii=False)
    print(f"SCAN_OK {p['dur']:.1f}s {len(words)} words {len(sents)} sentences {len(cands)} candidates")


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


def overlay(title, pill, path, logo=None, logo_w=380, logo_pos="video_bottom", fg=(400, 1200)):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
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
        if not str(c.get("title", "")).strip(): errs.append(f"{cid}: title missing")
    return errs


def render_clip(job, c, src, p, words, out, tmp):
    a, b = float(c["a"]), min(float(c["b"]), p["dur"]); dur = b - a; cid = c["id"]
    title = str(c["title"]).strip().upper(); pill = c.get("pill", job.get("pill")) or ""
    ov = os.path.join(tmp, cid + ".png"); sub = os.path.join(tmp, cid + ".ass")
    caps = c.get("captions", True) and bool(words); n = 0
    fg_h = FG_H if not c.get("wide") else int(W / (0.75 * p["w"] / p["h"]) / 2) * 2  # wide: 75 % of the source width visible
    fg_h = min(fg_h, FG_H); fg_y = FG_Y + (FG_H - fg_h) // 2
    overlay(title, pill, ov, logo=job.get("_logo_img"), logo_w=int(c.get("logo_w", job.get("logo_w", 380))),
            logo_pos=c.get("logo_pos", job.get("logo_pos", "video_bottom")), fg=(fg_y, fg_h))
    cw = min(p["w"], int(p["h"] * W / fg_h / 2) * 2); ch = min(p["h"], int(cw * fg_h / W / 2) * 2)  # also fits portrait sources
    if caps: n = ass(words, a, b, sub, job.get("fix") or {}, margin_v=H - (fg_y + fg_h) + 130)
    fps = min(60, max(24, round(p["fps"])))
    dst = os.path.join(out, f"{job['name']}_{cid}.mp4")
    fl = (f"[0:v]split=2[b0][f0];"
          f"[b0]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=6:2,scale={W}:{H},eq=brightness=-0.22:saturation=1.1[bg];"
          f"[f0]crop={cw}:{ch},scale={W}:{fg_h}:flags=lanczos[fg];"
          f"[bg][fg]overlay=0:{fg_y}[v1];[v1][1:v]overlay=0:0[v2];[v2]"
          + (f"subtitles={sub}:fontsdir={FONTS}," if caps and n else "") + f"fps={fps},format=yuv420p[v]")
    amap = ["-an"]
    if p["audio"]:
        fl += f";[0:a]afade=t=in:d=0.12,afade=t=out:st={dur - 0.35:.2f}:d=0.35[a]"
        amap = ["-map", "[a]", "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{dur:.3f}", "-i", src, "-i", ov, "-filter_complex", fl,
         "-map", "[v]", *amap, "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
         "-maxrate", "9M", "-bufsize", "18M", "-movflags", "+faststart", dst])
    q = probe(dst)
    if (q["w"], q["h"]) != (W, H) or abs(q["dur"] - dur) > 0.6: raise Fail(f"{cid}: output check failed {q}")
    png = os.path.join(out, "qa", f"{job['name']}_{cid}.jpg"); os.makedirs(os.path.dirname(png), exist_ok=True)
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{dur * 0.4:.2f}", "-i", dst, "-frames:v", "1", "-vf", "scale=540:-2", "-q:v", "4", png])
    print(f"CLIP_OK {dst} {dur:.1f}s caption groups {n}")
    return {"id": cid, "ok": True, "seconds": round(q["dur"], 2), "title": title, "file": os.path.basename(dst), "qa": "qa/" + os.path.basename(png)}


def sig(*parts):
    return hashlib.sha1(json.dumps(parts, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def job_sig(job):
    return sig(job.get("source"), job.get("pill"), job.get("fix"), job.get("clips"), job.get("min_len"),
               *([job.get("logo"), job.get("logo_w"), job.get("logo_pos")] if job.get("logo") else []))


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
        if not src:
            src = os.path.join(tmp, "source.mp4"); p = download(str(job.get("source", "")), src)
        else: p = probe(src)
        try: old = json.load(open(os.path.join(sc, "scan.json")))
        except Exception: old = {}
        if old.get("source") != job.get("source") or not os.path.exists(os.path.join(sc, "words.json")):
            for f in os.listdir(sc): os.remove(os.path.join(sc, f))
            scan(src, sc, lo=float(job.get("min_len", 10)), model=job.get("whisper", "small.en"))
            d = json.load(open(os.path.join(sc, "scan.json"))); d["source"] = job.get("source")
            json.dump(d, open(os.path.join(sc, "scan.json"), "w"), indent=1, ensure_ascii=False)
        words = json.load(open(os.path.join(sc, "words.json")))
        errs = check_clips(job, p["dur"])
        if errs: raise Fail("job rejected: " + "; ".join(errs))
        job["_logo_img"] = load_logo(job.get("logo"), root)
        done = {c["id"]: c for c in prev.get("clips", []) if c.get("ok")}
        for c in job.get("clips", []):
            csig = sig(job.get("source"), c.get("pill", job.get("pill")), job.get("fix"), c,
                       *([job.get("logo"), job.get("logo_w"), job.get("logo_pos")] if job.get("logo") else []))
            d = done.get(c["id"])
            if d and d.get("sig") == csig and os.path.exists(os.path.join(out, d["file"])):
                res["clips"].append(d); continue
            try:
                r = render_clip(job, c, src, p, words, out, tmp); r["sig"] = csig
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
