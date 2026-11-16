#!/usr/bin/env python3
"""Livewatch-Erkennung messbar machen (Session 2, 16.11.2026) - liest das Log eines livewatch-Laufs, ändert nichts an livewatch.py.

Jeder Kandidat (Minute mit Lautstärke-Spitze oder Chat-Ausbruch) wird mit Grund und Score als Zeile ausgegeben:
  Kanal | Minute | Pos (s) | Art (chat/laut) | hype | chat x | Ergebnis | Grund | brauchbar?
Ergebnis: clip / verworfen / gesperrt.
Grund:    Werbepause, Alert-Kette, Aufwärmzeit, unter Schwelle, Abstand/Limit, ohne Chat-Bestätigung, zu wenig Sprache, Selbstverletzung, ...

Benutzen am Donnerstag (Chat-Session, kein Netz nötig außer dem Log):
  1. Log des livewatch-Laufs holen (GitHub-Tool get_job_logs, oder Actions -> Lauf -> Log herunterladen) -> lw.log
  2. python3 tests/livewatch_messen.py lw.log                 -> Tabelle (Markdown) + Zusammenfassung
  3. Clips ansehen, in bewertung.json eintragen: {"<Kanal>:<Pos>": true/false, ...} (true = postbar)
     python3 tests/livewatch_messen.py lw.log bewertung.json  -> zusätzlich Trefferquote (postbar / Clips) je Kanal und Art
Optionen: --warmup 480 --min-hype 9 (müssen zu plan/livewatch.json passen; Standard = Code-Standard).
"""
import json, re, sys

MIN_RE = re.compile(r"min\s+(\d+) hype\s+([\d.]+) peak (\S+) chat x([\d.]+) at (\S+)")
RULES = [  # (Muster in den Folgezeilen, Ergebnis, Grund)
    (re.compile(r"skipped: alert chain"), "gesperrt", "Alert-Kette (Subs/Raids, kein echter Moment)"),
    (re.compile(r"moment skipped: Twitch ad break"), "gesperrt", "Werbepause"),
    (re.compile(r"WARN clip failed:.*too little speech"), "verworfen", "zu wenig Sprache (Musik/Werbung/Stille)"),
    (re.compile(r"WARN clip failed:.*self-harm"), "verworfen", "Selbstverletzung im Wortlaut"),
    (re.compile(r"WARN clip failed:.*almost no speech"), "verworfen", "kaum Sprache im Schnitt"),
    (re.compile(r"WARN clip failed:.*gap"), "verworfen", "Aufnahmelücke"),
    (re.compile(r"WARN clip failed:"), "verworfen", "Fehler beim Schneiden"),
    (re.compile(r"PUBLISHED|WARN push failed"), "clip", "Clip erstellt"),
]
CHAT_RE = re.compile(r"chat burst x([\d.]+): moment (\d+) s before")


def parse(lines, warmup=480, min_hype=9.0):
    rows, cur, block = [], None, []
    def close():
        if cur is None: return
        m, hype, peak, cr, cp = cur
        res, why, kind, lag = None, None, "laut", None
        for l in block:
            c = CHAT_RE.search(l)
            if c: kind, lag = "chat", int(c.group(2))
            for rx, r, w in RULES:
                if rx.search(l) and res is None: res, why = r, w
        if peak is None and kind != "chat" and res is None: return  # keine Spitze, kein Ausbruch -> kein Kandidat
        if res is None:
            if m * 60 <= warmup: res, why = "gesperrt", "Aufwärmzeit"
            elif kind == "laut" and hype < min_hype: res, why = "gesperrt", f"unter Schwelle (hype {hype} < {min_hype})"
            elif kind == "laut" and cr > 0: res, why = "gesperrt", "ohne Chat-Bestätigung"
            else: res, why = "gesperrt", "Abstand 90 s / Stundenlimit / max_clips"
        pos = max(cp + 4 - (lag or 0), 0) if kind == "chat" and cp is not None else peak  # wie loop(): Moment = lauteste Sekunde vor dem Chat
        rows.append({"min": m, "pos": pos, "kind": kind, "hype": hype, "chat": cr, "lag": lag, "result": res, "why": why})
    for l in lines:
        l = l.rstrip("\n"); l = re.sub(r"^\S+Z\s", "", l)  # Zeitstempel aus GitHub-Logs
        mm = MIN_RE.search(l)
        if mm:
            close(); block = []
            cur = (int(mm.group(1)), float(mm.group(2)), None if mm.group(3) == "None" else int(mm.group(3)), float(mm.group(4)),
                   None if mm.group(5) == "None" else int(mm.group(5)))
            continue
        ls = re.search(r"LOOP_STATS (\S+)", l)
        if ls:
            close(); cur = None; block = []
            for r in rows:
                r.setdefault("channel", ls.group(1))
            continue
        block.append(l)
    close()
    for r in rows: r.setdefault("channel", "?")
    # dieselbe Spitze erscheint mehrere Minuten hintereinander: nur die erste zählt (sonst doppelte Kandidaten)
    out, seen = [], set()
    for r in rows:
        k = (r["channel"], r["pos"], r["kind"])
        if r["pos"] is not None and k in seen and r["result"] != "clip": continue
        seen.add(k); out.append(r)
    return out


def report(rows, rating=None):
    L = ["| Kanal | Min | Pos (s) | Art | hype | chat x | Ergebnis | Grund | postbar? |", "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        k = f"{r['channel']}:{r['pos']}"; ok = "" if not rating or k not in rating else ("ja" if rating[k] else "nein")
        L.append(f"| {r['channel']} | {r['min']} | {r['pos']} | {r['kind']} | {r['hype']} | {r['chat']} | {r['result']} | {r['why']} | {ok} |")
    clips = [r for r in rows if r["result"] == "clip"]
    from collections import Counter
    L += ["", f"Kandidaten {len(rows)}, Clips {len(clips)}, Gründe: " + ", ".join(f"{w} {n}" for w, n in Counter(r["why"] for r in rows).most_common())]
    if rating:
        for kind in ("chat", "laut"):
            rated = [r for r in clips if r["kind"] == kind and f"{r['channel']}:{r['pos']}" in rating]
            good = sum(1 for r in rated if rating[f"{r['channel']}:{r['pos']}"])
            if rated: L.append(f"Trefferquote {kind}: {good}/{len(rated)} postbar ({100 * good // len(rated)} %)")
    return "\n".join(L)


if __name__ == "__main__":
    a, opt, it = [], {}, iter(sys.argv[1:])
    for x in it:
        if x.startswith("--"): opt[x] = next(it, "")
        else: a.append(x)
    if not a: sys.exit(__doc__)
    rows = parse(open(a[0], encoding="utf-8", errors="replace"), int(opt.get("--warmup", 480)), float(opt.get("--min-hype", 9)))
    rating = json.load(open(a[1])) if len(a) > 1 else None
    print(report(rows, rating))
