#!/usr/bin/env python3
"""Wächter (0 Credits): Geplant gegen Live, Action-Gesundheit, Kampagnen-Einreichung -> stats/alerts.md + GitHub-Issues (Label "alarm").

  python3 waechter/waechter.py --root . [--dry] [--no-api] [--now 2026-11-17T06:47:00Z]

--dry     nichts schreiben, keine Issues, nur ausgeben (so läuft er auf Nicht-main-Branches und lokal)
--no-api  GitHub-Actions-Status nicht abfragen (offline)
Konfig: plan/waechter.json. Einreich-Notiz: plan/eingereicht.json. Details: claude/haertung-stand.md.

Prinzipien (Advisor 16.11.): Inhalt statt Workflow-Farbe (Actions laufen bei Fehlern oft GRÜN: `|| true`, `|| exit 0`);
'nicht lesbar' ist NICHT 'nicht live' (-> ein Alarm 'Daten', Probleme der betroffenen Plattform werden nicht beurteilt, Issues
werden bei unsicherem Lauf nie geschlossen); ein Datum wird erst beurteilt, wenn stats 'updated' mindestens 2 h nach der Planzeit liegt."""
import argparse, datetime as dt, glob, json, os, re, sys, urllib.error, urllib.request
from zoneinfo import ZoneInfo

BER, UTC = ZoneInfo("Europe/Berlin"), dt.timezone.utc
TITEL = {"daten": "Daten veraltet oder nicht lesbar", "action": "Action fehlgeschlagen oder lange nicht gelaufen", "render": "Short nicht gerendert",
         "clipjob": "Clipfabrik-Auftrag gescheitert", "short": "Tages-Short nicht live", "postzeit": "Post nach 19:30",
         "einreichen": "Kampagnen-Clip nicht bei Content Rewards eingereicht", "kampagne": "Kampagne unvollständig", "repo": "Repo wächst zu stark"}


def jl(path, default=None):
    try: return json.load(open(path))
    except Exception: return default


def parse(s):
    try: return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(UTC)
    except Exception: return None


def hhmm(t): h, m = t.split(":"); return int(h) * 60 + int(m)
def local(t): return t.astimezone(BER)
def at_berlin(day, hm): return dt.datetime.fromisoformat(f"{day}T{hm}:00").replace(tzinfo=BER)


class P:
    """Ein Problem. group = ein Issue pro Gruppe, key = stabile Kennung (für ignorieren)."""
    def __init__(s, group, key, text): s.group, s.key, s.text = group, key, text


def merge_slots(slots):
    """Postplan-Slots mit gleichem Datum/Zeit/Konto/Kampagne zu EINEM Slot zusammenfassen (Plattformen vereinigt). Der Clipping-Agent kann
    pro vidiq_social_post_publish (= pro Plattform) einen Eintrag schreiben; ohne Zusammenfassen gäbe es doppelte Issue-Zeilen."""
    out = {}
    for s in slots:
        if not s.get("datum") or not s.get("zeit"): continue
        k = (s["datum"], s["zeit"], s.get("konto"), s.get("kampagne"))
        if k not in out: out[k] = dict(s, **({"plattformen": list(s["plattformen"])} if "plattformen" in s else {}))
        elif "plattformen" in s:
            have = out[k].setdefault("plattformen", [])
            have += [pl for pl in s["plattformen"] if pl not in have]
    return list(out.values())


def ignored(p, cfg): return any(p.key == i["key"] or p.key.startswith(i["key"] + ":") for i in cfg.get("ignorieren", []))


def check_daten(root, cfg, now, st):
    """Veraltete/teilweise Daten. Rückgabe: (Probleme, blind = {(konto, plattform)}, unsicher = [Gründe])."""
    out, blind, unsicher = [], set(), []
    mx = cfg["max_alter_stunden"]
    for name, path, field in (("stats", "stats/latest.json", "updated"), ("trends", "trends/latest.json", "at"), ("campaigns", "campaigns/latest.json", "at")):
        d = jl(os.path.join(root, path)); t = parse((d or {}).get(field))
        if not t: out.append(P("daten", f"daten:{name}", f"{path} fehlt oder ist unlesbar.")); unsicher.append(name); continue
        age = (now - t).total_seconds() / 3600
        if age > mx[name]:
            out.append(P("daten", f"daten:{name}:alt", f"{path} ist {age:.0f} h alt (erlaubt {mx[name]} h) – die Action liefert nichts Neues, auch wenn sie grün aussieht."))
            if name == "stats": unsicher.append("stats alt")
        if d.get("errors") and name != "stats":
            out.append(P("daten", f"daten:{name}:fehler", f"{path}: " + "; ".join(str(e)[:90] for e in d["errors"][:3])))
    for line in (st or {}).get("problems", []):
        if line.startswith("Instagram"): continue
        for acc in (st.get("accounts") or {}):
            if line.startswith(acc + " "):
                plat = "tiktok" if "TikTok" in line else "youtube" if ("YouTube feed" in line) else None
                if plat: blind.add((acc, plat)); unsicher.append(f"{acc} {plat}")
                if plat or "shorts tab" not in line: out.append(P("daten", f"daten:stats:{acc}:{plat or 'sonst'}", f"stats: {line[:140]}"))
    return out, blind, unsicher


