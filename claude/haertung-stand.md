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
Advisor-Befunde 2 (vor „fertig") – schon behoben: Sparse-Checkout enthielt `stats/alerts.md` nicht (Commit-Schritt wäre mit `git add`-Fehler gescheitert; im Wegwerf-Klon bestätigt); `| tee` versteckte Abstürze (entfernt); Kampagnen-Zähler brauchte `plattformen` pro Kampagne (Warzone nur TikTok); neues Problem in offenem Issue → jetzt Kommentar (Benachrichtigung); `stand_utc` in `alerts.md` (Wächter-Tod erkennbar); `clipfabrik`-Schwelle 3 → 6 h.

**Offen / nicht erledigt**
1. **Wer schreibt `plan/eingereicht.json`?** Der geplante Clipping-Agent hat evtl. keinen Schreibzugriff aufs Repo (team_state: keine neuen Schreibrechte). Dann bleibt der Alarm „Einreichen" dauerhaft offen. Klären: Steven trägt von Hand ein, oder der Agent bekommt das Recht, oder den Check abschalten (`seit` in die Zukunft setzen).
2. **Instagram unsichtbar:** Kampagnen-Posts auf Instagram stehen nicht in `stats/latest.json` → Wächter kann sie weder auf „live" noch auf „eingereicht" prüfen.
3. **Kein Postplan pro Clip im Repo:** „Clip hätte schon live sein müssen" geht nur für den Tages-Short und nach `bis` einer Kampagne. Vorschlag: `plan/postplan.json` (Clip-ID → Plattform → Zeit), vom Clipping-Agenten beim Einplanen geschrieben; Wächter vergleicht dann pro Clip.
4. **Workflows bleiben „grün bei Fehlern"** (`|| true`, `|| exit 0`, Push-Schleifen enden nach 4–5 Versuchen still). Besser: Ergebnis-JSON `ok:false` → Schritt rot; Push-Fehlschlag → rot. Bewusst nicht geändert (Produktivlauf, kein Test möglich).
5. **Drive-Auftragsordner** per HTML-Regex: ändert Google die Seite, verschwinden Drive-Aufträge still. Idee: Aufträge zusätzlich ins Repo (`jobs/`, `clipjobs/`) spiegeln, dann sieht der Wächter sie.
6. **Livewatch-Repo-Wachstum** (`raw_*.mp4`, ~10 MB pro Clip, Push alle 1–2 Min): Grenze `repo_mb_max` 3500 in `plan/waechter.json`; Aufräumen/Nicht-Committen der Rohdateien ist Sache der Livewatch-Session.
7. **Getrackte `.pyc`-Dateien** im Git (`pipeline/**/__pycache__`, auch Livewatch): `.gitignore` steht, aber getrackte Dateien bleiben. Erst mit der Livewatch-Session klären, dann `git rm -r --cached`.
8. **Wächter-Latenz:** Der Tages-Short (18:00) wird erst am Folgemorgen 06:47 beurteilt (Stats-Lauf 17:17 liegt davor). Soll er am selben Abend auffallen: zusätzlicher `stats`-Lauf ~20:20 Berlin + Wächter-Lauf danach.
9. **Schwellen geschätzt** (`plan/waechter.json`: stats 16 h, trendscout 12 h, kampagnen 15 h, render 3 h, clipfabrik 6 h, `einreichen_nach_minuten` 45). Nach einer Woche gegen Fehlalarme prüfen.
10. **Nicht getestet** (nur im Action-Log): Whisper, Kokoro-TTS, HyperFrames-Render (`npx`), `facecam: auto`/`track` (OpenCV), Netzabfragen (Reddit, Kick, TikTok, Content Rewards, Drive im Betrieb), TikTok-Einstellungen `brandContent` (steht nur in Posts, nicht in `stats`).
11. **`tests`-Action** lädt ffmpeg von GitHub (BtbN-Build, wie die anderen Actions): fällt der Download aus, wird sie rot ohne Codefehler – Log ansehen, erneut starten.
12. **Produzent/Clipping-Agent** sind Claude-Aufgaben, keine Actions: der Wächter sieht nur ihre Ergebnisse (Renderaufträge, Posts), nicht ob sie liefen.
13. **`advisorModel`** in `.claude/settings.json` steht noch auf `fable` → auf `opus` stellen, sobald Fable weg ist (nicht automatisch geändert, weil heute noch andere Sessions Fable nutzen).
14. **Daten-abhängige Tests:** Schema-/Plan-Tests lesen echte Repo-Dateien (`jobs/`, `clips/*/result.json`, `plan/*.json`). Ein neuer Auftrag, der gegen das lose Schema verstößt, macht `tests` rot – der Fehler nennt die Datei. `plan/livewatch.json` und `plan/jason*.json` sind absichtlich nicht geprüft.
