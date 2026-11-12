"""Glue between pipeline/scenes3d/clips.json and assets/ai_library.json (used by .github/workflows/scenes3d.yml).
  python3 library.py pending            -> comma-separated clip ids that are missing in the library or have a newer "rev"
  python3 library.py entries OUTDIR     -> writes OUTDIR/new_entries.json for every OUTDIR/<id>.mp4 that was rendered"""
import datetime, json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "..", "..", "assets", "ai_library.json")
clips = json.load(open(os.path.join(HERE, "clips.json")))["clips"]
try: have = {e["id"]: e for e in json.load(open(LIB)).get("items", [])}
except Exception: have = {}
if sys.argv[1] == "pending":
    print(",".join(c["id"] for c in clips if not have.get(c["id"], {}).get("url") or have[c["id"]].get("rev", 1) != c.get("rev", 1)))
else:
    out = sys.argv[2]; repo = os.environ.get("GITHUB_REPOSITORY", "pusnikg-media/pusnikg-media"); new = []
    for c in clips:
        f = os.path.join(out, c["id"] + ".mp4")
        if not os.path.exists(f) or os.path.getsize(f) < 200_000: continue
        d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f], capture_output=True, text=True).stdout.strip()
        new.append({"id": c["id"], "kind": "video", "category": "3d", "tags": c.get("tags", []), "model": "threejs", "rev": c.get("rev", 1),
                    "url": f"https://github.com/{repo}/releases/download/ai-library/{c['id']}.mp4", "duration": round(float(d or 0), 2),
                    "prompt": c.get("prompt", ""), "saved": datetime.date.today().isoformat()})
    json.dump(new, open(os.path.join(out, "new_entries.json"), "w"), indent=1)
    print("ENTRIES", len(new))