def check_actions(cfg, now, runs):
    """runs: {workflow: [Läufe neueste zuerst] | None (nicht lesbar)}. Fehlerlauf = der NEUESTE abgeschlossene Lauf ist failure/timed_out."""
    out, unsicher = [], []
    for name, mx in cfg["max_alter_actions_stunden"].items():
        r = runs.get(name)
        if r is None: unsicher.append(f"Action {name}: Status nicht lesbar"); continue
        done = [x for x in r if x.get("status") == "completed" and x.get("conclusion") != "cancelled"]
        if not done: out.append(P("action", f"action:{name}:leer", f"Action '{name}': keine abgeschlossenen Läufe gefunden.")); continue
        if done[0]["conclusion"] in ("failure", "timed_out", "startup_failure"):
            out.append(P("action", f"action:{name}:fehler", f"Action '{name}': letzter Lauf {done[0]['conclusion']} ({done[0].get('html_url', '')})"))
        ok = [x for x in done if x["conclusion"] == "success"]
        age = (now - parse(ok[0]["updated_at"])).total_seconds() / 3600 if ok else None
        if age is None or age > mx:
            out.append(P("action", f"action:{name}:alt", f"Action '{name}': letzter erfolgreicher Lauf " + (f"vor {age:.0f} h" if age is not None else "nicht gefunden") + f" (erlaubt {mx} h)."))
    return out, unsicher


def check_render(root, now, fresh=lambda p: False):
    out, today = [], local(now).date()
    by = {}
    for f in sorted(glob.glob(os.path.join(root, "jobs", "*.json"))):
        j = jl(f) or {}; d = j.get("date"); n = j.get("name") or os.path.basename(f)[:-5]
        if not d or not (today <= dt.date.fromisoformat(d) <= today + dt.timedelta(days=2)): continue
        r = jl(os.path.join(root, "shorts", n + ".json"))
        if r is None and fresh(f"jobs/{os.path.basename(f)}"): continue          # gerade erst gepusht: die Action ist noch dran
        by.setdefault(d, []).append((n, r))
    for d, lst in sorted(by.items()):
        if any(r and r.get("ok") for _, r in lst): continue
        why = "; ".join(f"{n}: " + ("noch kein Ergebnis" if r is None else f"ok=false nach {r.get('attempts', '?')} Versuchen – {str(r.get('error', ''))[:80]}") for n, r in lst)
        out.append(P("render", f"render:{d}", f"Short für {d} ist nicht fertig gerendert ({why})."))
    return out


def check_clipjobs(root, fresh=lambda p: False):
    out = []
    for f in sorted(glob.glob(os.path.join(root, "clipjobs", "*.json"))):
        j = jl(f) or {}; n = j.get("name") or os.path.basename(f)[:-5]
        if not j.get("clips"): continue
        r = jl(os.path.join(root, "clips", n, "result.json"))
        if r is None and fresh(f"clipjobs/{os.path.basename(f)}"): continue      # gerade erst gepusht
        if r is None: out.append(P("clipjob", f"clipjob:{n}:fehlt", f"Clipfabrik-Auftrag '{n}' hat noch kein Ergebnis (clips/{n}/result.json)."))
        elif not r.get("ok"):
            bad = [c["id"] for c in r.get("clips", []) if not c.get("ok")]
            out.append(P("clipjob", f"clipjob:{n}:fehler", f"Clipfabrik '{n}': ok=false, Versuche {r.get('attempts', '?')}" + (", Clips " + ",".join(bad) if bad else "") + f" – {str(r.get('error', ''))[:100]}"))
    return out


