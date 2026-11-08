"""Render one Pusnik G short from a JSON job spec (runs in GitHub Actions, see .github/workflows/render.yml).
Usage: python3 pipeline/gh_render.py spec.json workdir
spec.json (written by the scheduled producer, sent as a GitHub issue body inside a ```json block):
  date      "2026-11-11"            day   8 (countdown number; 0 after release)
  script    ["line 1", ...]         5-6 English sentences, last one = CTA
  shots     [[{"url": "https://...mp4", "start": 0}, ...], ...]   one non-empty list per script line
  music     {"url": "https://...mp3", "start": 4.0, "db": -9}   or null (then pipeline/music.py)
  optional: hook_big, hook_mid, hook_sub, badge, card, punch, voice (am_puck), speed (1.0), name
Writes workdir/<name>.mp4 + QA PNGs + result.json {"ok", "video", "pngs", "renderer", "seconds", "log"}.
Long shots are split automatically into cuts of <= 2.3 s from the same clip (as render_clips.py does)."""
import hashlib, json, math, os, re, subprocess, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
GAP, TAIL, MAX_SHOT = 0.22, 0.6, 2.3
LOG = []


def log(msg):
    print(msg, flush=True); LOG.append(str(msg)[-600:])


def finish(ok, **kw):
    res = {"ok": ok, "log": LOG[-25:], **kw}
    json.dump(res, open(os.path.join(WORK, "result.json"), "w"), indent=1, ensure_ascii=False)
    print("GH_RENDER_OK" if ok else "GH_RENDER_FAIL", flush=True)
    sys.exit(0 if ok else 1)


def sh(cmd, timeout=1800):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    out = (r.stdout + r.stderr).strip()
    return r.returncode, out


def fetch(url, dest, limit=300 * 1024 * 1024):
    if not re.match(r"^https://", url or ""):
        raise ValueError(f"only https URLs allowed: {url!r}")
    req = urllib.request.Request(url, headers={"User-Agent": "pusnikg-render/1.0"})
    n = 0
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b: break
            n += len(b)
            if n > limit: raise ValueError(f"file too large: {url}")
            f.write(b)
    if n < 10_000: raise ValueError(f"file too small ({n} bytes): {url}")


def duration(f):
    rc, out = sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f], 60)
    try: return float(out.splitlines()[-1])
    except (ValueError, IndexError): return 0.0


