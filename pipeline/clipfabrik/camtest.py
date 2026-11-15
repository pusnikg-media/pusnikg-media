"""Camtest (15.11.2026): does facecam_rect("auto") find the facecam on real gaming streams?
  python3 camtest.py REPO_ROOT   reads plan/camtest.json {"channels": ["jynxzi", ...], "per": 2}
Per channel: the most-viewed Twitch clips of the week (yt-dlp), detection on each, and a picture sheet with the found box
drawn in (clips/camtest/<channel>_<n>.jpg) + clips/camtest/report.json. No videos are stored."""
import glob, json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clipfabrik as cf


def sh(cmd, t=600):
    try: return subprocess.run(cmd, capture_output=True, text=True, timeout=t)
    except Exception as e: return subprocess.CompletedProcess(cmd, 1, "", str(e))


def sheet(src, p, dur, cam, dst):
    from PIL import Image, ImageDraw
    tiles = []
    for f in (0.15, 0.5, 0.85):
        tmp = dst + f".{int(f * 100)}.jpg"
        sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{dur * f:.2f}", "-i", src, "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "5", tmp])
        if not os.path.exists(tmp): continue
        im = Image.open(tmp).convert("RGB"); os.remove(tmp)
        if cam:
            k = im.width / p["w"]; x, y, w, h = (v * k for v in cam)
            ImageDraw.Draw(im).rectangle([x, y, x + w, y + h], outline=(255, 0, 80), width=4)
        tiles.append(im)
    if not tiles: return False
    out = Image.new("RGB", (sum(t.width for t in tiles), max(t.height for t in tiles)))
    x = 0
    for t in tiles: out.paste(t, (x, 0)); x += t.width
    out.save(dst, quality=70); return True


def main(root):
    cfg = json.load(open(os.path.join(root, "plan", "camtest.json"))); out = os.path.join(root, "clips", "camtest"); os.makedirs(out, exist_ok=True)
    rep = []
    for ch in cfg.get("channels", []):
        r = sh(["yt-dlp", "-J", "--flat-playlist", "--playlist-end", "12", f"https://www.twitch.tv/{ch}/clips?range=7d"], 300)
        try: ent = [e for e in json.loads(r.stdout).get("entries") or [] if e]
        except Exception: ent = []
        if not ent: rep.append({"channel": ch, "error": (r.stderr.strip().splitlines() or ["no clips"])[-1][-160:]}); continue
        for n, e in enumerate(ent[:int(cfg.get("per", 2))]):
            url = e.get("url") or e.get("webpage_url")
            with tempfile.TemporaryDirectory() as tmp:
                sh(["yt-dlp", "--no-progress", "-f", "b[height<=720]/b", "-o", os.path.join(tmp, "v.%(ext)s"), url])
                v = glob.glob(os.path.join(tmp, "v.*"))
                if not v: rep.append({"channel": ch, "url": url, "error": "download failed"}); continue
                p = cf.probe(v[0]); dur = min(p["dur"], 40)
                try: cam = cf.facecam_rect(v[0], 0, dur, p, "auto")
                except Exception as ex: cam = None; print("ERR", ex)
                name = f"{ch}_{n}.jpg"; ok = sheet(v[0], p, dur, cam, os.path.join(out, name))
                rep.append({"channel": ch, "url": url, "title": (e.get("title") or "")[:70], "size": f"{p['w']}x{p['h']}", "seconds": round(p["dur"], 1),
                            "cam": cam, "cam_frac": [round(cam[0] / p["w"], 3), round(cam[1] / p["h"], 3), round(cam[2] / p["w"], 3), round(cam[3] / p["h"], 3)] if cam else None,
                            "sheet": f"{cf.RAW}/clips/camtest/{name}" if ok else None})
                print(rep[-1])
    json.dump(rep, open(os.path.join(out, "report.json"), "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__": main(sys.argv[1])