def check_short(root, cfg, now, st, blind, ):
    """Pro Datum mit Render-Auftrag (seit 'seit'): läuft der Tages-Short auf YouTube und TikTok live?"""
    out, c = [], cfg["tagesshort"]; upd = parse((st or {}).get("updated"))
    if not upd: return out
    dates = {(jl(f) or {}).get("date") for f in glob.glob(os.path.join(root, "jobs", "*.json"))}
    ab, bis, heute = c.get("taeglich_ab"), c.get("taeglich_bis"), local(now).date()      # ab `taeglich_ab` (bis auf Widerruf/`taeglich_bis`) wird jeden Tag ein Short erwartet, auch ohne jobs/-Auftrag
    if ab:
        d0 = dt.date.fromisoformat(ab)
        dates |= {(d0 + dt.timedelta(days=i)).isoformat() for i in range((heute - d0).days + 1) if not bis or (d0 + dt.timedelta(days=i)).isoformat() <= bis}
    for d in sorted(x for x in dates if x and cfg["seit"] <= x <= local(now).date().isoformat()):
        due = at_berlin(d, "18:00") + dt.timedelta(hours=c["karenz_stunden"])
        if now < due or upd < due: continue          # erst beurteilen, wenn die Zahlen NACH der Planzeit gemessen wurden
        for plat in c["plattformen"]:
            if (c["konto"], plat) in blind: continue
            hit = [p for p in st["posts"] if p["account"] == c["konto"] and p["platform"] == plat and p.get("published") and not p.get("campaign")
                   and local(parse(p["published"])).date().isoformat() == d and hhmm(c["von"]) <= hhmm(local(parse(p["published"])).strftime("%H:%M")) <= hhmm(c["bis"])]
            if not hit: out.append(P("short", f"short:{d}:{plat}", f"Tages-Short vom {d} fehlt auf {plat} ({c['konto']}, erwartet {c['von']}–{c['bis']} Uhr)."))
    return out


def check_postzeit(cfg, now, st):
    out, lim = [], hhmm(cfg["postzeit_ende"]) + cfg.get("postzeit_toleranz_min", 0)
    for p in (st or {}).get("posts", []):
        t = parse(p.get("published"))
        if not t or local(t).date().isoformat() < cfg["seit"]: continue
        if hhmm(local(t).strftime("%H:%M")) > lim:
            day, art = local(t).date().isoformat(), "kampagne" if p.get("campaign") else "short"                 # Schlüssel: postzeit:<Berlin-Datum>:<short|kampagne>:<plattform>:<id> -> `ignorieren` kann einen Tag einzeln freigeben (ID ist vorher unbekannt)
            out.append(P("postzeit", f"postzeit:{day}:{art}:{p['platform']}:{p['id']}", f"{p['account']} {p['platform']} um {local(t):%d.%m. %H:%M} Uhr: „{p['title'][:50]}“ – {p['url']}"))
    return out


def check_einreichen(root, cfg, now, st, blind):
    """Kampagnen-Post ohne Einreich-Nachweis. Nachweis = (a) Slot in plan/eingereicht.json `slots` ('konto|kampagne|datum|HH:MM', von der Aktion
    `einreichen` aus den Haken im Tages-Issue geschrieben; Post wird dem nächsten Slot ±14 Min zugeordnet), (b) Post-ID/URL unter
    `eingereicht`/`posts`, (c) `nicht_noetig`."""
    out, e = [], jl(os.path.join(root, "plan", "eingereicht.json"), {}) or {}
    start = max(cfg["seit"], e.get("seit", cfg["seit"])); known = [str(x) for x in e.get("eingereicht", []) + e.get("nicht_noetig", []) + e.get("posts", [])]
    slots = []
    for k in e.get("slots", []):
        try: konto, kamp, datum, zeit = k.split("|"); slots.append((konto, kamp, at_berlin(datum, zeit).astimezone(UTC)))
        except Exception: continue
    stats_of = {k["name"]: k["stats"] for k in cfg.get("kampagnen", [])}
    for p in (st or {}).get("posts", []):
        t = parse(p.get("published"))
        if not p.get("campaign") or not t or local(t).date().isoformat() < start or (p["account"], p["platform"]) in blind: continue
        if (now - t).total_seconds() / 60 < cfg["einreichen_nach_minuten"]: continue
        if any(p["id"] in k or p["url"] in k or k in p["url"] for k in known if len(k) > 5): continue
        if any(konto == p["account"] and stats_of.get(kamp, kamp) == p["campaign"] and abs((t - ts).total_seconds()) <= 14 * 60 for konto, kamp, ts in slots): continue
        out.append(P("einreichen", f"einreichen:{p['platform']}:{p['id']}", f"{p['campaign']} ({p['account']}, {p['platform']}, {local(t):%d.%m. %H:%M}): „{p['title'][:45]}“ – {p['url']}"))
    return out


