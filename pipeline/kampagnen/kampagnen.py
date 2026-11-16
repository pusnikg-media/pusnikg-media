#!/usr/bin/env python3
"""Kampagnen-Radar: which paid clipping campaigns on Content Rewards fit our two accounts right now.

Reads the public discover page (no login, no API key, no Claude quota, our accounts are never involved), then the public
page of each campaign (brief, platforms, rate, min payout, budget). Keeps a history, so it knows what is NEW, how many
dollars a campaign paid out in the last 24 h (= clips really get approved) and when a campaign we joined runs dry.

Writes campaigns/latest.md (short, for agents and Steven), campaigns/latest.json (everything), campaigns/state.json.
Config: plan/kampagnen.json.

  python3 pipeline/kampagnen/kampagnen.py run .        collect and write
  python3 pipeline/kampagnen/kampagnen.py selftest     parser checks, no network
"""
import datetime as D
import html
import json
import os
import re
import sys
import time
import urllib.request

BASE = "https://contentrewards.com"
LIST = BASE + "/c/discover/clipping"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
PLATFORMS = ("tiktok", "instagram", "youtube", "x", "facebook", "twitch", "kick", "snapchat")
DEFAULTS = {
    "accounts": {
        "Pusnik G": {"categories": ["gaming", "gta", "esports", "video game"], "weak_categories": [],
                     "words": ["call of duty", "warzone", "modern warfare", "mw4", "black ops", "gta", "grand theft auto", "fortnite", "roblox",
                               "minecraft", "valorant", "apex legends", "esports", "gameplay", "video game", "faze", "gaming", "speedrun"]},
        "Pusnik IRL": {"categories": ["streamer", "twitch", "kick", "youtuber", "content creator", "celebrity", "personal brand", "podcast",
                                      "comedy", "fan page", "vlog"], "weak_categories": ["entertainment", "lifestyle", "sports"],
                       "words": ["stream", "streamer", "irl", "vlog", "podcast", "twitch", "youtuber", "his content", "her content",
                                 "'s content", "reaction", "interview", "host", "creator", "episode"]},
    },
    "block_words": ["casino", "stake", "gambl", "betting", "sportsbook", "slots", "roulette", "blackjack", "poker", "wager",
                    "rainbet", "roobet", "shuffle.com", "bc.game", "onlyfans", "18+", "nsfw", "forex signal", "crypto presale"],
    "skip_words": ["music video", "song", "album", "single out now", "artist", "sound on tiktok", "ugc"],
    "language_words": ["spanish", "español", "portugu", "french", "français", "german", "deutsch", "arabic", "hindi", "turkish",
                       "italian", "brasil", "latam", "por cada", "clips de ", "clips do ", "klage", "hablando", "en français", "latvia"],
    "min_rate": 0.5, "min_left": 300, "max_views_needed": 10000, "our_platforms": ["tiktok", "instagram", "youtube"],
    "joined": [], "ignore": [], "max_details": 30, "detail_days": 3, "top": 8,
}


def now():
    return D.datetime.now(D.timezone.utc)


def get(url, tries=3):
    err = None
    for i in range(tries):
        try:
            try:
                from curl_cffi import requests as cr
                r = cr.get(url, impersonate="chrome", timeout=30, headers={"Accept-Language": "en-US,en;q=0.8"})
                code, text = r.status_code, r.text
            except ImportError:
                rq = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.8"})
                with urllib.request.urlopen(rq, timeout=30) as r:
                    code, text = r.status, r.read().decode("utf-8", "replace")
            if code == 200 and len(text) > 2000:
                return text
            err = f"HTTP {code}"
            if code == 404:
                break
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {str(e)[:80]}"
        time.sleep(4 * (i + 1))
    raise RuntimeError(err or "empty")


def money(s):
    """'$1.6K' -> 1600.0, '$8,500' -> 8500.0, '$2.50' -> 2.5; None when there is no number."""
    m = re.search(r"([\d][\d,]*\.?\d*)\s*([KkMm]?)", s or "")
    if not m:
        return None
    return float(m.group(1).replace(",", "")) * {"k": 1e3, "m": 1e6}.get(m.group(2).lower(), 1)


