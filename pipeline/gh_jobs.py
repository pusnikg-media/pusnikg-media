"""Collect pending render jobs for the GitHub Action (render.yml).
Sources: jobs/*.json in the repo (written in chat) and, optionally, job-*.json files in a Google Drive folder
shared "anyone with the link" (DRIVE_FOLDER env; written by scheduled producers, read via the public folder view).
A job is pending while shorts/<name>.json (the result) does not exist. Prints a JSON list of spec paths."""
import glob, html, json, os, re, sys, urllib.request

os.makedirs("/home/runner/jobs_in", exist_ok=True)
pending, seen = [], set()


def consider(spec, src):
    name = re.sub(r"[^a-z0-9-]", "", spec.get("name") or "")
    if not name or name in seen: return
    seen.add(name)
    if os.path.exists(f"shorts/{name}.json") and not spec.get("force"):
        return
    p = f"/home/runner/jobs_in/{name}.json"; json.dump(spec, open(p, "w"), ensure_ascii=False)
    pending.append(p); print(f"pending: {name} ({src})", file=sys.stderr)


for f in sorted(glob.glob("jobs/*.json")):
    try: consider(json.load(open(f)), f)
    except Exception as e: print(f"skip {f}: {e}", file=sys.stderr)

folder = os.environ.get("DRIVE_FOLDER", "").strip()
if folder:
    try:
        ua = {"User-Agent": "Mozilla/5.0"}
        page = urllib.request.urlopen(urllib.request.Request(f"https://drive.google.com/embeddedfolderview?id={folder}", headers=ua), timeout=30).read().decode("utf-8", "replace")
        items = re.findall(r'href="https://drive\.google\.com/file/d/([\w-]{20,})/[^"]*"[^>]*>.*?flip-entry-title">([^<]+)<', page, re.S)
        print(f"drive folder: {len(items)} files", file=sys.stderr)
        for fid, title in items:
            if not re.match(r"job-.*\.json$", html.unescape(title).strip()): continue
            raw = urllib.request.urlopen(urllib.request.Request(f"https://drive.google.com/uc?export=download&id={fid}", headers=ua), timeout=30).read().decode("utf-8", "replace")
            m = re.search(r"\{.*\}", raw, re.S)
            if m: consider(json.loads(m.group(0)), f"drive:{title}")
    except Exception as e:
        print(f"drive folder not readable ({e}) - is it shared 'anyone with the link'?", file=sys.stderr)

print(json.dumps(pending[:6]))