def check_slots_live(root, cfg, now, st, blind):
    """Postplan (plan/postplan.json, vom Clipping-Agenten): Slot längst vorbei, aber kein Post desselben Kontos/derselben Plattform
    innerhalb ±14 Min in den Zahlen -> der Clip ist nicht rausgegangen. Nur YouTube/TikTok (Instagram ist unsichtbar); erst zwei Stunden
    nach der Planzeit UND wenn die Zahlen danach gemessen wurden (wie beim Tages-Short)."""
    out, upd = [], parse((st or {}).get("updated"))
    plan = jl(os.path.join(root, "plan", "postplan.json"), {}) or {}
    if not upd: return out
    for s in merge_slots(plan.get("slots", [])):
        if s["datum"] < cfg["seit"]: continue
        t0 = at_berlin(s["datum"], s["zeit"]).astimezone(UTC); due = t0 + dt.timedelta(hours=cfg.get("slot_karenz_stunden", 2))
        if now < due or upd < due: continue
        for plat in s.get("plattformen", []):
            if plat not in ("youtube", "tiktok") or (s["konto"], plat) in blind: continue
            hit = [p for p in st["posts"] if p["account"] == s["konto"] and p["platform"] == plat and p.get("published")
                   and abs((parse(p["published"]) - t0).total_seconds()) <= 14 * 60]
            if not hit: out.append(P("kampagne", f"live:{s['datum']}:{s['zeit']}:{s['konto']}:{plat}", f"{s['kampagne']} „{s.get('titel', s.get('clip', ''))}“ ({s['konto']}) war für {s['datum'][8:]}.{s['datum'][5:7]}. {s['zeit']} auf {plat} geplant, ist in den Zahlen aber nicht live."))
    return out


def check_postplan_regeln(root, now):
    """Vorbeugend (Fable-Nacht 16.11.): Regeln auf dem PLAN, bevor etwas schiefgeht. Gilt nur fuer Slots ab heute (Berlin).
    Kampagnen-Clip nie nach 19:30, nie um 18:00 (Tages-Short), hoechstens 2 pro Konto und Tag, derselbe Clip nicht zweimal (doppelter Post)."""
    plan = jl(os.path.join(root, "plan", "postplan.json"), {}) or {}
    today = f"{local(now):%Y-%m-%d}"; out, per_day, seen = [], {}, {}
    caps = {k["name"]: int(k["max_pro_tag"]) for k in ((jl(os.path.join(root, "plan", "waechter.json"), {}) or {}).get("kampagnen") or []) if k.get("max_pro_tag")}  # Steven-Ausnahme je Kampagne (z. B. Kai Cenat: 4/Tag)
    for s in merge_slots(plan.get("slots", [])):
        if s["datum"] < today: continue
        who = f"{s.get('kampagne')} {s.get('clip', '')} ({s.get('konto')}) {s['datum'][8:]}.{s['datum'][5:7]}. {s['zeit']}"
        if hhmm(s["zeit"]) > hhmm("19:30"): out.append(P("postzeit", f"plan-spaet:{s['datum']}:{s['zeit']}:{s.get('konto')}", f"Plan verletzt die 19:30-Regel: {who}."))
        if s["zeit"] == "18:00": out.append(P("postzeit", f"plan-1800:{s['datum']}:{s.get('konto')}", f"Plan: Kampagnen-Clip um 18:00 (Slot des Tages-Shorts): {who}."))
        per_day.setdefault((s["datum"], s.get("konto"), s.get("kampagne") if s.get("kampagne") in caps else None), []).append(s)
        if s.get("clip"): seen.setdefault(s["clip"], []).append(s)
    for (d, konto, kamp), sl in per_day.items():
        mx = caps.get(kamp, 2)
        if len(sl) > mx: out.append(P("postzeit", f"plan-max{mx}:{d}:{konto}" + (f":{kamp}" if kamp else ""), f"Plan: {len(sl)} {'Kampagnen-Clips' if not kamp else kamp + '-Clips'} am {d[8:]}.{d[5:7]}. auf {konto} (erlaubt: {mx})."))
    for clip, sl in seen.items():
        if len(sl) > 1: out.append(P("postzeit", f"plan-doppelt:{clip}", f"Plan: Clip {clip} steht {len(sl)}x im Postplan ({', '.join(x['datum'][5:] + ' ' + x['zeit'] for x in sl)}) – doppelter Post?"))
    return out


