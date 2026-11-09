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
    prev = {}
    if os.path.exists(f"shorts/{name}.json"):
        try: prev = json.load(open(f"shorts/{name}.json"))
        except Exception: prev = {}
    if prev.get("ok") and not spec.get("force"): return
    if not prev.get("ok") and prev.get("attempts", 1) >= 3 and not spec.get("force"):
        print(f"gave up: {name} (3 failed attempts)", file=sys.stderr); return
    spec["_attempt"] = (prev.get("attempts", 0) + 1) if prev and not prev.get("ok") else 1
    p = f"/home/runner/jobs_in/{name}.json"; json.dump(spec, open(p, "w"), ensure_ascii=False)
    pending.append(p); print(f"pending: {name} ({src})", file=sys.stderr)


def with_tiktok_cut(spec):
    """A spec with "tiktok_lines" (script line indices, e.g. [0, 1, 4, 5]) also yields <name>-tt: the same short cut
    to those lines only (12-15 s) for TikTok, where viewers swipe after 2-8 s. Card kept only if its line survives."""
    out = [spec]
    keep = spec.get("tiktok_lines")
    if not keep or not spec.get("name"): return out
    try:
        keep = sorted({int(i) for i in keep if 0 <= int(i) < len(spec["script"])})
        if len(keep) < 2: return out
        tt = {k: v for k, v in spec.items() if k not in ("tiktok_lines", "card", "force")}
        tt["name"] = spec["name"] + "-tt"
        tt["script"] = [spec["script"][i] for i in keep]
        tt["shots"] = [spec["shots"][i] for i in keep]
        tt["qa_range"] = [8, 20]
        words = [re.sub(r"[^a-z0-9]", "", w.lower()) for l in tt["script"] for w in l.split()]
        tt["punch"] = [p for p in spec.get("punch", []) if any(w.startswith(re.sub(r"[^a-z0-9]", "", str(p).lower())) for w in words)]
        c = spec.get("card")
        if c and c.get("line") in keep: tt["card"] = dict(c, line=keep.index(c["line"]))
        out.append(tt)
    except Exception as e:
        print(f"tiktok cut skipped for {spec.get('name')}: {e}", file=sys.stderr)
    return out


for f in sorted(glob.glob("jobs/*.json")):
    try:
        for sp in with_tiktok_cut(json.load(open(f))): consider(sp, f)
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
            if m:
                for sp in with_tiktok_cut(json.loads(m.group(0))): consider(sp, f"drive:{title}")
    except Exception as e:
        print(f"drive folder not readable ({e}) - is it shared 'anyone with the link'?", file=sys.stderr)

print(json.dumps(pending[:8]))
