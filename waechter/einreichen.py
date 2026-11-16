#!/usr/bin/env python3
"""Einreich-Issue (0 Credits): pro Berlin-Tag ein GitHub-Issue "Einreichen" mit einer Checkbox pro Kampagnen-Clip.

Steven hakt in der GitHub-App ab (ein Tipp pro Clip). Dieses Skript
  sync    liest die Haken aus den Issues  -> plan/eingereicht.json (`slots`, `eingereicht`; Haken sind monoton: nie zurück)
  update  legt/aktualisiert die Tages-Issues aus plan/postplan.json (Plan) + stats/latest.json (Live-Links, unplanmäßige Posts)
          und schließt ein Issue, wenn alles abgehakt ist (öffnet es wieder, wenn eine neue Zeile dazukommt).

  python3 waechter/einreichen.py --root . [--mode sync|update|both] [--dry] [--now 2026-11-16T14:00:00Z]

Schlüssel einer Zeile: `slot|<konto>|<kampagne>|<datum>|<HH:MM>` (Plan) oder `post|<plattform>|<id>` (Post ohne Plan).
Der Wächter ordnet einen Live-Post dem nächsten Slot (±14 Min) zu; ist der Slot abgehakt, gilt der Post als eingereicht.
Sicherheit: nur Issues des Actions-Bots mit unserer Markierung werden gelesen; der Issue-Text wird nie als Befehl benutzt."""
import argparse, datetime as dt, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import waechter as W

UTC, BER = W.UTC, W.BER
LABEL = "einreichen"
DAY_RE = re.compile(r"<!-- einreichen-day: (\d{4}-\d{2}-\d{2}) -->")
LINE_RE = re.compile(r"^- \[([ xX])\] .*?<!-- k:(.+?) -->\s*$", re.M)
TOL_MIN = 14                       # TJR postet 09:00 und 09:30 auf einem Konto: ±14 Min trennt sie sicher
FRIST_MIN = 30                     # Content Rewards: einreichen binnen 30 Min nach Veröffentlichung
PLAT = {"tiktok": "TikTok", "youtube": "YouTube", "instagram": "Instagram"}
WTAG = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def slot_key(konto, kampagne, datum, zeit): return f"slot|{konto}|{kampagne}|{datum}|{zeit}"
def post_key(p): return f"post|{p['platform']}|{p['id']}"
def slot_time(datum, zeit): return W.at_berlin(datum, zeit).astimezone(UTC)


def stats_name(cfg, kampagne):
    """Name der Kampagne in stats/latest.json (waechter.json kampagnen[].stats), sonst der Name selbst."""
    for k in cfg.get("kampagnen", []):
        if k["name"] == kampagne: return k["stats"]
    return kampagne


def match_slot(post, slots, cfg):
    """Nächster Plan-Slot desselben Kontos/derselben Kampagne innerhalb ±TOL_MIN, sonst None."""
    t = W.parse(post.get("published"))
    if not t or not post.get("campaign"): return None
    best = None
    for s in slots:
        if s["konto"] != post.get("account") or stats_name(cfg, s["kampagne"]) != post["campaign"]: continue
        d = abs((t - slot_time(s["datum"], s["zeit"])).total_seconds()) / 60
        if d <= TOL_MIN and (best is None or d < best[0]): best = (d, s)
    return best[1] if best else None


def load_slots(root):
    j = W.jl(os.path.join(root, "plan", "postplan.json"), {}) or {}
    return [s for s in j.get("slots", []) if s.get("datum") and s.get("zeit")]


