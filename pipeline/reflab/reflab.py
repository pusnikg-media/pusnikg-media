"""Reflab v0 (15.11.2026): look at what works elsewhere - without vidIQ credits.
Pulls the most-viewed recent shorts of reference accounts (and single links), measures how they are EDITED and writes
a small report + picture sheets that Claude can look at in chat. No videos are stored, only numbers and small JPEGs.

  python3 reflab.py run REPO_ROOT            reads plan/reflab.json, writes refs/latest/report.json + refs/latest/*.jpg
  python3 reflab.py measure FILE [FILE...]   prints the same metrics for local files (our own clips, for comparison)

plan/reflab.json: {"accounts": ["https://www.tiktok.com/@name", "https://www.youtube.com/@name/shorts"], "urls": ["<single video link>"],
                   "scan": 15 (newest videos looked at per account), "top": 3 (most-viewed of those analysed), "ours": ["clips/tjr5"]}
Metrics per video: seconds, views/likes (when the platform tells), cuts_per_10s, first_cut_s, speech_starts_s, words_per_s,
first_words (what is said in the first 3 s = the hook), quiet_share (seconds 12 dB under the median), and two sheets:
<id>_hook.jpg (first 3 s, 4 pictures per second) and <id>_flow.jpg (12 pictures across the video)."""
import glob, json, os, re, subprocess, sys, statistics

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "clipfabrik"))
import clipfabrik as cf


def sh(cmd, t=600):
    try: return subprocess.run(cmd, capture_output=True, text=True, timeout=t)
    except Exception as e: return subprocess.CompletedProcess(cmd, 1, "", str(e))


def measure(path, out=None, vid=None, model=None):
    import numpy as np
    p = cf.probe(path); d = p["dur"]; m = {"seconds": round(d, 1), "size": f"{p['w']}x{p['h']}"}
    cuts = cf.scene_cuts(path)
    m["cuts_per_10s"] = round(len(cuts) / max(d, 1) * 10, 1); m["first_cut_s"] = cuts[0] if cuts else None
    if p["audio"]:
        db = cf.energy(path, 0, d)
        if len(db): m["quiet_share"] = round(float((db < float(np.median(db)) - 12).mean()), 2)
        if model is not None:
            try:
                ws = cf.transcribe(cf.audio16k(path, os.path.dirname(os.path.abspath(path))), model)
                m["speech_starts_s"] = ws[0]["s"] if ws else None; m["words_per_s"] = round(len(ws) / max(d, 1), 2)
                m["first_words"] = " ".join(w["w"] for w in ws if w["s"] < 3.0)[:160]
            except Exception as e: m["transcript_error"] = str(e)[-120:]
    if out and vid:
        os.makedirs(out, exist_ok=True)
        cf.run(["ffmpeg", "-y", "-v", "error", "-t", "3", "-i", path, "-vf", "fps=4,scale=150:-2,tile=12x1", "-frames:v", "1", "-q:v", "6", os.path.join(out, vid + "_hook.jpg")])
        cf.run(["ffmpeg", "-y", "-v", "error", "-i", path, "-vf", f"fps=12/{max(d, 1):.2f},scale=150:-2,tile=12x1", "-frames:v", "1", "-q:v", "6", os.path.join(out, vid + "_flow.jpg")])
        m["hook_sheet"] = f"{cf.RAW}/refs/latest/{vid}_hook.jpg"; m["flow_sheet"] = f"{cf.RAW}/refs/latest/{vid}_flow.jpg"
    return m


def listing(account, n):
    """Newest n videos of an account with view counts (what yt-dlp can see without a login)."""
    r = sh(["yt-dlp", "-J", "--flat-playlist", "--playlist-end", str(n), account], 300)
    if r.returncode: return [], r.stderr.strip()[-200:]
    try: d = json.loads(r.stdout)
    except Exception: return [], "no listing"
    return [{"url": e.get("url") or e.get("webpage_url"), "id": str(e.get("id")), "views": e.get("view_count") or 0, "title": (e.get("title") or "")[:90]}
            for e in d.get("entries") or [] if e and (e.get("url") or e.get("webpage_url"))], ""


