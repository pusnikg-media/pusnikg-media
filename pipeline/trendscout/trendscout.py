#!/usr/bin/env python3
"""Trendscout: what is going viral right now, without login, API key, vidIQ credits or Claude quota.

Sources (all public, read-only, nothing is posted or liked, our social accounts are never involved):
  reddit  - top posts of the day per subreddit (Atom feed; order = rank, the feed carries no scores)
  kick    - most viewed clips of the day per streamer + overall (public clip API, incl. direct video URL)
  youtube - recent uploads of watched channels with view counts (channel feed) -> views per hour
  news    - RSS feeds of gaming news sites, filtered by key words (GTA 6 launch radar); a story several sites report ranks first

Writes trends/latest.md (short, for agents), trends/latest.json (full) and trends/seen.json (what was already listed,
so new items get a NEW mark). Config: plan/trendscout.json.

  python3 pipeline/trendscout/trendscout.py run .        collect and write
  python3 pipeline/trendscout/trendscout.py selftest     parser checks, no network
"""
import datetime as D
import html
import json
import os
import re
import sys
import time
import urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 pusnikg-trendscout"
CLIP_HOSTS = ("clips.twitch.tv", "twitch.tv", "kick.com", "youtube.com", "youtu.be", "streamable.com", "livestreamfails.com",
              "v.redd.it", "x.com", "twitter.com", "tiktok.com", "instagram.com")
DEFAULTS = {
    "reddit": [{"sub": "LivestreamFail", "area": "irl", "top": 12}, {"sub": "GTA6", "area": "gaming", "top": 8}],
    "kick": {"channels": [], "per_channel": 4, "overall": 8, "min_views": 300},
    "youtube": [],
    "news": {"feeds": [], "words": ["gta", "grand theft auto", "rockstar"], "top": 10, "max_age_hours": 30},
    "max_age_hours": 36,
}


def now():
    return D.datetime.now(D.timezone.utc)


def get(url, tries=3):
    """Fetch text. curl_cffi (browser fingerprint) when installed, else urllib. Backs off on 429/5xx."""
    err = None
    for i in range(tries):
        try:
            try:
                from curl_cffi import requests as cr
                r = cr.get(url, impersonate="chrome", timeout=25, headers={"Accept-Language": "en-US,en;q=0.8"})
                code, text = r.status_code, r.text
            except ImportError:
                rq = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.8"})
                with urllib.request.urlopen(rq, timeout=25) as r:
                    code, text = r.status, r.read().decode("utf-8", "replace")
            if code == 200 and text.strip():
                return text
            err = f"HTTP {code}"
        except Exception as e:  # noqa: BLE001 - every source is optional
            err = f"{type(e).__name__}: {str(e)[:80]}"
        time.sleep((15 if "429" in str(err) else 4) * (i + 1))
    raise RuntimeError(err or "empty")


def ts(s):
    try:
        return D.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


def age_h(t):
    return round((now() - t).total_seconds() / 3600, 1) if t else None


# ---------- reddit ----------
def parse_reddit(xml, sub, area, top):
    out = []
    for rank, e in enumerate(xml.split("<entry>")[1:], 1):
        title = html.unescape(re.search(r"<title>(.*?)</title>", e, re.S).group(1)).strip()
        post = re.search(r'<link href="([^"]+)"', e)
        body = html.unescape((re.search(r"<content[^>]*>(.*?)</content>", e, re.S) or [None, ""])[1])
        ext = re.search(r'<a href="([^"]+)">\[link\]</a>', body)
        ext = ext.group(1) if ext else ""
        when = ts((re.search(r"<published>(.*?)</published>", e) or re.search(r"<updated>(.*?)</updated>", e) or [0, ""])[1])
        host = re.sub(r"^www\.", "", re.sub(r"^https?://([^/]+).*", r"\1", ext)) if ext else ""
        out.append({"src": "reddit", "sub": sub, "area": area, "rank": rank, "title": title,
                    "post": post.group(1) if post else "", "link": ext if "reddit.com" not in host else "",
                    "is_clip": any(host.endswith(h) for h in CLIP_HOSTS), "host": host, "age_h": age_h(when),
                    "id": "r:" + (re.search(r"/comments/(\w+)", post.group(1)).group(1) if post and "/comments/" in post.group(1) else title[:40])})
        if rank >= top:
            break
    return out