def build_lines(root, cfg, day, stats):
    """Zeilen für einen Tag: [{key, zeit, text}] sortiert. Text ohne Haken und ohne Markierung."""
    slots, posts = load_slots(root), [p for p in (stats or {}).get("posts", []) if p.get("campaign")]
    lines, claimed = [], set()
    for s in sorted((s for s in slots if s["datum"] == day), key=lambda s: s["zeit"]):
        live = {}
        for p in posts:
            if match_slot(p, [s], cfg) is s and p["platform"] not in live: live[p["platform"]] = p; claimed.add((p["platform"], p["id"]))
        links = []
        for plat in s.get("plattformen", ["tiktok", "youtube", "instagram"]):
            if plat in live: links.append(f"{PLAT.get(plat, plat)} {live[plat]['url']}")
            elif plat == "instagram": links.append("Instagram: Link aus der App")
            else: links.append(f"{PLAT.get(plat, plat)}: Link folgt nach dem Post")
        frist = (slot_time(day, s["zeit"]) + dt.timedelta(minutes=FRIST_MIN)).astimezone(BER).strftime("%H:%M")
        lines.append({"key": slot_key(s["konto"], s["kampagne"], day, s["zeit"]), "zeit": s["zeit"],
                      "text": f"**{s['zeit']}** {s['kampagne']} · {s['konto']} · „{s.get('titel', s.get('clip', ''))}“ · Frist {frist} · " + " · ".join(links)})
    for p in sorted(posts, key=lambda p: p.get("published") or ""):
        t = W.parse(p.get("published"))
        if not t or W.local(t).date().isoformat() != day or day < cfg["seit"] or (p["platform"], p["id"]) in claimed or match_slot(p, slots, cfg): continue
        hm = W.local(t).strftime("%H:%M"); frist = (t + dt.timedelta(minutes=FRIST_MIN)).astimezone(BER).strftime("%H:%M")
        lines.append({"key": post_key(p), "zeit": hm, "text": f"**{hm}** {p['campaign']} · {p['account']} · {PLAT.get(p['platform'], p['platform'])} · „{p['title'][:45]}“ · Frist {frist} · {p['url']}"})
    return sorted(lines, key=lambda l: (l["zeit"], l["key"]))


def render_body(day, lines, ticked):
    d = dt.date.fromisoformat(day)
    L = [f"<!-- einreichen-day: {day} -->",
         f"**Einreichen {WTAG[d.weekday()]} {d:%d.%m.}** – bei Content Rewards einreichen, danach den Haken setzen (ein Tipp pro Clip, gilt für alle Plattformen des Clips). Frist: 30 Min nach dem Post.", ""]
    L += [f"- [{'x' if l['key'] in ticked else ' '}] {l['text']} <!-- k:{l['key']} -->" for l in lines]
    L += ["", "_Automatisch (Aktion `einreichen`). Schließt sich selbst, wenn alles abgehakt ist._"]
    return "\n".join(L)


def parse_body(body):
    """{key: abgehakt?} aus einem Issue-Text."""
    return {m.group(2): m.group(1) in "xX" for m in LINE_RE.finditer(body or "")}


def file_ticks(root):
    e = W.jl(os.path.join(root, "plan", "eingereicht.json"), {}) or {}
    t = {f"slot|{k}" for k in e.get("slots", [])}
    t |= {f"post|{k}" for k in e.get("posts", [])}
    return t


def is_ours(issue, cfg):
    authors = cfg.get("einreichen_autoren", ["github-actions[bot]"])
    return "pull_request" not in issue and (issue.get("user") or {}).get("login") in authors and DAY_RE.search(issue.get("body") or "")


def issue_ticks(issues, cfg):
    """Haken aus allen unseren Issues. Ein GESCHLOSSENES Issue gilt als komplett abgehakt (Fallback, falls Steven nur schließt)."""
    out = set()
    for i in issues:
        if not is_ours(i, cfg): continue
        for k, v in parse_body(i.get("body")).items():
            if v or i.get("state") == "closed": out.add(k)
    return out


def write_file(root, ticks):
    """Haken in plan/eingereicht.json eintragen (nur hinzufügen). Rückgabe: geändert?"""
    path = os.path.join(root, "plan", "eingereicht.json"); e = W.jl(path, {}) or {}
    slots, posts = set(e.get("slots", [])), set(e.get("posts", []))
    new_s = {k[5:] for k in ticks if k.startswith("slot|")}; new_p = {k[5:] for k in ticks if k.startswith("post|")}   # 'post|<plattform>|<id>' -> '<plattform>|<id>'
    if new_s <= slots and new_p <= posts: return False
    e["slots"] = sorted(slots | new_s); e["posts"] = sorted(posts | new_p)
    json.dump(e, open(path, "w"), ensure_ascii=False, indent=1); open(path, "a").write("\n")
    return True


def list_issues(gh):
    return gh.call("GET", f"/issues?labels={LABEL}&state=all&per_page=60&sort=created&direction=desc")