def main():
    spec = json.load(open(sys.argv[1]))
    for k in ("script", "shots"):
        if not spec.get(k): finish(False, error=f"spec field '{k}' missing or empty")
    script = [s.strip() for s in spec["script"] if s.strip()]
    if len(spec["shots"]) != len(script) or not all(spec["shots"]):
        finish(False, error=f"shots has {len(spec['shots'])} lists for {len(script)} script lines (need one non-empty list per line)")
    name = re.sub(r"[^a-z0-9-]", "", spec.get("name") or f"pusnikg-{spec.get('date', 'x')}-day{spec.get('day', '')}") or "pusnikg-short"
    # 1) assets (one file per distinct URL; a broken clip is dropped if its line still has another one)
    os.makedirs(os.path.join(WORK, "clips"), exist_ok=True)
    files, shots = {}, []
    for i, line in enumerate(spec["shots"]):
        keep = []
        for c in line:
            u = c.get("url", "")
            if u not in files:
                p = os.path.join(WORK, "clips", "c" + hashlib.sha1(u.encode()).hexdigest()[:10] + ".mp4")
                try:
                    fetch(u, p); d = duration(p)
                    if d < 0.8: raise ValueError(f"clip unreadable or shorter than 0.8 s ({d:.2f}s)")
                    files[u] = (p, d)
                except Exception as e:
                    files[u] = None; log(f"WARN clip dropped (line {i}): {u[:120]} - {e}")
            if files[u]: keep.append({"file": files[u][0], "dur": files[u][1], "start": float(c.get("start", 0) or 0)})
        if not keep: finish(False, error=f"script line {i} has no downloadable clip")
        shots.append(keep)
    music = spec.get("music") or {}
    mpath = None
    if music.get("url"):
        mpath = os.path.join(WORK, "music" + (os.path.splitext(music["url"].split("?")[0])[1][:5] or ".mp3"))
        try:
            fetch(music["url"], mpath)
            if duration(mpath) < 5: raise ValueError("music shorter than 5 s")
        except Exception as e:
            log(f"WARN music failed ({e}) - using pipeline/music.py"); mpath = None
    # 2) voice
    open(os.path.join(WORK, "script.txt"), "w").write("\n".join(script) + "\n")
    rc, out = sh(["python3", os.path.join(HERE, "tts.py"), os.path.join(WORK, "script.txt"), os.path.join(WORK, "vo"),
                  spec.get("voice", "am_puck"), str(max(1.0, float(spec.get("speed", 1.0))))], 900)
    log(out[-800:])
    if rc: finish(False, error="TTS failed", detail=out[-1500:])
    timing = json.load(open(os.path.join(WORK, "vo", "timing.json")))
    total = sum(t["dur"] for t in timing) + GAP * (len(timing) - 1) + TAIL
    if not mpath:
        mpath = os.path.join(WORK, "music.wav")
        rc, out = sh(["python3", os.path.join(HERE, "music.py"), str(int(total) + 2), mpath, str(spec.get("day", 1))], 600)
        if rc: log("WARN music.py failed - rendering without music: " + out[-300:]); mpath = None
        else: log("Notlösung-Musik (music.py)")
    # 3) split long shots into <= 2.3 s cuts of the same clip (clip-length aware)
    jshots = []
    for i, line in enumerate(shots):
        win = timing[i]["dur"] + (GAP if i < len(timing) - 1 else TAIL)
        d = win / len(line); out_line = []
        for c in line:
            k = max(1, math.ceil(d / MAX_SHOT)); sd = d / k
            for j in range(k):
                s = c["start"] + j * sd
                room = c["dur"] - sd - 0.15
                if room <= 0: s = 0.0
                elif s > room: s = (s % room) if room > 0.3 else 0.0
                out_line.append({"file": c["file"], "start": round(s, 3)})
        jshots.append(out_line)
    job = {"vo_dir": "vo", "shots": jshots, "day": spec.get("day", ""), "out": name + ".mp4",
           "music": mpath, "music_start": float(music.get("start", 0) or 0) if music.get("url") and mpath and not mpath.endswith("music.wav") else 0,
           "music_db": float(music.get("db", -9) or -9)}
    for k in ("hook_big", "hook_mid", "hook_sub", "badge", "card", "punch"):
        if spec.get(k) not in (None, "", []): job[k] = spec[k]
    if "badge" not in job and spec.get("day") not in (None, "", 0): job["badge"] = f"GTA 6 • DAY {spec['day']}"
    jp = os.path.join(WORK, "job.json"); json.dump(job, open(jp, "w"), indent=1, ensure_ascii=False)
    # 4) render: HyperFrames v3, fallback clip renderer v2
    renderer = "v3 HyperFrames"
    rc, out = sh(["python3", os.path.join(HERE, "hyperframes", "render_hf.py"), jp], 2400)
    log(out[-1500:])
    if rc:
        log("WARN HyperFrames failed - fallback render_clips.py (v2)")
        renderer = "Fallback v2"
        j2 = dict(job); j2["hook"] = spec.get("hook_text") or (spec.get("hook_sub") or str(job.get("hook_big", job["day"])))
        j2["music_db"] = -12
        jp2 = os.path.join(WORK, "job_v2.json"); json.dump(j2, open(jp2, "w"), indent=1, ensure_ascii=False)
        rc, out = sh(["python3", os.path.join(HERE, "render_clips.py"), jp2], 2400)
        log(out[-1000:])
        if rc: finish(False, error="both renderers failed", detail=out[-1500:])
    video = os.path.join(WORK, name + ".mp4")
    rc, out = sh(["python3", os.path.join(HERE, "qa.py"), video], 600)
    log(out[-1200:])
    pngs = [os.path.join(WORK, f"{name}_qa_{t}.png") for t in ("0", "mid", "end")]
    if rc: finish(False, error="QA failed", detail=out[-1500:], video=video, pngs=[p for p in pngs if os.path.exists(p)], renderer=renderer)
    finish(True, video=video, pngs=[p for p in pngs if os.path.exists(p)], renderer=renderer,
           seconds=round(duration(video), 2), music="music.py" if (mpath or "").endswith("music.wav") else (music.get("url") or "none"))


if __name__ == "__main__":
    if len(sys.argv) < 3: sys.exit(__doc__)
    WORK = os.path.abspath(sys.argv[2]); os.makedirs(WORK, exist_ok=True)
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        log(f"EXCEPTION {type(e).__name__}: {e}")
        finish(False, error=f"{type(e).__name__}: {e}")