def tokens(h):
    """HTML -> visible text pieces. Images become [img:alt], aria-labels are kept (platform icons carry no text)."""
    h = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S)
    h = re.sub(r'<(?:span|div|svg|img)[^>]*aria-label="([^"]*)"[^>]*>', r"|[a:\1]|", h)
    h = re.sub(r"<svg.*?</svg>", "", h, flags=re.S)
    h = re.sub(r'<img[^>]*alt="([^"]*)"[^>]*>', r"|[img:\1]|", h)
    h = html.unescape(re.sub(r"<[^>]+>", "|", h))
    return [t.strip() for t in re.sub(r"\s+", " ", h).split("|") if t.strip()]


# ---------- discover list ----------
def parse_list(page):
    out = {}
    for part in re.split(r'(?=<a[^>]+href="/c/campaigns/)', page)[1:]:
        m = re.match(r'<a[^>]+href="/c/campaigns/([0-9a-f-]{36})', part)
        if not m or m.group(1) in out:
            continue
        cid = m.group(1)
        head = part[:part.find(">") + 1]
        body = part[:part.find("</a>")]
        tk = tokens(body[len(head):])
        title = html.unescape((re.search(r'aria-label="Preview ([^"]*)"', head) or [0, ""])[1]).strip()
        plat = [p for p in PLATFORMS if any(t.lower() == f"[a:{p}]" for t in tk)]
        text = [t for t in tk if not t.startswith("[")]
        c = {"id": cid, "url": f"{BASE}/c/campaigns/{cid}", "title": title, "brand": text[0] if text else "",
             "verified": "[img:Verified]" in tk, "platforms": plat, "pool": False, "rate": None, "rate_max": None,
             "spent": None, "budget": None, "clippers": None}
        # age: the token after the "·"
        if "·" in text:
            c["age"] = text[text.index("·") + 1] if text.index("·") + 1 < len(text) else ""
        tail = text[text.index("·") + 2:] if "·" in text else text
        for i, t in enumerate(tail):
            if t == "/1K" and i:
                r = re.findall(r"\$([\d.,]+)", tail[i - 1])
                if r:
                    c["rate"], c["rate_max"] = float(r[0].replace(",", "")), float(r[-1].replace(",", ""))
            elif t == "/" and 0 < i < len(tail) - 1 and tail[i - 1].startswith("$") and tail[i + 1].startswith("$"):
                c["spent"], c["budget"] = money(tail[i - 1]), money(tail[i + 1])
            elif re.fullmatch(r"\$[\d.,]+[KkMm]? pool", t):
                c["pool"], c["budget"] = True, money(t)
            elif re.fullmatch(r"[\d.,]+[KkMm]?", t) and i and not (i + 1 < len(tail) and tail[i + 1] == "/1K"):
                c["clippers"] = int(money(t))  # the last bare number on the card = people clipping
        if not title:
            c["title"] = " ".join(x for x in tail if not x.startswith("$") and x not in ("/", "/1K") and not re.fullmatch(r"[\d.,]+[KkMm]?", x))[:120]
        out[cid] = c
    return list(out.values())


