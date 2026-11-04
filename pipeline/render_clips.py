"""Pusnik G clip renderer v2 (0 credits): stock clips + am_puck voice + music + karaoke subtitles.
Usage: python3 render_clips.py job.json
job.json fields:
  vo_dir      folder from tts.py (timing.json + line_XX.wav)
  shots       list per script line: list of clip specs {"file": "...mp4", "start": 0.0}
              (a shot longer than max_shot is auto-split into several cuts of the same clip)
  music       music file (any ffmpeg format, looped) or null
  music_start seconds to skip at the start of the track (skip slow intros, default 0)
  music_db    music gain in dB before ducking (default -12; ducked further under the voice)
  badge       e.g. "GTA 6 • DAY 12"
  hook        big hook text shown in frame 0 during line 1 (max ~6 words)
  out         output mp4
  gap         pause between lines in s (default 0.22)
  tail        extra seconds after last line (default 0.6)
  max_shot    longest single cut in s (default 2.3)
v2 (04.11.): Anton font in repo, word-by-word karaoke highlight, white flash on every cut,
pink progress bar, auto cuts every <=2.3 s with alternating zoom/pan, voice EQ+compression,
music sidechain-ducked under the voice (louder between lines).
Output: 1080x1920, 30 fps, h264 + aac, loudnorm -14 LUFS."""
import json, os, re, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 1080, 1920, 30
ANTON = os.path.join(HERE, "fonts", "Anton-Regular.ttf")
INTER = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
PINK = (255, 46, 136)
YELLOW = (255, 230, 0)


def font(p, s):
    try:
        return ImageFont.truetype(p, s)
    except OSError:
        return ImageFont.truetype(INTER, s)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit("FFMPEG FAIL: " + " ".join(cmd)[:300] + "\n" + r.stderr[-1500:])


def wrap(d, text, f, maxw):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    return lines + ([cur] if cur else [])


def text_block(img, text, f, cy, maxw, glow=True, stroke=8):
    d = ImageDraw.Draw(img)
    lines = wrap(d, text, f, maxw)
    lh = f.size * 1.08
    y0 = cy - lh * len(lines) / 2
    if glow:
        g = Image.new("RGBA", img.size, (0, 0, 0, 0)); gd = ImageDraw.Draw(g)
        for i, l in enumerate(lines):
            x = (W - gd.textlength(l, font=f)) / 2
            gd.text((x, y0 + i * lh), l, font=f, fill=PINK + (255,), stroke_width=14, stroke_fill=PINK + (255,))
        gb = g.filter(ImageFilter.GaussianBlur(22))
        img.alpha_composite(gb); img.alpha_composite(gb)  # double pass = stronger pink glow
    for i, l in enumerate(lines):
        x = (W - d.textlength(l, font=f)) / 2
        d.text((x, y0 + i * lh), l, font=f, fill=(255, 255, 255, 255), stroke_width=stroke, stroke_fill=(0, 0, 0, 255))


