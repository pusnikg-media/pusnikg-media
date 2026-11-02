"""Render a 1080x1920 Pusnik G short: synthwave motion background, hook in frame 0,
word-synced captions, Kokoro voice + ducked music. Usage: render.py job.json"""
import json, sys, os, subprocess, math, re
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

job = json.load(open(sys.argv[1]))
W, H, FPS = 1080, 1920, 30
F_BLACK = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
F_BOLD = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
GAP, LEAD = 0.22, 0.12
work = os.path.dirname(os.path.abspath(sys.argv[1]))

# ---------- audio timeline ----------
timing = json.load(open(job["timing"]))
t = LEAD; words = []; lines = []
for ln in timing:
    lines.append((t, t + ln["dur"], ln))
    toks = ln["text"].split()
    w8 = [len(re.sub(r"\W", "", w)) + 2.5 for w in toks]
    a, b = t + 0.08, t + ln["dur"] - 0.12
    acc = a
    for w, k in zip(toks, w8):
        d = (b - a) * k / sum(w8); words.append([acc, acc + d, w]); acc += d
    t += ln["dur"] + GAP
DUR = t + 0.35
voice = os.path.join(work, "voice.wav")
parts = []
for i, (s, e, ln) in enumerate(lines):
    parts.append(f"[{i}:a]adelay={int(s*1000)}|{int(s*1000)},aresample=44100[a{i}]")
amix = ";".join(parts) + ";" + "".join(f"[a{i}]" for i in range(len(lines))) + f"amix=inputs={len(lines)}:normalize=0,apad,atrim=0:{DUR:.2f}[v]"
cmd = ["ffmpeg", "-y", "-loglevel", "error"]
for _, _, ln in lines: cmd += ["-i", ln["file"]]
subprocess.run(cmd + ["-filter_complex", amix, "-map", "[v]", "-ac", "1", voice], check=True)

# ---------- caption chunks (max 3 words, break on punctuation) ----------
chunks = []; cur = []
for w in words:
    cur.append(w)
    if len(cur) == 3 or re.search(r"[.,!?;:]$", w[2]):
        chunks.append(cur); cur = []
if cur: chunks.append(cur)
# keep chunk on screen until next chunk starts (no flicker in short gaps)
for i, c in enumerate(chunks):
    nxt = chunks[i + 1][0][0] if i + 1 < len(chunks) else DUR
    c.append(min(nxt, c[-1][1] + 0.5))

# ---------- static background ----------
HOR = 1080
sky = np.zeros((H, W, 3), np.float32)
top, mid, low = np.array([10, 2, 30]), np.array([70, 10, 90]), np.array([255, 70, 140])
for y in range(HOR):
    k = y / HOR
    c = top + (mid - top) * min(1, k / 0.6) if k < 0.6 else mid + (low - mid) * ((k - 0.6) / 0.4) ** 1.6
    sky[y] = c
for y in range(HOR, H):
    k = (y - HOR) / (H - HOR); sky[y] = np.array([25, 4, 40]) * (1 - k) + np.array([6, 0, 14]) * k
bg = Image.fromarray(sky.clip(0, 255).astype(np.uint8))
# sun
R = 300; sun = Image.new("RGBA", (2 * R, 2 * R), (0, 0, 0, 0)); sp = sun.load()
for y in range(2 * R):
    k = y / (2 * R); col = (255, int(230 - 150 * k), int(80 + 60 * k))
    for x in range(2 * R):
        if (x - R) ** 2 + (y - R) ** 2 <= R * R:
            band = y > R * 0.9 and ((y - int(R * 0.9)) % 46) < 8 + (y - R * 0.9) / 16
            if not band: sp[x, y] = col + (255,)
SY = HOR - R - 60; cut = HOR - SY  # rows of the sun above the horizon
sun = sun.crop((0, 0, 2 * R, cut))
gc = Image.new("RGBA", (2 * R + 240, cut + 240), (0, 0, 0, 0)); gc.paste(sun, (120, 120), sun)
glow = gc.filter(ImageFilter.GaussianBlur(45)).crop((0, 0, 2 * R + 240, cut + 120))
bg.paste(glow, (W // 2 - R - 120, SY - 120), glow); bg.paste(sun, (W // 2 - R, SY), sun)
# stars
d = ImageDraw.Draw(bg); rng = np.random.default_rng(3)
for _ in range(120):
    x, y = rng.integers(0, W), rng.integers(0, 650); r = rng.choice([1, 1, 2])
    d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 180))
# palms (silhouettes)
def palm(d, x0, s, flip):
    pts = [(x0 + (-1 if flip else 1) * int(s * 0.12 * (1 - (i / 20)) ** 2 * 3), HOR + 60 - int(s * i / 20)) for i in range(21)]
    for i in range(20): d.line([pts[i], pts[i + 1]], fill=(8, 0, 18), width=int(26 - i * 0.6))
    cx, cy = pts[-1]
    for ang in range(0, 360, 40):
        a = math.radians(ang); L = s * 0.45
        tip = (cx + L * math.cos(a), cy + L * 0.45 * math.sin(a) + L * 0.25)
        midp = (cx + L * 0.5 * math.cos(a), cy + L * 0.3 * math.sin(a) - 20)
        d.polygon([(cx, cy), midp, tip, (midp[0], midp[1] + 26)], fill=(8, 0, 18))
