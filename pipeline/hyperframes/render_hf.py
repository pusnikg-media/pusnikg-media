"""Pusnik G renderer v3 (HyperFrames, 0 credits): stock clips + am_puck voice + music + word-exact karaoke captions.
Usage: python3 render_hf.py job.json
job.json:
  vo_dir      folder from tts.py (timing.json + line_XX.wav); line 1 = hook, last line = CTA
  shots       per script line a list of {"file": "local.mp4", "start": s}; each shot <= ~2.3 s; file stems unique
  day         countdown number (badge "GTA 6 • DAY X", giant hook number)
  hook_big    giant hook text in frame 0 (default: day)      hook_mid  yellow line under it (default "DAYS LEFT")
  hook_sub    small white line, appears on the 3rd spoken word of line 1 (optional)
  badge       override badge text (optional)
  card        optional slam card on a keyword: {"line": i, "word": "november", "top": "NOV", "big": "19", "bottom": "2026"}
  music       music file (looped)   music_start  skip slow intro (s)   music_db  gain before ducking (default -9)
  out         output mp4
Output: 1080x1920, 30 fps, h264 + aac 48 kHz, loudnorm -14 LUFS. Needs: Node 22, google-chrome, ffmpeg,
pip faster-whisper (word timestamps, model base.en from Hugging Face)."""
import json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
HF = "hyperframes@0.9.13"
GAP, TAIL = 0.22, 0.6


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode:
        sys.exit("FAIL: " + " ".join(cmd)[:300] + "\n" + (r.stdout + r.stderr)[-2000:])
    return r.stdout


def main():
    jp = os.path.abspath(sys.argv[1]); job = json.load(open(jp)); base = os.path.dirname(jp)
    job["vo_dir"] = os.path.join(base, job["vo_dir"]) if not os.path.isabs(job["vo_dir"]) else job["vo_dir"]
    proj = os.path.join(base, "hf_proj"); os.makedirs(os.path.join(proj, "assets", "v"), exist_ok=True)
    os.makedirs(os.path.join(proj, "assets", "fonts"), exist_ok=True)
    shutil.copy(os.path.join(HERE, "gsap.min.js"), os.path.join(proj, "assets", "gsap.min.js"))
    shutil.copy(os.path.join(HERE, "..", "fonts", "Anton-Regular.ttf"), os.path.join(proj, "assets", "fonts", "Anton-Regular.ttf"))
    open(os.path.join(proj, "meta.json"), "w").write(json.dumps({"id": "pusnikg", "name": "pusnikg"}))
    # 1) exact word timings (Whisper, calibrated to the real speech span)
    if not os.path.exists(os.path.join(job["vo_dir"], "words.json")):
        print(run(["python3", os.path.join(HERE, "words.py"), job["vo_dir"]])[-1500:])
    # 2) clips -> vertical 1080x1920 30 fps, light grade (saturation/contrast)
    done = set()
    for line in job["shots"]:
        for c in line:
            src = c["file"] if os.path.isabs(c["file"]) else os.path.join(base, c["file"])
            stem = os.path.splitext(os.path.basename(src))[0]
            if stem in done: continue
            done.add(stem)
            run(["ffmpeg", "-v", "error", "-y", "-i", src, "-an", "-vf",
                 "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,eq=saturation=1.2:contrast=1.06",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-g", "15",
                 os.path.join(proj, "assets", "v", stem + ".mp4")])
    # 3) composition
    print(run(["python3", os.path.join(HERE, "build_cd.py"), jp, proj]).strip())
    chk = subprocess.run(["npx", "--yes", HF, "check", "--json"], cwd=proj, capture_output=True, text=True)
    if '"ok": false' in chk.stdout or '"ok":false' in chk.stdout:
        print("CHECK WARN:", chk.stdout[-1500:])
    silent = os.path.join(base, "video_silent.mp4")
    run(["npx", "--yes", HF, "render", "-q", "delivery", "-w", "4", "-o", silent], cwd=proj, timeout=1500)
    # 4) audio: voice (EQ + compressor) + looped music ducked under the voice, -14 LUFS
    tm = json.load(open(os.path.join(job["vo_dir"], "timing.json")))
    total = sum(l["dur"] for l in tm) + GAP * (len(tm) - 1) + TAIL
    inp, fl = [], ""
    for i, l in enumerate(tm):
        inp += ["-i", l["file"]]; pad = GAP if i < len(tm) - 1 else TAIL
        fl += f"[{i}:a]aresample=48000,apad=pad_dur={pad}[a{i}];"
    n = len(tm)
    fl += ("".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1,highpass=f=80,"
           "equalizer=f=3200:t=q:w=1.2:g=3,acompressor=threshold=-20dB:ratio=3:attack=5:release=80,asplit[vo][sc];")
    music = job.get("music")
    if music:
        music = music if os.path.isabs(music) else os.path.join(base, music)
        inp += ["-stream_loop", "-1", "-ss", str(job.get("music_start", 0)), "-i", music]
        fl += (f"[{n}:a]aresample=48000,atrim=0:{total:.3f},asetpts=PTS-STARTPTS,volume={job.get('music_db', -9)}dB,"
               f"afade=t=out:st={total - 1.3:.2f}:d=1.3[mus];[mus][sc]sidechaincompress=threshold=0.03:ratio=6:attack=15:release=250[duck];"
               "[vo][duck]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[out]")
    else:
        fl += "[sc]anullsink;[vo]loudnorm=I=-14:TP=-1.5:LRA=11[out]"
    mix = os.path.join(base, "mix.wav")
    run(["ffmpeg", "-v", "error", "-y", *inp, "-filter_complex", fl, "-map", "[out]", "-ar", "48000", "-ac", "2", mix])
    out = job["out"] if os.path.isabs(job["out"]) else os.path.join(base, job["out"])
    run(["ffmpeg", "-v", "error", "-y", "-i", silent, "-i", mix, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
         "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", out])
    print(f"RENDER_OK {out} {total:.2f}s")


if __name__ == "__main__":
    main()
