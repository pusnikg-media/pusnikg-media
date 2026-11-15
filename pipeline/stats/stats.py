"""Zahlen-Sammler v1 (15.11.2026): public view counts of our own posts - no login, no API key, no credits.

  python3 stats.py run REPO_ROOT     reads plan/stats.json, writes stats/latest.json, stats/latest.md, stats/history.json
  python3 stats.py selftest          offline test of the parsing and the history/alert logic

Sources: YouTube = the channel's public RSS feed (newest 15 public videos, exact views + likes) and, when the runner is
allowed, the Shorts tab via yt-dlp (older videos). TikTok = the profile via yt-dlp (views, likes, comments, shares).
Instagram shows nothing without a login, so it is not collected (see 'problems' in the output).
history.json keeps a few (time, views) points per post, so every run can tell what a post gained in the last 24 h,
what it had after its first 24 h / 72 h, and whether a campaign clip has just crossed its payout threshold ('alerts')."""
import datetime as dt, json, os, re, subprocess, sys, urllib.request
import xml.etree.ElementTree as ET

UTC = dt.timezone.utc
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015", "m": "http://search.yahoo.com/mrss/"}


def now(): return dt.datetime.now(UTC).replace(microsecond=0)
def iso(t): return t.strftime("%Y-%m-%dT%H:%M:%SZ")
def parse(s):
    try: return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC)
    except Exception: return None


def sh(cmd, t=300):
    try: return subprocess.run(cmd, capture_output=True, text=True, timeout=t)
    except Exception as e: return subprocess.CompletedProcess(cmd, 1, "", str(e))


def get(url, t=30):
    rq = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36", "Accept-Language": "en-US,en;q=0.8"})
    return urllib.request.urlopen(rq, timeout=t).read()


def yt_rss(xml_bytes):
    """Entries of a channel feed -> posts. Only public videos are in the feed (privately scheduled uploads are not)."""
    out = []
    for e in ET.fromstring(xml_bytes).findall("a:entry", NS):
        vid = e.findtext("yt:videoId", "", NS)
        if not vid: continue
        st = e.find("m:group/m:community/m:statistics", NS); sr = e.find("m:group/m:community/m:starRating", NS)
        out.append({"platform": "youtube", "id": vid, "url": f"https://www.youtube.com/shorts/{vid}", "title": (e.findtext("a:title", "", NS) or "")[:100],
                    "text": (e.findtext("m:group/m:description", "", NS) or "")[:600], "published": iso(parse(e.findtext("a:published", "", NS)) or now()),
                    "views": int(st.get("views", 0)) if st is not None else None, "likes": int(sr.get("count", 0)) if sr is not None else None})
    return out


def flat(entries, platform):
    """yt-dlp --flat-playlist entries -> posts (fields differ per platform and per yt-dlp version: read defensively)."""
    out = []
    for e in entries or []:
        if not e or not e.get("id"): continue
        vid = str(e["id"]); ts = e.get("timestamp") or e.get("release_timestamp")
        url = e.get("webpage_url") or e.get("url") or ""
        if platform == "youtube": url = f"https://www.youtube.com/shorts/{vid}"
        text = (e.get("description") or e.get("title") or "")
        out.append({"platform": platform, "id": vid, "url": url, "title": re.sub(r"\s+", " ", (e.get("title") or text))[:100], "text": text[:600],
                    "published": iso(dt.datetime.fromtimestamp(ts, UTC)) if ts else None, "views": e.get("view_count"),
                    "likes": e.get("like_count"), "comments": e.get("comment_count"), "shares": e.get("repost_count")})
    return out


def listing(url, n):
    r = sh(["yt-dlp", "-J", "--flat-playlist", "--playlist-end", str(n), url])
    if r.returncode: return None, (r.stderr.strip().splitlines() or ["failed"])[-1][-160:]
    try: return json.loads(r.stdout).get("entries") or [], ""
    except Exception: return None, "no listing"


def collect(cfg, problems):
    posts = []; n = int(cfg.get("scan", 40))
    for acc in cfg.get("accounts", []):
        got = {}
        if acc.get("youtube"):
            try:
                for p in yt_rss(get("https://www.youtube.com/feeds/videos.xml?channel_id=" + acc["youtube"])): got[("youtube", p["id"])] = p
            except Exception as e: problems.append(f"{acc['name']} YouTube feed: {str(e)[-120:]}")
            ent, err = listing(f"https://www.youtube.com/channel/{acc['youtube']}/shorts", n)
            if ent is None: problems.append(f"{acc['name']} YouTube shorts tab: {err}")
            else:
                for p in flat(ent, "youtube"):
                    k = ("youtube", p["id"])
                    if k not in got and p.get("views") is not None: got[k] = p          # the feed is exact, the tab only fills the gaps
        if acc.get("tiktok"):
            ent, err = listing(f"https://www.tiktok.com/@{acc['tiktok']}", n)
            if ent is None: problems.append(f"{acc['name']} TikTok: {err}")
            else:
                for p in flat(ent, "tiktok"):
                    if not p["url"].startswith("http"): p["url"] = f"https://www.tiktok.com/@{acc['tiktok']}/video/{p['id']}"
                    got[("tiktok", p["id"])] = p
        if not any(k[0] == "tiktok" for k in got) and acc.get("tiktok") and not any("TikTok" in x and acc["name"] in x for x in problems):
            problems.append(f"{acc['name']} TikTok: profile readable, but no videos listed")
        for p in got.values(): p["account"] = acc["name"]; posts.append(p)
    problems.append("Instagram: not collected (no public numbers without a login)")
    return posts