palm(d, 90, 520, False); palm(d, W - 70, 430, True)
d.rectangle([0, HOR, W, HOR + 4], fill=(255, 110, 200))
bg = bg.convert("RGB")

def grid(img, ph):
    d = ImageDraw.Draw(img)
    for i in range(-14, 15):
        x_far = W / 2 + i * 40; x_near = W / 2 + i * 420
        d.line([(x_far, HOR), (x_near, H)], fill=(0, 220, 255), width=3)
    for j in range(16):
        z = (j + ph) / 16; y = HOR + (H - HOR) * z ** 2.2
        d.line([(0, y), (W, y)], fill=(255, 60, 200), width=max(2, int(5 * z)))

# ---------- text helpers ----------
def font(p, s): return ImageFont.truetype(p, s)
def wrap(text, f, maxw, d):
    out, cur = [], ""
    for w in text.split():
        tst = (cur + " " + w).strip()
        if d.textlength(tst, font=f) <= maxw: cur = tst
        else: out.append(cur); cur = w
    out.append(cur); return out
def draw_center(img, lines_, f, y, fill, stroke=10, glowc=None, lh=1.08):
    d = ImageDraw.Draw(img)
    for i, l in enumerate(lines_):
        tw = d.textlength(l, font=f); x = (W - tw) / 2; yy = y + i * f.size * lh
        if glowc:
            g = Image.new("RGBA", img.size, (0, 0, 0, 0)); ImageDraw.Draw(g).text((x, yy), l, font=f, fill=glowc)
            g = g.filter(ImageFilter.GaussianBlur(18)); img.paste(g, (0, 0), g)
        d.text((x, yy), l, font=f, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0))

f_hook = font(F_BLACK, 124); f_cap = font(F_BLACK, 104); f_lab = font(F_BOLD, 40); f_big = font(F_BLACK, 210); f_small = font(F_BOLD, 54)
tmp = ImageDraw.Draw(bg)
hook_lines = wrap(job["hook"].upper(), f_hook, W - 140, tmp)
hook_end = lines[0][1] + 0.1

def pill(img, text, y, fg=(255, 255, 255), bgc=(0, 0, 0, 170)):
    o = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(o)
    tw = d.textlength(text, font=f_lab); x = (W - tw) / 2
    d.rounded_rectangle([x - 34, y - 16, x + tw + 34, y + 60], 38, fill=bgc, outline=(0, 230, 255), width=3)
    d.text((x, y - 4), text, font=f_lab, fill=fg); img.paste(o, (0, 0), o)

# ---------- render ----------
out = job["out"]
ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                       "-i", voice, "-i", job["music"],
                       "-filter_complex", "[2:a]volume=0.30,atrim=0:%.2f[m];[1:a]aresample=44100,asplit=2[vo][sc];[m][sc]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=350[md];[vo][md]amix=inputs=2:normalize=0,highpass=f=60,acompressor=threshold=-18dB:ratio=2.5,loudnorm=I=-14:TP=-1.5:LRA=9[a]" % DUR,
                       "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-profile:v", "high",
                       "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-movflags", "+faststart", "-t", f"{DUR:.2f}", out], stdin=subprocess.PIPE)
nf = int(DUR * FPS)
beat = 0.6
for fi in range(nf):
    tt = fi / FPS
    img = bg.copy(); grid(img, (tt * 1.6) % 1)
    pulse = 1 + 0.012 * max(0, 1 - ((tt % beat) / 0.18))
    if pulse > 1.0005:
        z = img.resize((int(W * pulse), int(H * pulse))); ox = (z.width - W) // 2; oy = (z.height - H) // 2
        img = z.crop((ox, oy, ox + W, oy + H))
    pill(img, job["day_label"], 150)
    if tt < hook_end:
        pop = min(1, 0.85 + tt * 1.5) if tt > 0 else 1
        fh = f_hook if pop >= 1 else font(F_BLACK, int(124 * pop))
        hl = hook_lines if pop >= 1 else wrap(job["hook"].upper(), fh, W - 140, tmp)
        draw_center(img, hl, fh, 330, (255, 255, 255), 12, (255, 40, 180, 255))
    else:
        draw_center(img, [job["big"]], f_big, 300, (255, 235, 90), 12, (255, 60, 160, 255))
        draw_center(img, [job["big_sub"]], f_small, 540, (255, 255, 255), 8)
    for c in chunks:
        ws, end = c[:-1], c[-1]
        if ws[0][0] <= tt < end:
            d = ImageDraw.Draw(img); txt = [w[2].upper() for w in ws]
            line = " ".join(txt); tw = d.textlength(line, font=f_cap)
            fc = f_cap if tw <= W - 120 else font(F_BLACK, int(104 * (W - 120) / tw))
            x = (W - d.textlength(line, font=fc)) / 2; y = 1330
            for w, s in zip(ws, txt):
                col = (255, 230, 60) if w[0] <= tt < w[1] + 0.05 else (255, 255, 255)
                d.text((x, y), s, font=fc, fill=col, stroke_width=11, stroke_fill=(0, 0, 0))
                x += d.textlength(s + " ", font=fc)
            break
    if tt >= lines[-1][0]:
        pill(img, job["cta"], 1560, fg=(255, 235, 90))
    ff.stdin.write(img.tobytes())
ff.stdin.close(); ff.wait()
print(f"done {out} {DUR:.2f}s, {nf} frames")