def fetch(url, tmp):
    for f in glob.glob(os.path.join(tmp, "v.*")): os.remove(f)
    r = sh(["yt-dlp", "--no-playlist", "--no-progress", "-f", "b[height<=720]/bv*[height<=720]+ba/b", "--merge-output-format", "mp4", "--max-filesize", "80M",
            "--match-filter", "duration<=180", "--write-info-json", "-o", os.path.join(tmp, "v.%(ext)s"), url], 600)
    v = [f for f in glob.glob(os.path.join(tmp, "v.*")) if f.endswith((".mp4", ".mkv", ".webm"))]
    if not v: return None, {}, r.stderr.strip()[-200:]
    try: info = json.load(open(os.path.join(tmp, "v.info.json")))
    except Exception: info = {}
    return v[0], info, ""


def summary(rows):
    out = {}
    for k in ("seconds", "cuts_per_10s", "first_cut_s", "speech_starts_s", "words_per_s", "quiet_share"):
        v = [r[k] for r in rows if isinstance(r.get(k), (int, float))]
        if v: out[k] = round(statistics.median(v), 2)
    out["n"] = len(rows); return out


def run(root):
    c = json.load(open(os.path.join(root, "plan", "reflab.json"))); out = os.path.join(root, "refs", "latest")
    if os.path.isdir(out):
        for f in os.listdir(out): os.remove(os.path.join(out, f))
    os.makedirs(out, exist_ok=True); tmp = os.path.join(os.environ.get("RUNNER_TEMP", "/tmp"), "reflab"); os.makedirs(tmp, exist_ok=True)
    model = c.get("whisper", "small.en"); rep = {"refs": [], "ours": [], "problems": []}
    todo = [{"url": u, "account": "link", "views": None, "title": ""} for u in c.get("urls", [])]
    for acc in c.get("accounts", []):
        items, err = listing(acc, int(c.get("scan", 15)))
        if not items: rep["problems"].append(f"{acc}: no listing ({err})"); continue
        for it in sorted(items, key=lambda x: -x["views"])[:int(c.get("top", 3))]: todo.append(dict(it, account=acc))
    for i, it in enumerate(todo[:int(c.get("max", 18))]):
        f, info, err = fetch(it["url"], tmp)
        if not f: rep["problems"].append(f"{it['url']}: download failed ({err})"); continue
        vid = "r%02d" % i
        try: m = measure(f, out, vid, model)
        except Exception as e: rep["problems"].append(f"{it['url']}: {str(e)[-150:]}"); continue
        m.update(url=it["url"], account=it["account"], views=info.get("view_count") or it.get("views"), likes=info.get("like_count"),
                 title=(info.get("title") or it.get("title") or "")[:90], caption=(info.get("description") or "")[:200])
        rep["refs"].append(m); print("REF", vid, m.get("views"), m["seconds"], m["cuts_per_10s"])
    for d in c.get("ours", []):
        for j, f in enumerate(sorted(glob.glob(os.path.join(root, d, "*.mp4")))[:6]):
            try: m = measure(f, out, "o%02d" % len(rep["ours"]), model); m["file"] = os.path.relpath(f, root); rep["ours"].append(m)
            except Exception as e: rep["problems"].append(f"{f}: {str(e)[-150:]}")
    rep["median_refs"] = summary(rep["refs"]); rep["median_ours"] = summary(rep["ours"])
    json.dump(rep, open(os.path.join(out, "report.json"), "w"), indent=1, ensure_ascii=False)
    print("REFLAB_OK refs", len(rep["refs"]), "ours", len(rep["ours"]), "problems", len(rep["problems"]))


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) == 2 and a[0] == "run": run(a[1])
    elif len(a) >= 2 and a[0] == "measure":
        for f in a[1:]: print(os.path.basename(f), json.dumps(measure(f, model="small.en"), ensure_ascii=False))
    else: sys.exit(__doc__)