def campaign(p, cfg):
    t = (p.get("title", "") + " " + p.get("text", "")).lower()
    for c in cfg.get("campaigns", []):
        if any(w.lower() in t for w in c.get("match", [])): return c
    return None


def at_age(pts, pub, hours):
    """Views at the first measurement taken at least `hours` after publishing (None when we never measured that late or started too late)."""
    if not pub: return None
    for t, v in pts:
        age = (parse(t) - pub).total_seconds() / 3600
        if age >= hours: return v if age <= hours * 1.6 + 6 else None
    return None


def update(posts, hist, cfg, t=None):
    """Adds this run's numbers to the history and derives growth + alerts. hist: {url: {"pub": iso, "pts": [[iso, views], ...]}}"""
    t = t or now(); alerts = []; keep = int(cfg.get("keep_days", 45))
    for p in posts:
        if p.get("views") is None: continue
        h = hist.setdefault(p["url"], {"pub": p.get("published"), "pts": []})
        if p.get("published"): h["pub"] = p["published"]
        elif h.get("pub"): p["published"] = h["pub"]
        elif h["pts"]: p["published"] = h["pts"][0][0]                                   # no date from the platform: first time we saw it
        prev = h["pts"][-1][1] if h["pts"] else None
        if not h["pts"] or (t - parse(h["pts"][-1][0])).total_seconds() >= 3 * 3600: h["pts"].append([iso(t), p["views"]])
        else: h["pts"][-1][1] = p["views"]
        if len(h["pts"]) > 60: h["pts"] = h["pts"][:6] + h["pts"][-54:]
        pub = parse(p["published"]) if p.get("published") else None
        if pub: p["age_h"] = round((t - pub).total_seconds() / 3600, 1)
        old = [v for ts, v in h["pts"] if 20 <= (t - parse(ts)).total_seconds() / 3600 <= 34]
        p["plus_24h"] = p["views"] - old[-1] if old else None
        p["views_24h"] = at_age(h["pts"], pub, 24); p["views_72h"] = at_age(h["pts"], pub, 72)
        c = campaign(p, cfg)
        if c:
            p["campaign"] = c["name"]; mv = c.get("min_views")
            if mv:
                p["min_views"] = mv; p["reached"] = p["views"] >= mv
                if p["reached"] and (prev is None or prev < mv): alerts.append({"account": p["account"], "campaign": c["name"], "platform": p["platform"], "title": p["title"], "url": p["url"], "views": p["views"], "min_views": mv})
        p.pop("text", None)
    for u in [u for u, h in hist.items() if h["pts"] and (t - parse(h["pts"][-1][0])).days > keep]: del hist[u]
    return alerts


def de(n): return "–" if n is None else f"{n:,}".replace(",", ".")


def markdown(out):
    L = [f"# Zahlen – Stand {out['updated_berlin']} (Europe/Berlin)", "", "Öffentliche Zahlen der eigenen Posts, ohne Login gesammelt. `+24h` = Zuwachs seit der Messung vor etwa einem Tag, `24h` = Views einen Tag nach Veröffentlichung.", ""]
    if out["alerts"]:
        L += ["## Schwelle erreicht (seit dem letzten Lauf)"] + [f"- {a['campaign']} auf {a['account']} ({a['platform']}): {de(a['views'])} Views, Schwelle {de(a['min_views'])} – {a['url']}" for a in out["alerts"]] + [""]
    for acc, s in out["accounts"].items():
        L += [f"## {acc}", f"Posts gezählt: {s['posts']} · Views gesamt: {de(s['views'])} · Zuwachs 24 h: {de(s['plus_24h'])}", "", "| Datum | Plattform | Titel | Views | +24h | 24h | Likes | Kampagne |", "|---|---|---|---|---|---|---|---|"]
        for p in [p for p in out["posts"] if p["account"] == acc][:24]:
            L.append(f"| {(p.get('published') or '')[:10]} | {p['platform']} | {p['title'][:48].replace('|', '/')} | {de(p['views'])} | {de(p.get('plus_24h'))} | {de(p.get('views_24h'))} | {de(p.get('likes'))} | {p.get('campaign', '')}{' ✅' if p.get('reached') else ''} |")
        L.append("")
    if out["by_campaign"]:
        L += ["## Kampagnen", "| Kampagne | Clips | Views gesamt | bester Clip | über der Schwelle |", "|---|---|---|---|---|"]
        L += [f"| {k} | {v['clips']} | {de(v['views'])} | {de(v['best'])} | {v['reached'] if v['min_views'] else '–'}{(' von ' + str(v['clips'])) if v['min_views'] else ''} |" for k, v in out["by_campaign"].items()] + [""]
    L += ["## Nicht lesbar"] + [f"- {x}" for x in out["problems"]]
    return "\n".join(L) + "\n"