def reddit(cfg, errors):
    out = []
    for s in cfg:
        try:
            xml = get(f"https://www.reddit.com/r/{s['sub']}/top/.rss?t=day&limit={int(s.get('top', 10)) + 3}")
            got = parse_reddit(xml, s["sub"], s.get("area", "gaming"), int(s.get("top", 10)))
            if not got:
                raise RuntimeError("feed without entries")
            out += got
        except Exception as e:  # noqa: BLE001
            errors.append(f"reddit r/{s['sub']}: {e}")
        time.sleep(12)
    return out


# ---------- kick ----------
def parse_kick(js, max_age, min_views, limit):
    out = []
    for c in (json.loads(js).get("clips") or []):
        a = age_h(ts(c.get("created_at", "")))
        v = c.get("view_count") or c.get("views") or 0
        if a is None or a > max_age or v < min_views:
            continue
        ch = (c.get("channel") or {}).get("slug") or ""
        out.append({"src": "kick", "area": "irl", "channel": ch, "title": (c.get("title") or "").strip(), "views": v,
                    "per_h": round(v / max(a, 0.5)), "dur": c.get("duration"), "age_h": a,
                    "category": (c.get("category") or {}).get("name") or "",
                    "page": f"https://kick.com/{ch}/clips/{c.get('id')}", "video": c.get("clip_url") or c.get("video_url") or "",
                    "mature": bool(c.get("is_mature")), "id": "k:" + str(c.get("id"))})
    out.sort(key=lambda x: -x["views"])
    return out[:limit]


def kick(cfg, max_age, errors):
    out, mv = [], int(cfg.get("min_views", 300))
    for ch in cfg.get("channels", []):
        try:
            out += [dict(x, watched=True) for x in parse_kick(get(f"https://kick.com/api/v2/channels/{ch}/clips?sort=view&time=day"),
                                                              max_age, mv, int(cfg.get("per_channel", 4)))]
        except Exception as e:  # noqa: BLE001
            errors.append(f"kick {ch}: {e}")
        time.sleep(1.5)
    if int(cfg.get("overall", 0)):
        try:
            have = {x["id"] for x in out}
            out += [x for x in parse_kick(get("https://kick.com/api/v2/clips?sort=view&time=day"), max_age, mv, int(cfg["overall"]))
                    if x["id"] not in have]
        except Exception as e:  # noqa: BLE001
            errors.append(f"kick overall: {e}")
    return out


# ---------- youtube ----------
def parse_youtube(xml, name, area, max_age):
    out = []
    for e in xml.split("<entry>")[1:]:
        vid = re.search(r"<yt:videoId>(.*?)</yt:videoId>", e)
        views = re.search(r'<media:statistics views="(\d+)"', e)
        when = ts((re.search(r"<published>(.*?)</published>", e) or [0, ""])[1])
        a = age_h(when)
        if not vid or not views or a is None or a > max_age:
            continue
        v = int(views.group(1))
        out.append({"src": "youtube", "area": area, "channel": name, "views": v, "per_h": round(v / max(a, 0.5)), "age_h": a,
                    "title": html.unescape(re.search(r"<title>(.*?)</title>", e, re.S).group(1)).strip(),
                    "page": ("https://www.youtube.com/shorts/" if "/shorts/" in e else "https://www.youtube.com/watch?v=") + vid.group(1),
                    "id": "y:" + vid.group(1)})
    return out