# ---------- campaign page ----------
def parse_detail(page):
    d = {"brief": [], "platform_rates": {}}
    m = re.search(r'"@type":"Service","description":"((?:[^"\\]|\\.)*)"', page)
    if m:
        try:
            d["description"] = json.loads('"' + m.group(1) + '"')
        except ValueError:
            d["description"] = m.group(1)
    else:
        m = re.search(r'<meta name="description" content="([^"]*)"', page)
        d["description"] = html.unescape(m.group(1)) if m else ""
    tk = tokens(page[page.find("<body"):])
    try:
        tk = tk[len(tk) - 1 - tk[::-1].index("Back"):]  # the nav is rendered several times; start at the last "Back"
    except ValueError:
        pass
    low = [t.lower() for t in tk]
    d["status"] = next((t for t in tk if re.match(r"(Accepting|Not accepting|Paused|Ended|Closed|Budget|Completed|Full)", t)), "")
    d["launched"] = next((t[9:] for t in tk if t.startswith("Launched ")), "")
    plat = [p for p in PLATFORMS if f"[img:{p}]" in low]
    d["platforms"] = plat
    if plat:  # category = first plain token after the last platform icon
        last = max(i for i, t in enumerate(low) if t in [f"[img:{p}]" for p in plat])
        d["category"] = next((t for t in tk[last + 1:last + 4] if not t.startswith("[")), "")
    for i, t in enumerate(tk):
        if t == "Per 1K views" and i and i + 1 < len(tk):
            name = tk[i - 1].lower(); k0 = i + 2 if tk[i + 1] in ("Up to", "From") and i + 2 < len(tk) else i + 1  # "Up to $2.00" = by country
            pr = {"rate": money(tk[k0]) if "$" in tk[k0] else None}
            if k0 != i + 1: pr["up_to"] = True
            for j in range(k0 + 1, min(k0 + 6, len(tk) - 1)):
                if tk[j] == "Min payout": pr["min_payout"] = money(tk[j + 1])
                if tk[j] == "Max payout": pr["max_payout"] = money(tk[j + 1])
            d["platform_rates"][name] = pr
        elif t == "Budget" and i + 4 < len(tk) and tk[i + 1] == "$":
            d["spent"], d["budget"] = money(tk[i + 2]), money(tk[i + 4])
        elif t == "Pool" and i + 1 < len(tk) and tk[i + 1].startswith("$"):
            d["pool"], d["budget"] = True, money(tk[i + 1])
        elif t == "Pay by viewer country":
            part = []
            for x in tk[i + 1:i + 10]:
                if x in ("Budget", "Pool", "Reference materials", "Brief"): break
                if not x.startswith("["): part.append(x)
            d["by_country"] = " ".join(part)[:160]
        elif t == "Reference materials" and i + 1 < len(tk):
            d["files"] = int(money(tk[i + 1]) or 0)
        elif t == "Content requirements" and i + 1 < len(tk):
            d["hidden_rules"] = int(money(tk[i + 1]) or 0)
        elif t == "views" and i and re.fullmatch(r"[\d.,]+[KkMm]?", tk[i - 1]):
            d["views"] = int(money(tk[i - 1]))
    if "Brief" in tk:
        i = tk.index("Brief") + 1
        while i < len(tk) and tk[i] not in ("Top clippers", "Views", "Join Campaign", "Full rules in the guidelines") and len(d["brief"]) < 20:
            if not tk[i].startswith("["): d["brief"].append(tk[i])
            i += 1
    return d