def ensure_label(gh):
    try: gh.call("POST", "/labels", {"name": LABEL, "color": "0e8a16", "description": "Kampagnen-Clips bei Content Rewards einreichen"})
    except Exception as e:
        if getattr(e, "code", None) != 422: raise


def update_day(gh, root, cfg, day, stats, ticked, issues, now):
    lines = build_lines(root, cfg, day, stats)
    cur = next((i for i in issues if is_ours(i, cfg) and DAY_RE.search(i["body"]).group(1) == day), None)
    if not lines: return None
    title = f"Einreichen {WTAG[dt.date.fromisoformat(day).weekday()]} {dt.date.fromisoformat(day):%d.%m.}"
    if cur is None:
        body = render_body(day, lines, ticked)
        data = {"title": f"{title} – {len(lines)} Clip{'s' if len(lines) != 1 else ''}", "body": body, "labels": [LABEL]}
        if cfg.get("einreichen_assignee"): data["assignees"] = [cfg["einreichen_assignee"]]
        try: return gh.call("POST", "/issues", data)
        except Exception as e:
            if "assignees" in data and getattr(e, "code", None) == 422: data.pop("assignees"); return gh.call("POST", "/issues", data)
            raise
    n = cur["number"]
    fresh = gh.call("GET", f"/issues/{n}")                                   # unmittelbar vor dem Schreiben neu lesen (Tipp von Steven nicht überschreiben)
    ticks = ticked | {k for k, v in parse_body(fresh.get("body")).items() if v or fresh.get("state") == "closed"}
    body = render_body(day, lines, ticks)
    old = parse_body(fresh.get("body"))
    new = [l for l in lines if l["key"] not in old]
    if body.strip() != (fresh.get("body") or "").strip():
        if new: gh.call("POST", f"/issues/{n}/comments", {"body": "Neu: " + "; ".join(l["text"] for l in new)})        # Kommentar = Benachrichtigung
        gh.call("PATCH", f"/issues/{n}", {"body": body, "title": f"{title} – {len(lines)} Clip{'s' if len(lines) != 1 else ''}"})
    done = all(l["key"] in ticks for l in lines)
    if done and fresh.get("state") == "open":
        gh.call("POST", f"/issues/{n}/comments", {"body": "Alles eingereicht ✅"}); gh.call("PATCH", f"/issues/{n}", {"state": "closed", "state_reason": "completed"})
    elif not done and fresh.get("state") == "closed":
        gh.call("PATCH", f"/issues/{n}", {"state": "open"})
    return fresh


def run(gh, root, cfg, now, mode="both"):
    """Rückgabe: True, wenn plan/eingereicht.json geändert wurde."""
    ensure_label(gh)
    issues = list_issues(gh)
    ticks = file_ticks(root) | issue_ticks(issues, cfg)
    changed = write_file(root, ticks) if mode in ("sync", "both") else False
    if mode in ("update", "both"):
        stats = W.jl(os.path.join(root, "stats", "latest.json"))
        today = W.local(now).date()
        for off in (-1, 0, 1):
            day = (today + dt.timedelta(days=off)).isoformat()
            if off == -1 and not any(is_ours(i, cfg) and DAY_RE.search(i["body"]).group(1) == day for i in issues): continue
            update_day(gh, root, cfg, day, stats, ticks, issues, now)
    return changed


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--root", default="."); ap.add_argument("--dry", action="store_true")
    ap.add_argument("--mode", default="both", choices=["sync", "update", "both"]); ap.add_argument("--now"); a = ap.parse_args(argv)
    now = W.parse(a.now) if a.now else dt.datetime.now(UTC).replace(microsecond=0)
    cfg = json.load(open(os.path.join(a.root, "plan", "waechter.json")))
    if a.dry:
        stats = W.jl(os.path.join(a.root, "stats", "latest.json")); ticked = file_ticks(a.root)
        for off in (-1, 0, 1):
            day = (W.local(now).date() + dt.timedelta(days=off)).isoformat(); lines = build_lines(a.root, cfg, day, stats)
            if lines: print(render_body(day, lines, ticked), "\n")
        print("(Trockenlauf: nichts geschrieben)"); return 0
    gh = W.GH(os.environ.get("GITHUB_REPOSITORY", "pusnikg-media/pusnikg-media"), os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"))
    changed = run(gh, a.root, cfg, now, a.mode)
    print("CHANGED" if changed else "unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
