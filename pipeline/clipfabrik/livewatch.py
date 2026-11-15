"""Livewatch v0 (prototype, 15.11.2026): "almost live" clipping on a free GitHub runner.
Watches the channels in plan/livewatch.json; while one is live it records the stream in 60 s pieces, measures loudness
per second against the last 10 minutes, and when a moment clearly stands out (shouting, laughter, crowd) it cuts,
captions and renders a 9:16 clip a few minutes after it happened -> clips/live-<channel>/ + inbox.json (pushed at once).
Posting is NOT done here (no platform keys on the runner): an agent reads inbox.json, looks at the QA picture,
writes title/caption and posts through vidIQ.

  python3 livewatch.py check REPO_ROOT           prints "run" when enabled and a channel is configured, else "skip"
  python3 livewatch.py watch REPO_ROOT           the watcher (used by .github/workflows/livewatch.yml)
  python3 livewatch.py simulate FILE REPO_ROOT   same detection + rendering on a local file (test without a live stream)

plan/livewatch.json:
  {"enabled": false, "max_minutes": 330, "channels": [
     {"name": "tjr", "url": "https://kick.com/tjr", "min_hype": 9, "per_hour": 3, "max_clips": 8, "height": 720,
      "layout": "full", "track": true, "fix": {"fucking": "f*cking"}}]}
  min_hype = dB above the 10-min baseline (mean of the 4 loudest seconds in a 20 s window); 9 is strict, 6 is generous."""
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
    return u[0] if r.returncode == 0 and u else None


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


def cut(segs, t0, a, b, dst):
    """Seconds [a, b] of the recording (segment i holds [t0 + i*SEG, ...)) -> one mp4."""
    i0, i1 = int((a - t0) // SEG), int((b - t0) // SEG); files = [segs[i] for i in range(i0, i1 + 1) if i in segs]
    if not files: raise cf.Fail("recording for that moment is gone")
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
    sents = cf.sentences(words)
    cands = [c for c in cf.candidates(sents, [], p["dur"], 6, 12, 34) if c["a"] <= pk <= c["b"]] if sents else []
    if cands: c = max(cands, key=lambda x: x["score"]); a, b = c["a"], c["b"]
    else: a, b = max(pk - 16, 0), min(pk + 8, p["dur"])
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
    cf.run(["ffmpeg", "-y", "-v", "error", "-i", raw, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
            os.path.join(out, rawname)]); os.remove(raw)
    return {"id": stamp, "at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "channel": ch["name"],
            "hype": round(hype, 1), "seconds": r["seconds"], "quote": quote, "a": clip["a"], "b": clip["b"], "raw": f"{cf.RAW}/clips/{name}/{rawname}", "said": " ".join(w["w"] for w in words if a <= w["s"] <= b)[:500],
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


def loop(ch, root, rec, alive, push, t_end):
    """Shared by watch and simulate: rec = folder that fills with %05d.ts pieces, alive() = recorder still running."""
    db, segs, done, clips, last = [], {}, 0, [], -999.0; t0 = 0.0
    min_hype = float(ch.get("min_hype", 9)); per_hour = int(ch.get("per_hour", 3)); max_clips = int(ch.get("max_clips", 8))
    while time.time() < t_end:
        files = sorted(glob.glob(os.path.join(rec, "*.ts"))); run = alive()
        ready = files if not run else files[:-1]  # the newest piece is still being written
        for f in ready[done:]:
            i = int(os.path.basename(f)[:5]); segs[i] = f; d = seg_db(f)
            db += d + [-60.0] * max(0, SEG - len(d)) if run or f != files[-1] else d
            done += 1
            hype, peak = find_peak(db)
            recent = [c for c in clips if c > len(db) - 3600]
            print(f"min {done:3d} hype {hype:4.1f} peak {peak}")
            if peak is not None and hype >= min_hype and len(db) - peak >= 12 and peak - last > 90 and len(recent) < per_hour and len(clips) < max_clips:
                stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
                try:
                    entry, name = make_clip(ch, root, segs, t0, peak, hype, stamp); publish(root, name, entry, push)
                    clips.append(peak); last = peak
                except Exception as e:
                    print("WARN clip failed:", str(e)[-300:]); last = peak
            for j in [k for k in segs if k < i - 14]:  # keep 15 minutes on disk
                try: os.remove(segs.pop(j))
                except OSError: pass
        if not run and done >= len(files): break
        time.sleep(1 if not push else 20)
    return len(clips)


def watch(root):
    c = cfg(root); t_end = time.time() + 60 * int(c.get("max_minutes", 330))
    for ch in c.get("channels", []):
        hls = live_url(ch["url"], int(ch.get("height", 720)))
        if not hls: print("offline:", ch["name"]); continue
        print("LIVE:", ch["name"]); rec = os.path.join(os.environ.get("RUNNER_TEMP", "/tmp"), "lw_rec"); os.makedirs(rec, exist_ok=True)
        for f in glob.glob(os.path.join(rec, "*.ts")): os.remove(f)
        pr = subprocess.Popen(["ffmpeg", "-v", "error", "-i", hls, "-c", "copy", "-f", "segment", "-segment_time", str(SEG), "-reset_timestamps", "1",
                               os.path.join(rec, "%05d.ts")])
        try: n = loop(ch, root, rec, lambda: pr.poll() is None, True, t_end)
        finally: pr.terminate()
        print(f"LIVEWATCH_DONE {ch['name']} clips {n}"); return
    print("LIVEWATCH_IDLE")


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
    else: sys.exit(__doc__)