# ---------- judging ----------
def judge(c, cfg):
    """Adds account, ok, flags (why not / watch out), score. Rules only - an agent still reads the brief before joining."""
    text = " ".join([c.get("title", ""), c.get("brand", ""), c.get("description", ""), " ".join(c.get("brief", []))]).lower()
    cat = (c.get("category") or "").lower(); flags, no = [], []
    hit = lambda words: next((w for w in words if re.search(r"(?<![a-z])" + re.escape(w), text)), None)  # noqa: E731
    w = hit(cfg["block_words"])
    if w: no.append(f"gesperrt: {w}")
    w = hit(cfg["language_words"])
    if w: no.append(f"nicht englisch: {w}")
    w = hit(cfg["skip_words"])
    if w and cat in ("music", ""): no.append(f"Musik/UGC: {w}")
    if cat == "music": no.append("Musik")
    title = (c.get("title", "") + " " + c.get("brand", "")).lower(); acc, best = None, 0
    for name, a in cfg["accounts"].items():  # category 4, weak category 1, a key word in the title 3, key words in the text up to 3
        s = (4 if cat and any(k_ in cat for k_ in a["categories"]) else 1 if any(k_ in cat for k_ in a.get("weak_categories", [])) else 0)
        s += (3 if any(k_ in title for k_ in a["words"]) else 0) + min(3, sum(1 for k_ in a["words"] if k_ in text))
        if s > best: acc, best = name, s
    if best < 3: acc = "Sonstige"  # fine campaign, but neither gaming nor a person in front of the camera
    plats = [p for p in (c.get("platforms") or []) if p in cfg["our_platforms"]]
    if c.get("platforms") and not plats: no.append("keine unserer Plattformen")
    status = (c.get("status") or "").lower()
    if status and "accepting" not in status: no.append(f"Status: {c['status']}")
    if status.startswith("not accepting"): pass
    rate = c.get("rate"); left = None
    if c.get("budget") is not None and not c.get("pool"): left = c["budget"] - (c.get("spent") or 0)
    c["left"] = left
    if c.get("pool"): flags.append("Pool (Anteil nach Views, unsicher für kleine Konten)")
    elif rate is not None and rate < cfg["min_rate"]: no.append(f"Rate {rate:g} $ zu niedrig")
    if left is not None and left < cfg["min_left"]: no.append(f"nur noch {left:.0f} $ im Topf")
    pr = [v for k, v in (c.get("platform_rates") or {}).items() if k in cfg["our_platforms"] and v.get("rate")]
    need = min((v["min_payout"] / v["rate"] * 1000 for v in pr if v.get("min_payout")), default=None)
    c["views_needed"] = int(need) if need else None
    if need and need > cfg["max_views_needed"]: flags.append(f"erste Auszahlung erst ab {int(need):,} Views".replace(",", "."))
    m = re.search(r"(\d{2})\s*%\+?\s*(?:us|usa|u\.s\.|tier[- ]?1|english|american)\b[^.|]{0,30}(?:audience|viewers|views)|audience[^.|]{0,40}?(\d{2})\s*%", text)
    if m: flags.append(f"Publikum: {m.group(1) or m.group(2)} % USA/Tier 1 verlangt")
    m = re.search(r"(?:min(?:imum)?\.?|at least)\s*([\d.,]+[km]?)\s*followers", text)
    if m: flags.append(f"Mindest-Follower: {m.group(1)}")
    if c.get("by_country"): flags.append(f"Bezahlung hängt vom Zuschauerland ab ({c['by_country'][:90]})")
    if re.search(r"pre-?approv|application requires|apply (?:first|to join)", text): flags.append("Bewerbung/Vorab-Freigabe nötig")
    if re.search(r"logo|watermark", text): flags.append("Logo/Wasserzeichen Pflicht")
    if re.search(r"#ad\b|paid partnership", text): flags.append("#Ad/Offenlegung Pflicht")
    if c.get("files"): flags.append(f"Material liegt bei ({c['files']} Dateien)")
    elif c.get("files") == 0 or "files" not in c: flags.append("kein Material hinterlegt – Quelle selbst besorgen")
    if c.get("hidden_rules"): flags.append(f"{c['hidden_rules']} Regel(n) erst nach Beitritt sichtbar")
    score = 0.0
    if not c.get("pool") and rate: score += min(rate, 4) * 2
    if left: score += min(left / 2000, 3)
    if c.get("paid_24h"): score += min(c["paid_24h"] / 100, 3)  # money really flows
    if c.get("files"): score += 2
    if c.get("verified"): score += 1
    if c.get("clippers") and left: score += min(left / max(c["clippers"], 1) / 50, 2)  # budget per clipper
    if need and need > cfg["max_views_needed"]: score -= 2
    if any(f.startswith("Publikum") for f in flags): score -= 2
    if c.get("pool"): score -= 1
    c.update(account=acc, ok=not no, why_not=no, flags=flags, score=round(score, 1))
    return c


def k(v):
    if v is None: return "?"
    return f"{v / 1000:.1f}K".replace(".0K", "K") if v >= 1000 else f"{v:.0f}"


def line(c, new=False):
    rate = f"{k(c.get('budget'))} $ Pool" if c.get("pool") else (f"{c['rate']:g}" + (f"–{c['rate_max']:g}" if c.get("rate_max") and c["rate_max"] != c["rate"] else "") + " $/1K" if c.get("rate") else "Rate ?")
    left = "" if c.get("left") is None else f", {k(c['left'])} $ frei"
    paid = f", {k(c['paid_24h'])} $ in 24 h ausgezahlt" if c.get("paid_24h") else ""
    need = f", Auszahlung ab {k(c['views_needed'])} Views" if c.get("views_needed") else ""
    plat = "/".join({"tiktok": "TT", "instagram": "IG", "youtube": "YT", "x": "X"}.get(p, p) for p in c.get("platforms", []))
    s = (f"- {'NEW ' if new else ''}**{c['title'][:70]}** ({c.get('brand', '')}{', verifiziert' if c.get('verified') else ''}) – {rate}{left}{paid}{need}, "
         f"{c.get('clippers') if c.get('clippers') is not None else '?'} Clipper, {plat or '?'}, {c.get('category') or '?'}, seit {c.get('launched') or c.get('age') or '?'}")
    if c.get("flags"): s += "\n  Achtung: " + "; ".join(c["flags"])
    if c.get("description"): s += "\n  " + re.sub(r"\s+", " ", c["description"])[:230]
    return s + f"\n  {c['url']}"