def karaoke(words, hi, f, cy, maxw, stroke=9):
    """One subtitle phrase, word `hi` highlighted yellow; others white. Same layout for every hi."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    sp = d.textlength(" ", font=f); lines, cur, cw = [], [], 0
    for i, w in enumerate(words):
        tw = d.textlength(w, font=f)
        if cur and cw + sp + tw > maxw:
            lines.append((cur, cw)); cur, cw = [], 0
        cw = cw + (sp if cur else 0) + tw; cur.append(i)
    if cur: lines.append((cur, cw))
    lh = f.size * 1.1; y = cy - lh * len(lines) / 2
    for idx, lw in lines:
        x = (W - lw) / 2
        for i in idx:
            col = YELLOW if i == hi else (255, 255, 255)
            d.text((x, y), words[i], font=f, fill=col + (255,), stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
            x += d.textlength(words[i], font=f) + sp
        y += lh
    return img


def base_overlay(badge):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    grad = Image.new("L", (1, H))
    for y in range(H):  # dark top + strong dark bottom
        a = 0.55 * max(0, 1 - y / 420) + 0.75 * max(0, (y - H * 0.45) / (H * 0.55))
        grad.putpixel((0, y), int(255 * min(a, 0.85)))
    img.alpha_composite(Image.merge("RGBA", [Image.new("L", (W, H), 0)] * 3 + [grad.resize((W, H))]))
    d = ImageDraw.Draw(img); f = font(ANTON, 66)
    tw = d.textlength(badge, font=f); px, py = 34, 16; x = (W - tw) / 2 - px; y = 150
    d.rounded_rectangle([x, y, x + tw + 2 * px, y + f.size + 2 * py + 8], radius=18, fill=PINK + (255,))
    d.text((x + px, y + py - 2), badge, font=f, fill=(255, 255, 255, 255))
    return img


def phrases(text, maxw=3):
    words = text.split(); out, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= maxw or re.search(r"[,.?!]$", w):
            out.append(" ".join(cur)); cur = []
    if cur:
        if out and len(cur) == 1: out[-1] += " " + cur[0]
        else: out.append(" ".join(cur))
    # never end a phrase on a weak word ("RIGHT BEATS A") - push it to the next phrase
    weak = {"a", "an", "the", "and", "or", "to", "on", "of", "for", "in", "is", "it's", "so", "are", "your", "my"}
    for i in range(len(out) - 1):
        ws = out[i].split()
        while len(ws) > 1 and ws[-1].lower() in weak:
            out[i + 1] = ws.pop() + " " + out[i + 1]
        out[i] = " ".join(ws)
    return out


def main():
    job = json.load(open(sys.argv[1]))
    tmp = tempfile.mkdtemp(prefix="rc_")
    timing = json.load(open(os.path.join(job["vo_dir"], "timing.json")))
    gap, tail, max_shot = job.get("gap", 0.22), job.get("tail", 0.6), job.get("max_shot", 2.3)
    t, wins = 0.0, []
    for i, ln in enumerate(timing):
        wins.append((t, t + ln["dur"])); t += ln["dur"] + (gap if i < len(timing) - 1 else 0)
    total = t + tail
    # --- voice track (EQ + light compression for clarity)
    vo = os.path.join(tmp, "vo.wav"); inputs, fl = [], ""
    for i, ln in enumerate(timing):
        inputs += ["-i", ln["file"]]
        pad = gap if i < len(timing) - 1 else tail
        fl += f"[{i}:a]aresample=48000,apad=pad_dur={pad}[a{i}];"
    fl += "".join(f"[a{i}]" for i in range(len(timing))) + f"concat=n={len(timing)}:v=0:a=1,"
    fl += "highpass=f=80,equalizer=f=3000:t=q:w=1.2:g=3,acompressor=threshold=-20dB:ratio=3:attack=5:release=80[v]"
    run(["ffmpeg", "-y", *inputs, "-filter_complex", fl, "-map", "[v]", "-ac", "2", vo])
    # --- video segments: shots share their line's window; long shots auto-split into <=max_shot cuts
    segs = []
    for i, shots in enumerate(job["shots"]):
        a = wins[i][0]; b = wins[i + 1][0] if i + 1 < len(wins) else total
        dur = (b - a) / len(shots)
        for s in shots:
            k = max(1, -(-dur // max_shot)); d = dur / k
            for j in range(int(k)):
                segs.append(({"file": s["file"], "start": s.get("start", 0) + j * d}, d))
    seg_files, cuts, tt = [], [], 0.0
    for idx, (s, dur) in enumerate(segs):
        out = os.path.join(tmp, f"s{idx:02d}.mp4"); zin = idx % 2 == 0
        zexpr = f"1+0.08*t/{dur:.3f}" if zin else f"1.08-0.08*t/{dur:.3f}"
        px = ["(iw-ow)/2", "(iw-ow)*t/" + f"{dur:.3f}", "(iw-ow)*(1-t/" + f"{dur:.3f})"][idx % 3]
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
              f"scale=w='trunc({W}*({zexpr})/2)*2':h=-2:eval=frame,crop={W}:{H}:x='{px}':y='(ih-oh)/2',"
              f"eq=saturation=1.2:contrast=1.07,fps={FPS},setsar=1")
        run(["ffmpeg", "-y", "-ss", f"{s['start']:.3f}", "-i", s["file"], "-t", f"{dur:.3f}", "-an",
             "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", out])
        seg_files.append(out)
        if idx: cuts.append(tt)
        tt += dur
    lst = os.path.join(tmp, "list.txt"); open(lst, "w").write("".join(f"file '{f}'\n" for f in seg_files))
    bg = os.path.join(tmp, "bg.mp4")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", bg])
    # --- overlays
    ovs = []
    p = os.path.join(tmp, "base.png"); base_overlay(job["badge"]).save(p); ovs.append((p, 0, total))
    hook = Image.new("RGBA", (W, H), (0, 0, 0, 0)); text_block(hook, job["hook"].upper(), font(ANTON, 170), H * 0.42, W - 120)
    p = os.path.join(tmp, "hook.png"); hook.save(p); ovs.append((p, 0, wins[0][1] + gap))
    fsub = font(ANTON, 104); n = 0
    for i, ln in enumerate(timing[1:], start=1):
        ph = phrases(ln["text"]); a, b = wins[i]; chars = sum(len(x) for x in ph); t0 = a
        for pi, x in enumerate(ph):
            t1 = t0 + (b - a) * len(x) / chars
            end = t1 if pi < len(ph) - 1 else (wins[i + 1][0] if i + 1 < len(wins) else total)
            words = x.upper().split(); wl = sum(len(w) + 1 for w in words); w0 = t0
            for wi in range(len(words)):
                w1 = w0 + (t1 - t0) * (len(words[wi]) + 1) / wl
                p = os.path.join(tmp, f"sub{n:03d}.png"); n += 1
                karaoke(words, wi, fsub, H * 0.62, W - 140).save(p)
                ovs.append((p, w0, end if wi == len(words) - 1 else w1)); w0 = w1
            t0 = t1
    flash = os.path.join(tmp, "flash.png"); Image.new("RGBA", (W, H), (255, 255, 255, 120)).save(flash)
    bar = os.path.join(tmp, "bar.png"); Image.new("RGBA", (W, 12), PINK + (255,)).save(bar)
    # --- final compose
    inputs = ["-i", bg, "-i", vo]
    music = job.get("music")
    if music:
        inputs += ["-stream_loop", "-1", "-ss", str(job.get("music_start", 0)), "-i", music]
    off = 3 if music else 2
    for p, _, _ in ovs:
        inputs += ["-i", p]
    inputs += ["-loop", "1", "-i", flash, "-loop", "1", "-i", bar]
    fi, bi = off + len(ovs), off + len(ovs) + 1
    fl = "[0:v]null[v0];"
    for k, (p, a, b) in enumerate(ovs):
        fl += f"[v{k}][{off + k}:v]overlay=0:0:enable='between(t,{a:.3f},{b:.3f})'[v{k + 1}];"
    k = len(ovs)
    if cuts:
        en = "+".join(f"between(t,{c:.3f},{c + 0.07:.3f})" for c in cuts)
        fl += f"[v{k}][{fi}:v]overlay=0:0:shortest=1:enable='{en}'[vf];"
    else:
        fl += f"[v{k}]null[vf];"
    fl += f"[vf][{bi}:v]overlay=x='-W+W*t/{total:.3f}':y=H-12:shortest=1[vout];"
    if music:
        g = job.get("music_db", -12)
        fl += (f"[1:a]asplit=2[vo1][vo2];"
               f"[2:a]aresample=48000,volume={g}dB,afade=t=in:d=0.3,afade=t=out:st={total - 1.2:.2f}:d=1.2[m];"
               f"[m][vo2]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=300[md];"
               f"[vo1][md]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]")
    else:
        fl += "[1:a]loudnorm=I=-14:TP=-1.5:LRA=11[a]"
    run(["ffmpeg", "-y", *inputs, "-filter_complex", fl, "-map", "[vout]", "-map", "[a]",
         "-t", f"{total:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
         "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", job["out"]])
    print(f"RENDER_OK {job['out']} {total:.2f}s segments={len(segs)} overlays={len(ovs)}")


if __name__ == "__main__":
    main()