def check_kampagnen(root, cfg, now, st, blind):
    out, today = [], local(now).date().isoformat()
    for k in cfg["kampagnen"]:
        if not k.get("erwartet"): continue
        rend = 0
        for n in k["clips"]:
            r = jl(os.path.join(root, "clips", n, "result.json")) or {}
            rend += sum(1 for c in r.get("clips", []) if c.get("ok") and r.get("phase") == "rendered")
        if rend < k["erwartet"]: out.append(P("kampagne", f"kampagne:{k['name']}:render", f"{k['name']}: nur {rend} von {k['erwartet']} geplanten Clips gerendert (clips/{'/, clips/'.join(k['clips'])}/)."))
        if k.get("bis") and today > k["bis"]:
            for plat in k.get("plattformen", ["youtube", "tiktok"]):
                if (k["konto"], plat) in blind: continue
                live = sum(1 for p in (st or {}).get("posts", []) if p.get("campaign") == k["stats"] and p["platform"] == plat and p["account"] == k["konto"])
                if live < k["erwartet"]: out.append(P("kampagne", f"kampagne:{k['name']}:{plat}", f"{k['name']}: Zeitraum vorbei (bis {k['bis']}), aber nur {live} von {k['erwartet']} Clips live auf {plat}."))
    return out


def check_repo(cfg, mb):
    """mb = Repo-Größe laut GitHub-API (inkl. Historie). Livewatch legt pro Clip ca. 10 MB + Rohdatei ab - das Repo wächst."""
    if mb is None or mb <= cfg["repo_mb_max"]: return []
    return [P("repo", "repo:groesse", f"Repo ist {mb:.0f} MB groß (Alarm ab {cfg['repo_mb_max']} MB; GitHub empfiehlt unter 5 GB). Livewatch-Rohdateien (clips/live-*/raw_*.mp4) wachsen mit.")]


def evaluate(root, cfg, now, runs, repo_mb=None, fresh=lambda p: False):
    st = jl(os.path.join(root, "stats", "latest.json"))
    probs, blind, unsicher = check_daten(root, cfg, now, st)
    if runs is not None:
        a, u = check_actions(cfg, now, runs); probs += a; unsicher += u
    else: unsicher.append("Action-Status nicht abgefragt")
    probs += check_render(root, now, fresh) + check_clipjobs(root, fresh) + check_repo(cfg, repo_mb) + check_postplan_regeln(root, now)
    if st:
        probs += check_short(root, cfg, now, st, blind) + check_postzeit(cfg, now, st) + check_einreichen(root, cfg, now, st, blind) + check_kampagnen(root, cfg, now, st, blind) + check_slots_live(root, cfg, now, st, blind)
    return [p for p in probs if not ignored(p, cfg)], unsicher


def markdown(probs, unsicher, now):
    L = [f"# Alarme – Stand {local(now):%d.%m.%Y %H:%M} (Europe/Berlin)", "", f"stand_utc: {now:%Y-%m-%dT%H:%M:%SZ}  (älter als ca. 15 h = Wächter tot, Alarmliste nicht vertrauen)", "", "Vom Wächter (3× täglich: 06:47, 12:37, 20:47 Berlin, 0 Credits). Nur offene Probleme. Gelöstes verschwindet von selbst.", ""]
    if not probs: L += ["**Keine offenen Probleme.**", ""]
    for g in dict.fromkeys(p.group for p in probs):
        L += [f"## {TITEL.get(g, g)}"] + [f"- {p.text}" for p in probs if p.group == g] + [""]
    if unsicher: L += ["## Nicht beurteilbar (Lauf unsicher – es können Probleme fehlen)"] + [f"- {u}" for u in unsicher] + [""]
    return "\n".join(L)