def render(items, state, cfg, errors, new_ids):
    L = [f"# Kampagnen-Radar – {now().strftime('%d.%m.%Y %H:%M')} UTC", "",
         "Automatisch von Content Rewards (öffentliche Seiten, ohne Login). Vorauswahl nach festen Regeln – vor dem Beitritt das Briefing lesen. "
         "Beitreten kann nur Steven. NEW = seit dem letzten Lauf neu.", ""]
    mine = [c for c in items if c.get("joined")]
    if mine:
        L += ["## Unsere Kampagnen", ""]
        for c in mine:
            warn = ""
            if c.get("left") is not None and c.get("paid_24h") and c["left"] / c["paid_24h"] < 3: warn = " ⚠ Topf reicht bei diesem Tempo keine 3 Tage mehr"
            if c.get("left") is not None and c["left"] < cfg["min_left"]: warn = " ⚠ Topf fast leer – nichts Neues mehr dafür schneiden"
            if c.get("gone"): warn = " ⚠ steht nicht mehr in der Liste (beendet oder voll?)"
            L += [f"- **{c['title'][:70]}** ({c['joined']}): " + (f"{k(c.get('budget'))} $ Pool" if c.get("pool") else f"{k(c.get('left'))} $ von {k(c.get('budget'))} $ frei")
                  + (f", {k(c['paid_24h'])} $ in 24 h ausgezahlt" if c.get("paid_24h") else "") + f", {c.get('clippers', '?')} Clipper{warn}"]
        L += [""]
    for acc in cfg["accounts"]:
        good = sorted((c for c in items if c["ok"] and c["account"] == acc and not c.get("joined")), key=lambda c: -c["score"])
        L += [f"## {acc} – beste offene Kampagnen ({len(good)} passen)", ""]
        cpm = [c for c in good if not c.get("pool")]; pools = [c for c in good if c.get("pool")]
        L += [line(c, c["id"] in new_ids) for c in cpm[:cfg["top"]]] or ["- nichts Passendes"]
        if pools:
            L += ["- Pools (fester Topf, wird nach Views aufgeteilt – für kleine Konten unsicher): " + "; ".join(
                f"{'NEW ' if c['id'] in new_ids else ''}{c['title'][:45]} ({k(c.get('budget'))} $, {c.get('clippers', '?')} Clipper)" for c in sorted(pools, key=lambda c: -(c.get("budget") or 0))[:5])]
        L += [""]
    other = sorted((c for c in items if c["ok"] and c["account"] == "Sonstige" and not c.get("joined")), key=lambda c: -c["score"])
    if other:
        L += [f"## Sonstige (weder Gaming noch Personen-Clips, {len(other)} offen) – nur falls ein drittes Konto dazukommt", ""]
        L += [f"- {'NEW ' if c['id'] in new_ids else ''}{c['title'][:60]} ({c.get('brand', '')}) – {c['rate']:g} $/1K, {k(c.get('left'))} $ frei, {c.get('category') or '?'}" if c.get("rate")
              else f"- {c['title'][:60]} ({c.get('brand', '')}) – Pool {k(c.get('budget'))} $, {c.get('category') or '?'}" for c in other[:6]] + [""]
    rest = [c for c in items if c["id"] in new_ids and not c["ok"]]
    if rest:
        L += ["## Neu, aber aussortiert", ""] + [f"- {c['title'][:60]} ({c.get('brand', '')}): {'; '.join(c['why_not'])}" for c in rest[:15]] + [""]
    if errors:
        L += ["## Probleme", ""] + [f"- {e}" for e in errors[:8]] + [""]
    return "\n".join(L)


