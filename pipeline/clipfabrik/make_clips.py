"""Clipfabrik v1: 16:9 campaign footage -> 9:16 clips. Original audio only (no music, no AI voice).
Usage: python3 make_clips.py SRC.mp4 words.json outdir
Layout 1080x1920: blurred fill background, sharp 1080x1200 centre crop, title + free-trial pill on top,
word-accurate karaoke captions (libass) inside the picture."""
import json, os, re, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ANTON = os.path.join(HERE, "fonts", "Anton-Regular.ttf")
INTER = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
W, H, FG_Y, FG_H = 1080, 1920, 400, 1200
PILL = "DMZ gets free access for a limited time"
FIX = {"X01.": "XO1.", "X01": "XO1", "granite": "Granit", "-armed": "Armament"}
CLIPS = [
    {"id": "A_blacksite", "a": 1.55, "b": 21.60, "title": "MW4 DMZ: BLACKSITE XO1"},
    {"id": "B_rogue", "a": 23.65, "b": 35.90, "title": "ROGUE OPERATORS INSIDE XO1"},
    {"id": "C_vault", "a": 45.45, "b": 63.90, "title": "DMZ OBJECTIVE: THE VAULT"},
]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: sys.exit("FAIL " + " ".join(cmd)[:200] + "\n" + r.stderr[-1500:])


def overlay(title, path):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    fs = 118
    while fs > 60 and d.textlength(title, font=ImageFont.truetype(ANTON, fs)) > W - 110: fs -= 2
    f = ImageFont.truetype(ANTON, fs); tw = d.textlength(title, font=f)
    head, _, tail = title.partition(":")  # part before ':' yellow
    x, y = (W - tw) / 2, 262 - fs
    if tail:
        d.text((x, y), head + ":", font=f, fill=(255, 230, 0, 255), stroke_width=7, stroke_fill=(0, 0, 0, 255))
        x += d.textlength(head + ":", font=f)
        d.text((x, y), tail, font=f, fill=(255, 255, 255, 255), stroke_width=7, stroke_fill=(0, 0, 0, 255))
    else:
        d.text((x, y), title, font=f, fill=(255, 255, 255, 255), stroke_width=7, stroke_fill=(0, 0, 0, 255))
    pf = ImageFont.truetype(INTER, 40); pw = d.textlength(PILL, font=pf)
    px = (W - pw) / 2 - 28
    d.rounded_rectangle([px, 306, px + pw + 56, 376], radius=16, fill=(255, 230, 0, 255))
    d.text((px + 28, 316), PILL, font=pf, fill=(0, 0, 0, 255))
    img.save(path)


def ts(t):
    t = max(t, 0); return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def ass(words, a, b, path):
    ws = [dict(w, w=FIX.get(w["w"], w["w"])) for w in words if w["s"] >= a - 0.05 and w["e"] <= b + 0.3]
    groups, cur = [], []
    for i, w in enumerate(ws):
        cur.append(w)
        gap = ws[i + 1]["s"] - w["e"] > 0.45 if i + 1 < len(ws) else True
        if len(cur) >= 3 or re.search(r"[,.?!]$", w["w"]) or gap: groups.append(cur); cur = []
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 2\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: C,Anton,150,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,0,0,0,0,100,100,1,0,1,9,3,2,40,40,450,1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    ev = []
    for gi, g in enumerate(groups):
        gend = g[-1]["e"] + 0.4
        if gi + 1 < len(groups): gend = min(gend, groups[gi + 1][0]["s"])
        gend = min(gend, b)
        for k, w in enumerate(g):
            s = max(w["s"], g[k - 1]["s"] + 0.08) if k else w["s"]
            e = g[k + 1]["s"] if k + 1 < len(g) else gend
            e = max(e, s + 0.08)
            txt = " ".join(("{\\c&H00E6FF&}" if j == k else "{\\c&HFFFFFF&}") + re.sub(r"[.,]$", "", x["w"]).upper()
                           for j, x in enumerate(g))
            ev.append(f"Dialogue: 0,{ts(s - a)},{ts(e - a)},C,,0,0,0,,{txt}")
    open(path, "w").write(head + "\n".join(ev) + "\n")
    return len(groups)


def main():
    src, words, out = sys.argv[1], json.load(open(sys.argv[2])), sys.argv[3]
    os.makedirs(out, exist_ok=True); tmp = os.path.join(out, "_tmp"); os.makedirs(tmp, exist_ok=True)
    only = sys.argv[4].split(",") if len(sys.argv) > 4 else None
    for c in CLIPS:
        if only and c["id"] not in only: continue
        dur = c["b"] - c["a"]; ov = os.path.join(tmp, c["id"] + ".png"); sub = os.path.join(tmp, c["id"] + ".ass")
        overlay(c["title"], ov); n = ass(words, c["a"], c["b"], sub)
        dst = os.path.join(out, f"mw4dmz_{c['id']}.mp4")
        fl = (f"[0:v]split=2[b0][f0];"
              f"[b0]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=6:2,scale={W}:{H},eq=brightness=-0.22:saturation=1.1[bg];"
              f"[f0]crop=ih*{W}/{FG_H}:ih,scale={W}:{FG_H}:flags=lanczos[fg];"
              f"[bg][fg]overlay=0:{FG_Y}[v1];[v1][1:v]overlay=0:0[v2];"
              f"[v2]subtitles={sub}:fontsdir={os.path.join(HERE, 'fonts')},fps=60,format=yuv420p[v];"
              f"[0:a]afade=t=in:d=0.12,afade=t=out:st={dur - 0.35:.2f}:d=0.35[a]")
        run(["ffmpeg", "-y", "-ss", f"{c['a']:.3f}", "-t", f"{dur:.3f}", "-i", src, "-i", ov, "-filter_complex", fl,
             "-map", "[v]", "-map", "[a]", "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
             "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", dst])
        print("OK", dst, f"{dur:.1f}s", "caption groups", n)


if __name__ == "__main__":
    main()