def youtube(cfg, max_age, errors):
    out = []
    for c in cfg:
        try:
            out += parse_youtube(get(f"https://www.youtube.com/feeds/videos.xml?channel_id={c['id']}"), c.get("name", c["id"]),
                                 c.get("area", "gaming"), max(max_age, 72))
        except Exception as e:  # noqa: BLE001
            errors.append(f"youtube {c.get('name', c.get('id'))}: {e}")
        time.sleep(0.5)
    out.sort(key=lambda x: -x["per_h"])
    return out[:12]


# ---------- news ----------
STOP = set("the a an of to in on for and or is are was be with at by from as it its this that new gta vi 6 grand theft auto rockstar games game "
           "how what why when will has have you your can here everything need know about after before just more first all get gets".split())


def rfc_ts(s):
    s = (s or "").strip()
    try:
        from email.utils import parsedate_to_datetime
        t = parsedate_to_datetime(s)
        return t if t.tzinfo else t.replace(tzinfo=D.timezone.utc)
    except Exception:  # noqa: BLE001
        return ts(s)


def key_words(title):
    return {w for w in re.findall(r"[a-z0-9']+", title.lower()) if w not in STOP and len(w) > 2}


def parse_news(xml, name, words, max_age):
    out = []
    for e in re.split(r"<item[ >]|<entry[ >]", xml)[1:]:
        m = re.search(r"<title[^>]*>(.*?)</title>", e, re.S)
        if not m:
            continue
        title = html.unescape(html.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", m.group(1)))).strip()
        title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", title))
        low = " " + title.lower() + " "
        if not any(re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", low) for w in words):
            continue
        link = re.search(r"<link[^>]*href=\"([^\"]+)\"", e) or re.search(r"<link[^>]*>\s*(?:<!\[CDATA\[)?\s*(https?://[^<\]\s]+)", e)
        when = re.search(r"<pubDate>(.*?)</pubDate>|<published>(.*?)</published>|<updated>(.*?)</updated>|<dc:date>(.*?)</dc:date>", e, re.S)
        a = age_h(rfc_ts(next((g for g in when.groups() if g), "")) if when else None)
        if a is None or a > max_age or a < -2:
            continue
        url = html.unescape(link.group(1)) if link else ""
        out.append({"src": "news", "area": "gaming", "site": name, "title": title, "page": url, "age_h": max(a, 0.0),
                    "id": "n:" + re.sub(r"[^a-z0-9]+", "-", title.lower())[:60]})
    return out


def news(cfg, errors):
    got, words = [], [w.lower() for w in cfg.get("words", [])]
    for f in cfg.get("feeds", []):
        try:
            got += parse_news(get(f["url"], tries=2), f.get("name", f["url"]), words, float(cfg.get("max_age_hours", 30)))
        except Exception as e:  # noqa: BLE001
            errors.append(f"news {f.get('name', f.get('url'))}: {e}")
        time.sleep(0.5)
    # one story reported by several sites = one line; the more sites, the bigger the story
    got.sort(key=lambda x: x["age_h"]); groups = []
    for x in got:
        kw = key_words(x["title"])
        for g in groups:
            if x["site"] not in g["sites"] and len(kw & g["kw"]) >= max(2, min(3, min(len(kw), len(g["kw"])) // 2)):
                g["sites"].append(x["site"]); g["kw"] |= kw; break
            if x["site"] in g["sites"] and x["id"] == g["id"]:
                break
        else:
            groups.append(dict(x, sites=[x["site"]], kw=kw))
    groups.sort(key=lambda g: (-len(g["sites"]), g["age_h"]))
    return [{k: v for k, v in g.items() if k != "kw"} for g in groups[:int(cfg.get("top", 10))]]


# ---------- output ----------
def cut(s, n):
    s = re.sub(r"\s+", " ", s or "").replace("|", "/")
    return s if len(s) <= n else s[:n - 1] + "…"


def render(items, errors, seen):
    new = lambda x: "NEW " if x["id"] not in seen else ""  # noqa: E731
    L = [f"# Trendscout – {now().strftime('%d.%m.%Y %H:%M')} UTC", "",
         "Automatisch gesammelt (Reddit, Kick, YouTube-Feeds, Gaming-News), ohne Login/Credits. NEW = beim letzten Lauf noch nicht dabei.", ""]
    nn = [x for x in items if x["src"] == "news"]
    if nn:
        L += ["## GTA-6-News (letzte 30 h, Gaming-Newsseiten)", "Mehrere Quellen = große Geschichte. Für Shorts nur Fakten verwenden, die im verlinkten Artikel stehen; Leaks/Gerüchte als solche benennen.", ""]
        L += [f"- {new(x)}{'[' + str(len(x['sites'])) + ' Quellen] ' if len(x['sites']) > 1 else ''}{cut(x['title'], 120)} – {', '.join(x['sites'][:4])}, "
              f"vor {x['age_h']:.0f} h → {x['page']}" for x in nn] + [""]
    for area, head in (("irl", "IRL / Streamer"), ("gaming", "Gaming / GTA 6")):
        rd = [x for x in items if x["src"] == "reddit" and x["area"] == area]
        for sub in dict.fromkeys(x["sub"] for x in rd):
            L += [f"## {head} – Reddit r/{sub} (Top des Tages, nach Rang)"]
            L += [f"{x['rank']}. {new(x)}{cut(x['title'], 110)}" + (f" → {x['link']}" if x["is_clip"] else "") for x in rd if x["sub"] == sub]
            L += [""]
    kk = [x for x in items if x["src"] == "kick"]
    if kk:
        L += ["## Kick – meistgesehene Clips (24–36 h)", "W = beobachteter Kampagnen-Streamer. `video` in latest.json ist direkt als Clipfabrik-`source` nutzbar.", ""]
        L += [f"- {new(x)}{'W ' if x.get('watched') else ''}{x['channel']}: „{cut(x['title'], 60)}“ – {x['views']} Views, {x['dur']} s, "
              f"{x['category']}{', 18+' if x['mature'] else ''} → {x['page']}" for x in kk] + [""]
    yy = [x for x in items if x["src"] == "youtube"]
    if yy:
        L += ["## YouTube – beobachtete Kanäle (Views pro Stunde)", ""]
        L += [f"- {new(x)}{x['channel']}: {cut(x['title'], 80)} – {x['views']} Views, {x['per_h']}/h, {x['age_h']} h alt → {x['page']}" for x in yy] + [""]
    if errors:
        L += ["## Nicht erreichbar", ""] + [f"- {e}" for e in errors] + [""]
    return "\n".join(L)


def run(root):
    cfg = dict(DEFAULTS)
    p = os.path.join(root, "plan", "trendscout.json")
    if os.path.exists(p):
        cfg.update({k: v for k, v in json.load(open(p, encoding="utf-8")).items() if k in DEFAULTS})
    errors, max_age = [], float(cfg["max_age_hours"])
    items = (reddit(cfg["reddit"], errors) + kick(cfg["kick"], max_age, errors) + youtube(cfg["youtube"], max_age, errors)
             + news(cfg["news"], errors))
    out = os.path.join(root, "trends")
    os.makedirs(out, exist_ok=True)
    sp = os.path.join(out, "seen.json")
    seen = json.load(open(sp, encoding="utf-8")) if os.path.exists(sp) else {}
    if not items:  # keep the last good report instead of overwriting it with nothing
        print("NO DATA:", errors)
        return 1
    open(os.path.join(out, "latest.md"), "w", encoding="utf-8").write(render(items, errors, seen))
    json.dump({"at": now().isoformat(timespec="seconds"), "errors": errors,
               "items": [dict(x, new=x["id"] not in seen) for x in items]},
              open(os.path.join(out, "latest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    stamp = now().isoformat(timespec="seconds")
    for x in items:
        seen.setdefault(x["id"], stamp)
    limit = (now() - D.timedelta(days=14)).isoformat(timespec="seconds")
    json.dump({k: v for k, v in seen.items() if v >= limit}, open(sp, "w", encoding="utf-8"), indent=0)
    print(f"OK {len(items)} items, {len(errors)} errors")
    return 0


def selftest():
    t = (now() - D.timedelta(hours=5)).isoformat(timespec="seconds")
    rx = ('<feed><entry><content type="html">&lt;a href=&quot;https://clips.twitch.tv/Abc&quot;&gt;[link]&lt;/a&gt;</content>'
          '<link href="https://www.reddit.com/r/LivestreamFail/comments/1abc/x/" />'
          f'<published>{t}</published><title>Streamer &amp; chat lose it</title></entry></feed>')
    r = parse_reddit(rx, "LivestreamFail", "irl", 5)
    assert r[0]["title"] == "Streamer & chat lose it" and r[0]["is_clip"] and r[0]["id"] == "r:1abc" and 4.9 <= r[0]["age_h"] <= 5.1, r
    kj = json.dumps({"clips": [
        {"id": "c1", "title": "big", "view_count": 5000, "duration": 30, "created_at": t, "clip_url": "u", "channel": {"slug": "a"}},
        {"id": "c2", "title": "small", "view_count": 10, "duration": 30, "created_at": t, "channel": {"slug": "a"}},
        {"id": "c3", "title": "old", "view_count": 9000, "duration": 30, "created_at": "2020-01-01T00:00:00Z", "channel": {"slug": "a"}}]})
    k = parse_kick(kj, 36, 300, 5)
    assert [x["id"] for x in k] == ["k:c1"] and k[0]["per_h"] == 1000 and k[0]["page"] == "https://kick.com/a/clips/c1", k
    yx = (f'<feed><entry><yt:videoId>V1</yt:videoId><title>T &amp; t</title><link href="https://www.youtube.com/shorts/V1"/>'
          f'<published>{t}</published><media:statistics views="1000"/></entry></feed>')
    y = parse_youtube(yx, "ch", "gaming", 72)
    assert y[0]["per_h"] == 200 and "/shorts/V1" in y[0]["page"] and y[0]["title"] == "T & t", y
    t2 = (now() - D.timedelta(hours=3)).strftime("%a, %d %b %Y %H:%M:%S +0000")
    nx = (f'<rss><item><title><![CDATA[GTA 6 Map Size Revealed &amp; It&#8217;s Huge]]></title><link>https://a.example/x</link><pubDate>{t2}</pubDate></item>'
          f'<item><title>Stargate news</title><link>https://a.example/y</link><pubDate>{t2}</pubDate></item>'
          f'<item><title>Old GTA 6 story</title><link>https://a.example/z</link><pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate></item></rss>')
    n = parse_news(nx, "A", ["gta", "rockstar"], 30)
    assert len(n) == 1 and n[0]["title"] == "GTA 6 Map Size Revealed & It\u2019s Huge" and n[0]["page"] == "https://a.example/x" and 2.9 <= n[0]["age_h"] <= 3.1, n
    ax = f'<feed><entry><title>Rockstar reveals GTA 6 map size</title><link rel="alternate" href="https://b.example/q"/><updated>{t}</updated></entry></feed>'
    n2 = parse_news(ax, "B", ["gta"], 30)
    assert n2 and n2[0]["page"] == "https://b.example/q" and key_words(n[0]["title"]) & key_words(n2[0]["title"]) >= {"map", "size"}, n2
    md = render(r + [dict(k[0], watched=True)] + y + [dict(n[0], sites=["A", "B"])], ["kick x: HTTP 403"], {"r:1abc": "x"})
    assert "[2 Quellen] GTA 6 Map Size" in md, md
    assert "NEW W a" in md and "1. Streamer" in md and "Nicht erreichbar" in md, md
    print("selftest ok")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        selftest()
    elif len(sys.argv) > 2 and sys.argv[1] == "run":
        sys.exit(run(sys.argv[2]))
    else:
        print(__doc__)