def run(root):
    cfg = dict(DEFAULTS)
    p = os.path.join(root, "plan", "kampagnen.json")
    if os.path.exists(p):
        cfg.update({k_: v for k_, v in json.load(open(p, encoding="utf-8")).items() if k_ in DEFAULTS})
    out = os.path.join(root, "campaigns"); os.makedirs(out, exist_ok=True)
    sp = os.path.join(out, "state.json")
    state = json.load(open(sp, encoding="utf-8")) if os.path.exists(sp) else {}
    camps, errors, stamp = state.setdefault("campaigns", {}), [], now().isoformat(timespec="seconds")
    try:
        listed = parse_list(get(LIST))
    except Exception as e:  # noqa: BLE001
        print("NO DATA:", e); return 1
    if len(listed) < 5:
        print("NO DATA: only", len(listed), "cards - page layout changed?"); return 1
    first_run = not camps; new_ids = set()
    for c in listed:
        old = camps.get(c["id"])
        if old is None:
            old = camps[c["id"]] = {"first": stamp, "hist": []}
            if not first_run: new_ids.add(c["id"])
        old.update({k_: v for k_, v in c.items() if v is not None and v != [] or k_ not in old}); old["last"] = stamp
        if c.get("spent") is not None:
            old["hist"] = (old["hist"] + [[stamp, c["spent"]]])[-40:]
    # details: new ones first, then the stalest; joined campaigns always
    joined = lambda c: next((j.get("account", "ja") for j in cfg["joined"] if j.get("match", "\0").lower() in (c.get("title", "") + " " + c.get("brand", "") + " " + c.get("id", "")).lower()), None)  # noqa: E731
    live = [camps[c["id"]] for c in listed]
    limit = (now() - D.timedelta(days=float(cfg["detail_days"]))).isoformat(timespec="seconds")
    todo = sorted((c for c in live if c.get("detail_at", "") < limit or joined(c)), key=lambda c: (not joined(c), c.get("detail_at", "")))
    for c in todo[:110 if first_run else int(cfg["max_details"])]:  # very first run reads every campaign page once
        try:
            c.update({k_: v for k_, v in parse_detail(get(c["url"])).items() if v not in (None, "", [], {}) or k_ not in c}); c["detail_at"] = stamp
        except Exception as e:  # noqa: BLE001
            errors.append(f"{c.get('title', c['id'])[:40]}: {e}")
        time.sleep(1.2)
    items = []
    ids = {c["id"] for c in listed}
    for cid, c in camps.items():
        j = joined(c)
        if cid not in ids and not j: continue
        h = c.get("hist") or []
        day = (now() - D.timedelta(hours=26)).isoformat(timespec="seconds")
        base = next((v for t, v in h if t >= day), None)
        c["paid_24h"] = round(h[-1][1] - base, 2) if base is not None and len(h) > 1 and h[-1][1] > base else 0
        x = judge(dict(c), cfg); x["joined"] = j; x["gone"] = cid not in ids
        if cid in cfg["ignore"] or any(i.lower() in (x["title"] + x.get("brand", "")).lower() for i in cfg["ignore"]): x["ok"] = False; x["why_not"].append("ignoriert")
        items.append({k_: v for k_, v in x.items() if k_ != "hist"})
    old_limit = (now() - D.timedelta(days=45)).isoformat(timespec="seconds")
    state["campaigns"] = {k_: v for k_, v in camps.items() if v.get("last", "") >= old_limit}
    open(os.path.join(out, "latest.md"), "w", encoding="utf-8").write(render(items, state, cfg, errors, new_ids))
    json.dump({"at": stamp, "errors": errors, "new": sorted(new_ids), "items": sorted(items, key=lambda c: -c["score"])},
              open(os.path.join(out, "latest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(state, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"OK {len(listed)} listed, {len(new_ids)} new, {sum(1 for c in items if c['ok'])} fit, {len(errors)} errors")
    return 0


def selftest():
    card = ('<a aria-label="Preview Big &amp; Loud Stream" class="x" href="/c/campaigns/11111111-2222-3333-4444-555555555555"><div><img alt="" src="t.webp"/>'
            '<span>Reach</span><img alt="Verified" src="v.svg"/><span>·</span><span>2w</span><span aria-label="TikTok"></span><span aria-label="YouTube"></span>'
            '<p>Big &amp; Loud Stream</p><span>$1.6K</span><span>/</span><span>$2K</span><img alt=""/><span>335</span><span>$2.50–$3</span><span>/1K</span></div></a>'
            '<a aria-label="Preview Pool Thing" href="/c/campaigns/aaaaaaaa-2222-3333-4444-555555555555"><span>Brand</span><span>·</span><span>3d</span><p>Pool Thing</p>'
            '<img alt=""/><span>2.4K</span><span>$9K pool</span></a>')
    a, b = parse_list(card)
    assert a["title"] == "Big & Loud Stream" and a["brand"] == "Reach" and a["verified"] and a["platforms"] == ["tiktok", "youtube"], a
    assert (a["spent"], a["budget"], a["clippers"], a["rate"], a["rate_max"], a["age"]) == (1600.0, 2000.0, 335, 2.5, 3.0, "2w"), a
    assert b["pool"] and b["budget"] == 9000.0 and b["clippers"] == 2400 and b["rate"] is None, b
    page = ('<html><head><script type="application/ld+json">{"@type":"Service","description":"Clip the \\"official\\" stream. 60%+ US audience.","name":"x"}</script></head>'
            '<body><a>Back</a><b>Join Campaign</b><span>Accepting clips</span><span>Launched 4 days ago</span><img alt="instagram"/><img alt="tiktok"/>'
            '<span>Gaming</span><img alt=""/><span>15</span><span>CPM</span><img alt=""/><span>TikTok</span><span>Per 1K views</span><span>$1.00</span><span>Min payout</span>'
            '<span>$10.00</span><span>Max payout</span><span>$350.00</span><span>Budget</span><span>$</span><span>46</span><span>/ </span><span>$8,500</span>'
            '<span>Reference materials</span><span>2 files</span><span>Brief</span><li>Keep the logo on screen</li><li>Vertical 9:16</li><span>Top clippers</span>'
            '<span>57K</span><span>views</span></body></html>')
    d = parse_detail(page)
    assert d["description"].startswith('Clip the "official"') and d["status"] == "Accepting clips" and d["launched"] == "4 days ago", d
    assert d["platforms"] == ["tiktok", "instagram"] and d["category"] == "Gaming" and d["platform_rates"]["tiktok"] == {"rate": 1.0, "min_payout": 10.0, "max_payout": 350.0}, d
    assert (d["spent"], d["budget"], d["files"], d["views"]) == (46.0, 8500.0, 2, 57000) and d["brief"] == ["Keep the logo on screen", "Vertical 9:16"], d
    d2 = parse_detail(page.replace("<span>$1.00</span><span>Min payout</span>", "<span>Up to</span><span>$2.00</span><span>Min payout</span>")
                      .replace("<span>Budget</span>", "<span>Pay by viewer country</span><span>India</span><span>Not paid</span><span>Budget</span>"))
    assert d2["platform_rates"]["tiktok"] == {"rate": 2.0, "up_to": True, "min_payout": 10.0, "max_payout": 350.0} and d2["by_country"] == "India Not paid" and d2["budget"] == 8500.0, d2
    c = judge(dict(a, **d, title="FaZe Tournament", rate=1.0), DEFAULTS)
    assert c["account"] == "Pusnik G" and c["ok"] and c["views_needed"] == 10000 and any("Publikum: 60" in f for f in c["flags"]) and any("Logo" in f for f in c["flags"]), c
    g = judge(dict(a, description="Clip our Stake casino stream", category="Entertainment"), DEFAULTS)
    assert not g["ok"] and "gesperrt" in g["why_not"][0], g
    md = render([dict(c, joined=None), dict(g, joined="Pusnik IRL", gone=False)], {}, DEFAULTS, ["x: HTTP 500"], {c["id"]})
    assert "NEW **FaZe Tournament**" in md and "Unsere Kampagnen" in md and "Probleme" in md, md
    print("selftest ok")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        selftest()
    elif len(sys.argv) > 2 and sys.argv[1] == "run":
        sys.exit(run(sys.argv[2]))
    else:
        print(__doc__)
