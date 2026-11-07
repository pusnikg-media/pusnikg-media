"""Pusnik G QA in one command: python3 pipeline/qa.py out.mp4 [min_s max_s]
Checks: h264 1080x1920 video + aac audio, durations match, 18-35 s, integrated loudness -16..-12 LUFS,
no silence > 1 s (-45 dB), no black/frozen frame 0. Writes 3 PNGs next to the video
(<name>_qa_0.png, _qa_mid.png, _qa_end.png at 0 s, middle, end-0.3 s) - look at them.
Prints QA_OK or QA_FAIL + one line per failing check (exit 1)."""
import json, os, re, subprocess, sys


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    f = os.path.abspath(sys.argv[1])
    lo, hi = (float(sys.argv[2]), float(sys.argv[3])) if len(sys.argv) > 3 else (18.0, 35.0)
    F = []
    if not os.path.exists(f) or os.path.getsize(f) < 100_000:
        print(f"QA_FAIL\n- {f} missing or tiny"); sys.exit(1)
    r = sh(["ffprobe", "-v", "error", "-show_entries",
            "stream=codec_type,codec_name,width,height,duration,sample_rate:format=duration", "-of", "json", f])
    if r.returncode:
        print(f"QA_FAIL\n- ffprobe cannot read the file: {r.stderr[-300:]}"); sys.exit(1)
    d = json.loads(r.stdout); st = d.get("streams", [])
    v = next((s for s in st if s.get("codec_type") == "video"), None)
    a = next((s for s in st if s.get("codec_type") == "audio"), None)
    total = float(d.get("format", {}).get("duration") or 0)
    if not v: F.append("no video stream")
    else:
        if v.get("codec_name") != "h264": F.append(f"video codec {v.get('codec_name')} != h264")
        if (v.get("width"), v.get("height")) != (1080, 1920): F.append(f"resolution {v.get('width')}x{v.get('height')} != 1080x1920")
    if not a: F.append("no audio stream")
    elif a.get("codec_name") != "aac": F.append(f"audio codec {a.get('codec_name')} != aac")
    if v and a:
        dv, da = float(v.get("duration") or total), float(a.get("duration") or total)
        if abs(dv - da) > 0.25: F.append(f"video {dv:.2f}s vs audio {da:.2f}s differ")
    if not lo <= total <= hi: F.append(f"duration {total:.2f}s outside {lo:.0f}-{hi:.0f}s")
    if a:
        e = sh(["ffmpeg", "-nostats", "-i", f, "-vn", "-af", "ebur128", "-f", "null", "-"]).stderr
        m = re.findall(r"I:\s+(-?[\d.]+) LUFS", e)
        lufs = float(m[-1]) if m else None
        if lufs is None: F.append("loudness could not be measured")
        elif not -16 <= lufs <= -12: F.append(f"loudness {lufs:.1f} LUFS outside -16..-12")
        s = sh(["ffmpeg", "-nostats", "-i", f, "-vn", "-af", "silencedetect=n=-45dB:d=1", "-f", "null", "-"]).stderr
        for ss, dd in re.findall(r"silence_end: ([\d.]+) \| silence_duration: ([\d.]+)", s):
            F.append(f"silence {float(dd):.2f}s ending at {float(ss):.2f}s")
        if "silence_start" in s and not re.search(r"silence_end", s.split("silence_start")[-1]):
            F.append("silence until the end of the file")
    else:
        lufs = None
    stem = os.path.splitext(f)[0]; pngs = []
    for tag, t in (("0", 0.0), ("mid", total / 2), ("end", max(0.0, total - 0.3))):
        p = f"{stem}_qa_{tag}.png"
        sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", f, "-frames:v", "1", p])
        if not os.path.exists(p) or os.path.getsize(p) < 1000: F.append(f"frame at {t:.2f}s could not be extracted")
        else: pngs.append(p)
    if v:  # frame 0 must not be black (hook must be visible immediately)
        y = sh(["ffmpeg", "-v", "error", "-i", f, "-frames:v", "1", "-vf", "signalstats,metadata=print:key=lavfi.signalstats.YAVG",
                "-f", "null", "-"]).stderr
        m = re.search(r"YAVG=([\d.]+)", y)
        if m and float(m.group(1)) < 20: F.append(f"frame 0 is (nearly) black (YAVG {float(m.group(1)):.0f})")
        fr = sh(["ffmpeg", "-nostats", "-i", f, "-an", "-vf", "freezedetect=n=0.001:d=2.5", "-f", "null", "-"]).stderr
        for fs, fd in re.findall(r"freeze_start: ([\d.]+)[\s\S]*?freeze_duration: ([\d.]+)", fr):
            F.append(f"picture frozen {float(fd):.1f}s from {float(fs):.1f}s (clip too short?)")
    info = f"{total:.2f}s {lufs if lufs is not None else '?'} LUFS frames: {' '.join(pngs)}"
    if F:
        print("QA_FAIL " + info + "\n" + "\n".join("- " + x for x in F)); sys.exit(1)
    print("QA_OK " + info)


if __name__ == "__main__":
    main()
