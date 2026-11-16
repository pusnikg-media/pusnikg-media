# Härtung – Stand 16.11.2026

Ziel: Repo so absichern, dass Sonnet (+ Opus-Advisor) ab 17.11. sicher und sparsam arbeiten kann. Alles 0 Credits, nichts gepostet.

## Was gebaut wurde
| Teil | Wo | Kurz |
|---|---|---|
| Landkarte | `CLAUDE.md` (Abschnitt „Landkarte") | Dateien, Actions (UTC), `plan/*.json`, Daten-Ausgaben, 11 Fallen |
| Smoke-Tests | `tests/` (≈150 Fälle, ≈40 s) | Clipfabrik-Layouts native/full/framed/split + Hook, `check_clips`, goldene `job_sig`, `pending()` + Drive-Parser (Fixture); HyperFrames-Trockenlauf (`preflight.py`, `build_cd.py`); `stats.py` (Beispielfeeds, „nichts lesbar", Teilausfall); `gh_jobs.py` (3-Versuche-Logik, Drive); JSON-Schemas; Selbsttests von kampagnen/trendscout/stats; Wächter |
| Action `tests` | `.github/workflows/tests.yml` | bei jedem Push/PR (Daten-Pushes ausgenommen). **Rot = Push gilt als kaputt** |
| Wächter | `waechter/waechter.py`, `plan/waechter.json`, `.github/workflows/waechter.yml` | 05:47 + 11:37 UTC → `stats/alerts.md` + Issues „alarm" |
| Einreich-Notiz | `plan/eingereicht.json` | Clipping-Agent trägt Post-URLs ein; Wächter meldet Kampagnen-Posts ohne Eintrag nach 45 Min |
| Doku | `plan/team_state.md` (Abschnitt „Wächter und Tests"), `pipeline/README.md` (Metricool-Zeile korrigiert), `.gitignore` (`__pycache__`) | |

## Benutzen
- **Tests:** `pip install pytest jsonschema pillow numpy scipy` (+ ffmpeg mit libass), dann `python3 -m pytest tests -q`. Einzeln: `pytest tests/test_stats.py -q`. Goldene `job_sig` ändert sich nur bei bewusster Änderung der Signatur-Felder (dann Wert in `tests/test_clipfabrik.py` anpassen – bedeutet Neurender ALLER Clipjobs).
- **Wächter lokal:** `python3 waechter/waechter.py --dry --no-api [--now 2026-11-17T05:47:00Z]` (liest die Dateien im Checkout; ohne `--no-api` fragt er GitHub-Actions-Status ab). Echt (schreibt Datei + Issues) läuft nur die Action auf `main`; auf anderen Branches ist die Action ein Trockenlauf. Von Hand starten: Actions → waechter → Run workflow.
- **Alarm lesen:** `stats/alerts.md`. Gruppen: Daten, Action, Render, Clipfabrik, Tages-Short, Postzeit, Einreichen, Kampagne, Repo. Ein Issue pro Gruppe, `<!-- waechter-group: … -->` im Text; er aktualisiert den Text, schließt bei gelöstem Problem – aber nie bei „unsicherem" Lauf (Daten fehlten).
- **Ausnahme:** `plan/waechter.json` → `ignorieren` (`key` = Alarm-Kennung, z. B. `short:2026-11-12` oder `einreichen:tiktok:<id>`, mit `grund`). 12.11. und 13.11. sind schon drin.
- **Neue Kampagne:** Zeile in `plan/waechter.json` → `kampagnen` (`stats` = Name wie in `plan/stats.json`, `clips` = Ordner in `clips/`, `erwartet`, `bis`).

## Advisor-Befunde 1 (Architektur) – die 5 riskantesten Stellen
Status: ✅ abgedeckt (Wächter/Test), ⚠️ nur gemeldet, ❌ offen.
1. **Grün bei Fehlern** (`|| true` in render/clipfabrik, `|| exit 0` in stats/kampagnen; Aufgeben nach 3 Versuchen ohne Meldung): ✅ Wächter liest `ok`/`attempts` der Ergebnis-JSONs (`render:*`, `clipjob:*`) und den Lauf-Status der Actions; Tests dokumentieren das stille Aufgeben. ❌ Die Workflows selbst unverändert (bewusst).
2. **Veraltete/teilweise `stats/latest.json`** („nichts lesbar" behält alte Datei, Teilausfall nur als `problems`-Zeile): ✅ Wächter prüft `updated`, wertet `problems` aus (ein „Daten"-Alarm; Plattform wird nicht beurteilt, Issues bleiben offen); Tests für beide Fälle.
3. **Drive-Ordner-Scrape per Regex** (`clipfabrik.pending`, `gh_jobs.py`; Ausnahme nur auf stderr): ⚠️ Tests mit gespeicherter Beispielseite sichern das Parsen, **nicht** eine geänderte Drive-Seite im Betrieb. ❌ Offen: ein Drive-Auftrag, der plötzlich nie ankommt, ist nur am fehlenden Ergebnis sichtbar (Wächter meldet `render:`/`clipjob:fehlt` erst nach Planung). Idee: Drive-Aufträge zusätzlich als Datei ins Repo spiegeln.
4. **Push-Schleifen auf `main`** (4–5 Versuche, danach still grün; Livewatch pusht alle 1–2 Min inkl. `raw_*.mp4`): ⚠️ nur gemeldet (Repo-Größe im Wächter, Grenze `repo_mb_max`). ❌ Offen für die Livewatch-Session: `raw_*.mp4` nicht committen, Aufräumen, Push-Kollisionen. Nicht angefasst.
5. **Keine Verbindung Geplant↔Live, „eingereicht"-Notiz existierte nicht:** ✅ `plan/eingereicht.json` + Wächter (pro Post, ab `seit`); Kampagnen-Zähler (gerendert vs. live) nur für Kampagnen mit `erwartet`/`bis` in `plan/waechter.json`. ❌ Es gibt keinen Plan mit Postzeiten pro Clip im Repo → der Wächter kann „Clip hätte schon live sein müssen" nur nach Kampagnen-Ende (`bis`) und für den Tages-Short beurteilen.

## Offene Punkte für spätere Sonnet-Sessions (nach Wichtigkeit)
(wird nach dem letzten Advisor-Aufruf ergänzt)
