"""Pusnik G AI library: make generated clips (Higgsfield trial, 11.-14.11.2026) permanent.
Usage: python3 pipeline/ai_assets.py OUT_DIR
Reads  assets/ai_queue.json   {"items": [{"id": "city01a", "url": "https://...", "model": "veo-3.1"}]}
       plan/higgsfield_shotlist.json (kind, category, tags, prompt per id)
       assets/ai_library.json  (already saved ids are skipped)
Writes OUT_DIR/files/<id>.<ext> (normalized media) and OUT_DIR/new_entries.json; the workflow uploads the files
to the GitHub release "ai-library" and merges the entries into assets/ai_library.json.
Library entry: {"id","kind","category","tags","model","url","duration","prompt","saved"} or {"id","error","attempts"}."""
import datetime, json, os, subprocess, sys, urllib.request

OUT = sys.argv[1]; FILES = os.path.join(OUT, "files"); os.makedirs(FILES, exist_ok=True)
REPO = os.environ.get("GITHUB_REPOSITORY", "pusnikg-media/pusnikg-media")
REL = f"https://github.com/{REPO}/releases/download/ai-library"
load = lambda p, d: json.load(open(p)) if os.path.exists(p) else d
queue = load("assets/ai_queue.json", {"items": []}).get("items", [])
shots = {i["id"]: i for i in load("plan/higgsfield_shotlist.json", {"items": []})["items"]}
lib = {e["id"]: e for e in load("assets/ai_library.json", {"items": []}).get("items", [])}
EXT = {"video": "mp4", "image": "jpg", "music": "m4a"}


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode: raise RuntimeError(r.stderr[-400:])
    return r.stdout


def fetch(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (pusnikg-library/1.0)"})
    with urllib.request.urlopen(req, timeout=180) as r, open(dest, "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b: break
            f.write(b)
    if os.path.getsize(dest) < 10_000: raise RuntimeError(f"download too small ({os.path.getsize(dest)} bytes)")


def duration(p):
    try: return round(float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).strip()), 2)
    except Exception: return 0.0


new = []
for q in queue:
    qid, url = q.get("id"), q.get("url")
    if not qid or not url: continue
    old = lib.get(qid, {})
    if old.get("url") or old.get("attempts", 0) >= 3: continue  # saved, or given up after 3 tries
    s = shots.get(qid, {}); kind = q.get("kind") or s.get("kind") or "video"
    raw = os.path.join(OUT, f"raw_{qid}"); dst = os.path.join(FILES, f"{qid}.{EXT.get(kind, 'bin')}")
    try:
        fetch(url, raw)
        if kind == "video":
            run(["ffmpeg", "-y", "-v", "error", "-i", raw, "-an", "-vf",
                 "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-movflags", "+faststart", dst])
            if duration(dst) < 1.5: raise RuntimeError("video shorter than 1.5 s")
        elif kind == "image":
            run(["ffmpeg", "-y", "-v", "error", "-i", raw, "-vf",
                 "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920", "-q:v", "3", "-frames:v", "1", dst])
        else:
            run(["ffmpeg", "-y", "-v", "error", "-i", raw, "-vn", "-c:a", "aac", "-b:a", "192k", dst])
            if duration(dst) < 10: raise RuntimeError("music shorter than 10 s")
        new.append({"id": qid, "kind": kind, "category": s.get("category", ""), "tags": s.get("tags", []),
                    "model": q.get("model", ""), "url": f"{REL}/{os.path.basename(dst)}", "duration": duration(dst),
                    "prompt": s.get("prompt", q.get("prompt", ""))[:300], "saved": datetime.date.today().isoformat()})
        print("SAVED", qid, os.path.getsize(dst) // 1024, "KB")
    except Exception as e:
        if os.path.exists(dst): os.remove(dst)
        new.append({"id": qid, "error": str(e)[:200], "attempts": old.get("attempts", 0) + 1, "source": url[:300]})
        print("FAIL", qid, e)
    finally:
        if os.path.exists(raw): os.remove(raw)
json.dump(new, open(os.path.join(OUT, "new_entries.json"), "w"), indent=1)
print(f"AI_ASSETS_DONE new={sum(1 for n in new if n.get('url'))} failed={sum(1 for n in new if n.get('error'))}")
