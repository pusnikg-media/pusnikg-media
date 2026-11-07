"""Pusnik G campaign clipper (0 credits): official landscape trailer -> 1080x1920 campaign clip.
No music, no AI voice: only the original trailer audio (clipping-campaign rules).
Usage: python3 campaign_clip.py job.json
job.json:
  src        official source video (from the campaign's content folder)
  out        output mp4
  start,end  segment in seconds
  top_text   on-screen text (must describe what is really in the clip)
  logo       optional PNG (official logo, required by some campaigns)
  zoom       foreground zoom on the 16:9 frame (default 1.35 = sides slightly cropped)
  captions   true -> word-by-word captions of the trailer dialogue (faster-whisper)
Layout (TikTok/Reels/Shorts safe zones): logo 150-300, text ~410, video 560-1380, captions ~1480."""
import json, os, re, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 1080, 1920, 30
ANTON = os.path.join(HERE, "fonts", "Anton-Regular.ttf")
YELLOW, PINK = (255, 230, 0), (255, 46, 136)
VID_Y = 560


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit("FFMPEG FAIL: " + " ".join(cmd)[:300] + "\n" + r.stderr[-1500:])
    return r.stdout


def font(s):
    try:
        return ImageFont.truetype(ANTON, s)
    except OSError:
        return ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf", s)


def wrap(d, text, f, maxw):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    return lines + ([cur] if cur else [])


def static_overlay(job, vid_h):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    # thin frame lines around the video for a clean "cinema card" look
    d.rectangle([0, VID_Y - 6, W, VID_Y - 1], fill=(255, 255, 255, 60))
    d.rectangle([0, VID_Y + vid_h, W, VID_Y + vid_h + 5], fill=(255, 255, 255, 60))
    if job.get("logo"):
        lg = Image.open(job["logo"]).convert("RGBA")
        lw = job.get("logo_w", 380); lh = int(lg.height * lw / lg.width)
        if lh > 150: lh = 150; lw = int(lg.width * lh / lg.height)
        lg = lg.resize((lw, lh), Image.LANCZOS)
        img.alpha_composite(lg, ((W - lw) // 2, 150 + (150 - lh) // 2))
    text = job.get("top_text", "").upper()
    if text:
        size = 96
        while True:
            f = font(size); lines = wrap(d, text, f, W - 120)
            if len(lines) <= 2 or size <= 64: break
            size -= 6
        lh = f.size * 1.08; y0 = 420 - lh * len(lines) / 2
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0)); gd = ImageDraw.Draw(glow)
        for i, l in enumerate(lines):
            x = (W - d.textlength(l, font=f)) / 2
            gd.text((x, y0 + i * lh), l, font=f, fill=PINK + (200,), stroke_width=12, stroke_fill=PINK + (200,))
        img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(18)))
        for i, l in enumerate(lines):
            x = (W - d.textlength(l, font=f)) / 2
            d.text((x, y0 + i * lh), l, font=f, fill=(255, 255, 255, 255), stroke_width=7, stroke_fill=(0, 0, 0, 255))
    return img


def caption_png(words, hi, cy=1480):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    size = 84
    while True:
        f = font(size); sp = d.textlength(" ", font=f)
        tw = sum(d.textlength(w, font=f) for w in words) + sp * (len(words) - 1)
        if tw <= W - 140 or size <= 56: break
        size -= 4
    x = (W - tw) / 2; y = cy - f.size / 2
    for i, w in enumerate(words):
        col = YELLOW if i == hi else (255, 255, 255)
        d.text((x, y), w, font=f, fill=col + (255,), stroke_width=7, stroke_fill=(0, 0, 0, 255))
        x += d.textlength(w, font=f) + sp
    return img


def transcribe(wav):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return []
    import numpy as np, scipy.io.wavfile as wavf
    _, a = wavf.read(wav); a = a.astype(np.float32) / 32768  # 16 kHz mono from ffmpeg (avoids PyAV decode issues)
    m = WhisperModel(os.environ.get("WHISPER_MODEL", "small.en"), device="cpu", compute_type="int8")
    segs, _ = m.transcribe(a, word_timestamps=True, beam_size=5, vad_filter=True)
    return [(w.word.strip(), w.start, w.end) for s in segs for w in s.words if w.word.strip()]


def groups(words):
    out, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= 3 or re.search(r"[,.?!]$", w[0]):
            out.append(cur); cur = []
    if cur: out.append(cur)
    return out


def main():
    job = json.load(open(sys.argv[1])); tmp = tempfile.mkdtemp(prefix="cc_")
    s, e = float(job["start"]), float(job["end"]); dur = e - s
    if dur < 10.5: sys.exit("clip must be >10 s (campaign minimum is 10 s)")
    z = job.get("zoom", 1.35)
    fw = int(W * z) // 2 * 2; fh = int(fw * 9 / 16) // 2 * 2; vid_h = fh
    wav = os.path.join(tmp, "a.wav")
    run(["ffmpeg", "-y", "-ss", f"{s:.3f}", "-t", f"{dur:.3f}", "-i", job["src"], "-vn", "-ac", "1", "-ar", "16000", wav])
    words = transcribe(wav) if job.get("captions", True) else []
    # manual caption fixes (Whisper mishears names): {"<word index>": "NEW"} ; "" drops the word
    fixes = {int(k): v for k, v in job.get("fix", {}).items()}
    words = [(fixes.get(i, w[0]), w[1], w[2]) for i, w in enumerate(words) if fixes.get(i, w[0]) != ""]
    print("WORDS:", " ".join(w[0] for w in words))
    ovs = []
    p = os.path.join(tmp, "static.png"); static_overlay(job, vid_h).save(p); ovs.append((p, 0, dur))
    for gi, g in enumerate(groups(words)):
        texts = [re.sub(r"[^\w'?!-]", "", w[0]).upper() for w in g]
        g_end = g[-1][2] + 0.25
        for wi, w in enumerate(g):
            a = w[1]; b = g[wi + 1][1] if wi + 1 < len(g) else min(g_end, dur)
            p = os.path.join(tmp, f"c{gi:03d}_{wi}.png"); caption_png(texts, wi).save(p); ovs.append((p, a, b))
    inputs = ["-ss", f"{s:.3f}", "-t", f"{dur:.3f}", "-i", job["src"]]
    for p, _, _ in ovs: inputs += ["-i", p]
    fl = (f"[0:v]fps={FPS},split=2[a][b];"
          f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=28:2,eq=brightness=-0.18:saturation=1.1[bg];"
          f"[b]scale={fw}:{fh},crop={W}:{fh},eq=contrast=1.05:saturation=1.12[fg];"
          f"[bg][fg]overlay=0:{VID_Y}[v0];")
    for k, (p, a, b) in enumerate(ovs):
        fl += f"[v{k}][{k + 1}:v]overlay=0:0:enable='between(t,{a:.3f},{b:.3f})'[v{k + 1}];"
    fl += f"[v{len(ovs)}]format=yuv420p[vout];[0:a]loudnorm=I=-14:TP=-1.5:LRA=11,afade=t=out:st={dur - 0.4:.2f}:d=0.4[aout]"
    run(["ffmpeg", "-y", *inputs, "-filter_complex", fl, "-map", "[vout]", "-map", "[aout]",
         "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-profile:v", "high", "-r", str(FPS),
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", job["out"]])
    print(f"CLIP_OK {job['out']} {dur:.1f}s words={len(words)}")


if __name__ == "__main__":
    main()