def build(posts, alerts, problems, t=None):
    t = t or now(); posts = [p for p in posts if p.get("views") is not None]
    posts.sort(key=lambda p: p.get("published") or "", reverse=True)
    acc = {}; camp = {}
    for p in posts:
        s = acc.setdefault(p["account"], {"posts": 0, "views": 0, "plus_24h": 0}); s["posts"] += 1; s["views"] += p["views"]; s["plus_24h"] += p.get("plus_24h") or 0
        if p.get("campaign"):
            c = camp.setdefault(p["campaign"], {"clips": 0, "views": 0, "best": 0, "reached": 0, "min_views": p.get("min_views")}); c["clips"] += 1; c["views"] += p["views"]; c["best"] = max(c["best"], p["views"]); c["reached"] += 1 if p.get("reached") else 0
    try:
        from zoneinfo import ZoneInfo
        local = t.astimezone(ZoneInfo("Europe/Berlin")).strftime("%d.%m.%Y %H:%M")
    except Exception: local = iso(t)
    return {"updated": iso(t), "updated_berlin": local, "accounts": acc, "by_campaign": camp, "alerts": alerts, "problems": problems, "posts": posts}


def run(root):
    cfg = json.load(open(os.path.join(root, "plan", "stats.json"))); out_dir = os.path.join(root, "stats"); os.makedirs(out_dir, exist_ok=True)
    hp = os.path.join(out_dir, "history.json")
    try: hist = json.load(open(hp))
    except Exception: hist = {}
    problems = []; posts = collect(cfg, problems)
    if not [p for p in posts if p.get("views") is not None]:
        print("NOTHING READABLE:", problems); return 1                                    # keep the last good files
    alerts = update(posts, hist, cfg); out = build(posts, alerts, problems)
    json.dump(out, open(os.path.join(out_dir, "latest.json"), "w"), ensure_ascii=False, indent=1)
    json.dump(hist, open(hp, "w"), ensure_ascii=False, separators=(",", ":"))
    open(os.path.join(out_dir, "latest.md"), "w").write(markdown(out))
    print(f"posts {len(out['posts'])}, alerts {len(alerts)}, problems {len(problems)}"); [print(" -", x) for x in problems]
    return 0


def selftest():
    feed = b"""<?xml version="1.0"?><feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
    <entry><yt:videoId>abc</yt:videoId><title>TJR gets a car #shorts</title><published>2026-11-10T17:00:00+00:00</published>
    <media:group><media:description>Clip #TJR #cars</media:description><media:community><media:starRating count="12" average="5.00"/><media:statistics views="4900"/></media:community></media:group></entry></feed>"""
    cfg = {"campaigns": [{"name": "TJR", "match": ["#tjr"], "min_views": 5000}], "keep_days": 45}
    t0 = dt.datetime(2026, 11, 11, 18, 0, tzinfo=UTC); hist = {}
    p = yt_rss(feed); assert p[0]["views"] == 4900 and p[0]["likes"] == 12 and p[0]["url"].endswith("/abc"), p
    tk = flat([{"id": 7, "title": "x", "description": "Lacy #JasonTheWeen", "timestamp": 1794400000, "view_count": 321, "like_count": 4, "url": "https://www.tiktok.com/@a/video/7"}, None, {"title": "no id"}], "tiktok")
    assert len(tk) == 1 and tk[0]["views"] == 321 and tk[0]["published"].startswith("2026-"), tk
    for q in p: q["account"] = "Pusnik IRL"
    a = update(p, hist, cfg, t0); assert a == [] and p[0]["campaign"] == "TJR" and p[0]["reached"] is False and p[0]["views_24h"] == 4900 and p[0]["plus_24h"] is None, (a, p)
    p = yt_rss(feed.replace(b'views="4900"', b'views="5200"'))
    for q in p: q["account"] = "Pusnik IRL"
    a = update(p, hist, cfg, t0 + dt.timedelta(hours=24)); assert len(a) == 1 and p[0]["plus_24h"] == 300 and p[0]["reached"], (a, p)
    p2 = yt_rss(feed.replace(b'views="4900"', b'views="5300"'))
    for q in p2: q["account"] = "Pusnik IRL"
    a = update(p2, hist, cfg, t0 + dt.timedelta(hours=25)); assert a == [] and len(hist[p2[0]["url"]]["pts"]) == 2, (a, hist)   # no second alert, no extra point within 3 h
    out = build(p2, a, ["Instagram: not collected"], t0); md = markdown(out)
    assert "5.300" in md and "TJR ✅" in md and out["by_campaign"]["TJR"]["reached"] == 1 and out["accounts"]["Pusnik IRL"]["views"] == 5300, md
    update([], hist, cfg, t0 + dt.timedelta(days=60)); assert hist == {}, hist                                                     # old posts leave the history
    print("SELFTEST OK")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest": selftest()
    elif len(sys.argv) > 2 and sys.argv[1] == "run": sys.exit(run(sys.argv[2]))
    else: print(__doc__)