# ---------- GitHub (Actions-Status + Issues) ----------
class GH:
    def __init__(s, repo, token): s.repo, s.token = repo, token
    def call(s, method, path, body=None):
        rq = urllib.request.Request(f"https://api.github.com/repos/{s.repo}{path}", method=method, data=json.dumps(body).encode() if body is not None else None,
                                    headers={"Accept": "application/vnd.github+json", "User-Agent": "pusnikg-waechter", **({"Authorization": f"Bearer {s.token}"} if s.token else {})})
        return json.loads(urllib.request.urlopen(rq, timeout=30).read() or b"null")

    def runs(s, names):
        out = {}
        for n in names:
            try: out[n] = s.call("GET", f"/actions/workflows/{n}.yml/runs?branch=main&per_page=10&status=completed")["workflow_runs"]
            except Exception as e: print(f"Actions-Status {n}: {e}", file=sys.stderr); out[n] = None
        return out

    def fresh(s, path, hours=2):
        """Datei in den letzten `hours` Stunden committet? (Schonfrist für frisch gepushte Aufträge; bei Fehler: nein)"""
        try:
            c = s.call("GET", f"/commits?path={path}&per_page=1")
            return bool(c) and (dt.datetime.now(UTC) - parse(c[0]["commit"]["committer"]["date"])).total_seconds() < hours * 3600
        except Exception: return False

    def size_mb(s):
        try: return s.call("GET", "")["size"] / 1024
        except Exception as e: print(f"Repo-Größe: {e}", file=sys.stderr); return None

    def sync_issues(s, probs, sicher):
        try: s.call("POST", "/labels", {"name": "alarm", "color": "d73a4a", "description": "Wächter: offenes Problem"})
        except urllib.error.HTTPError as e:
            if e.code != 422: raise                                    # 422 = Label existiert schon
        issues = [i for i in s.call("GET", "/issues?labels=alarm&state=open&per_page=100") if "pull_request" not in i]
        have = {}
        for i in issues:
            m = re.search(r"<!-- waechter-group: ([\w-]+) -->", i.get("body") or "")
            if not m: continue
            if m.group(1) in have: s.call("PATCH", f"/issues/{i['number']}", {"state": "closed", "state_reason": "not_planned"}); continue   # Doppelte schließen
            have[m.group(1)] = i
        groups = {g: [p for p in probs if p.group == g] for g in dict.fromkeys(p.group for p in probs)}
        for g, ps in groups.items():
            body = f"<!-- waechter-group: {g} -->\n" + "\n".join(f"- {p.text}" for p in ps) + "\n\n_Automatisch vom Wächter (stats/alerts.md). Schließt sich selbst, sobald das Problem weg ist._"
            if g in have:
                old = (have[g].get("body") or "").strip()
                if old != body.strip():
                    new = [l for l in body.splitlines() if l.startswith("- ") and l not in old.splitlines()]
                    if new: s.call("POST", f"/issues/{have[g]['number']}/comments", {"body": "Neu dazugekommen:\n" + "\n".join(new)})   # Kommentar = Benachrichtigung
                    s.call("PATCH", f"/issues/{have[g]['number']}", {"body": body})
            else: s.call("POST", "/issues", {"title": "Alarm: " + TITEL.get(g, g), "body": body, "labels": ["alarm"]})
        if sicher:                                                      # bei unsicherem Lauf NIE schließen (Daten fehlten)
            for g, i in have.items():
                if g not in groups:
                    s.call("POST", f"/issues/{i['number']}/comments", {"body": "Gelöst – beim letzten Wächter-Lauf nicht mehr gefunden."})
                    s.call("PATCH", f"/issues/{i['number']}", {"state": "closed", "state_reason": "completed"})


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--root", default="."); ap.add_argument("--dry", action="store_true")
    ap.add_argument("--no-api", action="store_true"); ap.add_argument("--now"); a = ap.parse_args(argv)
    now = parse(a.now) if a.now else dt.datetime.now(UTC).replace(microsecond=0)
    cfg = json.load(open(os.path.join(a.root, "plan", "waechter.json")))
    gh = GH(os.environ.get("GITHUB_REPOSITORY", "pusnikg-media/pusnikg-media"), os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"))
    runs = None if a.no_api else gh.runs(list(cfg["max_alter_actions_stunden"]))
    probs, unsicher = evaluate(a.root, cfg, now, runs, None if a.no_api else gh.size_mb(), (lambda p: False) if a.no_api else gh.fresh)
    if runs and any(v is None for v in runs.values()) and not a.dry:
        probs.append(P("daten", "daten:actions", "GitHub-Actions-Status war nicht lesbar – Lauf unsicher."))
    md = markdown(probs, unsicher, now); print(md)
    if a.dry: print("(Trockenlauf: nichts geschrieben, keine Issues)"); return 0
    os.makedirs(os.path.join(a.root, "stats"), exist_ok=True); open(os.path.join(a.root, "stats", "alerts.md"), "w").write(md)
    gh.sync_issues(probs, sicher=not unsicher)
    return 0


if __name__ == "__main__":
    sys.exit(main())
