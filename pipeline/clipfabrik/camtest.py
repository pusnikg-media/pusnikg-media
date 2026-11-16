"""Camtest (15.11.2026, v2 16.11.): does facecam_rect("auto") find the facecam on real gaming streams - and does it fall back cleanly
(None -> native) instead of cutting a game character or a wall poster?
  python3 camtest.py REPO_ROOT   reads plan/camtest.json
    {"channels": ["xqc", ...], "per": 3, "scan": 12, "gta_only": true, "range": "7d", "urls": ["https://clips.twitch.tv/..."]}
Per channel: the most-viewed Twitch clips of the range (yt-dlp); with gta_only only those whose game/title says GTA / RP (up to `per`).
Each clip is run through BOTH pickers (v1 = old median of all faces, v2 = cluster pick with side/motion rules) in the same run, so one
download compares them. Output: clips/camtest/<channel>_<n>.jpg (4 frames, v2 box red, v1 box yellow if different) + clips/camtest/report.json
(per clip: game, cam_frac v1/v2, mode, all face clusters with coverage/motion). No videos are stored."""
import glob, json, os, re, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clipfabrik as cf

GTA = re.compile(r"grand theft|gta|nopixel|no pixel|\brp\b|roleplay|role play", re.I)


def sh(cmd, t=600):
    try: return subprocess.run(cmd, capture_output=True, text=True, timeout=t)
    except Exception as e: return subprocess.CompletedProcess(cmd, 1, "", str(e))


def sheet(src, p, dur, boxes, dst):
    """boxes = [(rect or None, colour)]. 4 frames side by side."""
    from PIL import Image, ImageDraw
    tiles = []
    for f in (0.1, 0.35, 0.6, 0.85):
        tmp = dst + f".{int(f * 100)}.jpg"
        sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{dur * f:.2f}", "-i", src, "-frames:v", "1", "-vf", "scale=480:-2", "-q:v", "5", tmp])
        if not os.path.exists(tmp): continue
        im = Image.open(tmp).convert("RGB"); os.remove(tmp); dr = ImageDraw.Draw(im)
        for cam, col in boxes:
            if cam:
                k = im.width / p["w"]; x, y, w, h = (v * k for v in cam); dr.rectangle([x, y, x + w, y + h], outline=col, width=3)
        tiles.append(im)
    if not tiles: return False
    out = Image.new("RGB", (sum(t.width for t in tiles), max(t.height for t in tiles)))
    x = 0
    for t in tiles: out.paste(t, (x, 0)); x += t.width
    out.save(dst, quality=70); return True


def frac(cam, p): return [round(cam[0] / p["w"], 3), round(cam[1] / p["h"], 3), round(cam[2] / p["w"], 3), round(cam[3] / p["h"], 3)] if cam else None


def run_picker(mode, v, dur, p):
    cf.FACECAM_PICK = mode
    try: cam = cf.facecam_rect(v, 0, dur, p, "auto")
    except Exception as ex: print("ERR", mode, ex); cam = None
    return cam, getattr(cf.facecam_rect, "last", None), list(getattr(cf.facecam_rect, "dbg", []) or [])


def clips_of(ch, cfg):
    r = sh(["yt-dlp", "-J", "--flat-playlist", "--playlist-end", str(int(cfg.get("scan", 12))), f"https://www.twitch.tv/{ch}/clips?range={cfg.get('range', '7d')}"], 300)
    try: ent = [e for e in json.loads(r.stdout).get("entries") or [] if e]
    except Exception: ent = []
    if not ent: return [], (r.stderr.strip().splitlines() or ["no clips"])[-1][-160:]
    out = []
    for e in ent:
        url = e.get("url") or e.get("webpage_url"); title = (e.get("title") or "")[:70]; game = ""
        if cfg.get("gta_only"):
            j = sh(["yt-dlp", "-j", "--skip-download", url], 120)
            try: info = json.loads(j.stdout); game = " / ".join(info.get("categories") or []) or str(info.get("game") or ""); title = (info.get("title") or title)[:70]
            except Exception: pass
            if not GTA.search(game + " " + title): continue
        out.append((url, title, game))
        if len(out) >= int(cfg.get("per", 2)): break
    return out, None


def main(root):
    cfg = json.load(open(os.path.join(root, "plan", "camtest.json"))); out = os.path.join(root, "clips", "camtest"); os.makedirs(out, exist_ok=True)
    rep = []; jobs = []
    for ch in cfg.get("channels", []):
        lst, err = clips_of(ch, cfg)
        if not lst: rep.append({"channel": ch, "error": err or "no GTA clip in range"}); continue
        jobs += [(ch, n, *x) for n, x in enumerate(lst)]
    jobs += [("url", n, u, "", "") for n, u in enumerate(cfg.get("urls", []))]
    for ch, n, url, title, game in jobs:
        with tempfile.TemporaryDirectory() as tmp:
            sh(["yt-dlp", "--no-progress", "-f", "b[height<=720]/b", "-o", os.path.join(tmp, "v.%(ext)s"), url])
            v = glob.glob(os.path.join(tmp, "v.*"))
            if not v: rep.append({"channel": ch, "url": url, "error": "download failed"}); continue
            p = cf.probe(v[0]); dur = min(p["dur"], 40)
            c1, m1, _ = run_picker("v1", v[0], dur, p); c2, m2, cl = run_picker("v2", v[0], dur, p)
            name = f"{ch}_{n}.jpg"; ok = sheet(v[0], p, dur, [(c1, (255, 220, 0)), (c2, (255, 0, 80))], os.path.join(out, name))
            rep.append({"channel": ch, "url": url, "title": title, "game": game, "size": f"{p['w']}x{p['h']}", "seconds": round(p["dur"], 1),
                        "v2": frac(c2, p), "v2_mode": m2, "v1": frac(c1, p), "v1_mode": m1, "clusters": cl,
                        "sheet": f"{cf.RAW}/clips/camtest/{name}" if ok else None})
            print(rep[-1])
    json.dump(rep, open(os.path.join(out, "report.json"), "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__": main(sys.argv[1])
