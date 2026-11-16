# Pusnik G – Regeln
Gaming-Shorts-Kanal "Pusnik G" (YT Shorts, TikTok, Reels) + Clipping-Kampagnen (Content Rewards). Ziel: möglichst vollautomatische Content-Maschine.

## Steven
- Deutsch mit ihm. Nur iPhone/iPad, kein PC.
- Liest am Handy: kurz, Ergebnis zuerst.
- Pro-Abo: Token sparen, keine unnötigen Agenten/Recherchen/Konnektor-Aufrufe. Gratis-Tools bevorzugt.

## Inhalte
- Titel, Captions, Skripte, Kommentare: Englisch, kopierfertig, ohne Überschriften wie "Description:".
- TikTok: genau 5 Hashtags im Text.
- Hook in Sekunde 1, keine beschleunigten Voiceovers.
- Nie nach 19:30 (Europe/Berlin) posten. Nie ohne Stevens "ja" veröffentlichen.
- Nur lizenziertes/erlaubtes Material mit eigenem Mehrwert.

## Advisor
- Max. 3 Aufrufe pro Aufgabe: vor dem Plan, wenn ein Fehler 2x auftritt, vor "fertig".
- Ist er bei "fertig" unzufrieden: nachbessern, genau 1x erneut fragen, dann stoppen und offene Punkte nennen.
- Nicht für Routine (lesen, kleine Fixes, Posts anlegen).
- Eine Aufgabe = eine Session. Wenn die Aufgabe fertig ist, sag Steven: "Für die nächste Aufgabe neue Session starten."

# Landkarte (Stand 16.11.2026 – neue Session: erst `stats/alerts.md`, dann dieses Blatt, dann `plan/team_state.md`; `pipeline/README.md` nur für Details)
## Arbeitsregeln fürs Repo
- **Tests:** `python3 -m pytest tests -q` (~40 s; braucht ffmpeg, pytest, jsonschema, pillow, numpy, scipy). Action `tests` läuft bei jedem Push (Daten-Pushes ausgenommen). **Rot = Push gilt als kaputt → sofort beheben, nichts Neues obendrauf.** Neuer Fix an Clipfabrik/Stats/Plan-Dateien = Test dazu.
- **Git:** Nie `git add -A` (im Repo liegen `__pycache__/*.pyc`) – Pfade einzeln. `main` bewegt sich minütlich (Livewatch, Actions): vor Push `git fetch origin main && git merge origin/main`, nie force/rebase.
- **Ändern/Rendern nur über Actions.** Claude-Läufe führen keinen heruntergeladenen Code aus. `render.yml` startet bei JEDEM Push auf `pipeline/**` – Änderungen dort bewusst machen.
- **Livewatch/JasonTheWeen** (`pipeline/clipfabrik/livewatch.py`, `plan/livewatch.json`, `plan/jason*.json`, `clips/live-*`) gehört einer eigenen Session: nicht anfassen, außer Steven sagt es.
- **Alarm-Pflicht:** `stats/alerts.md` ist Schritt 0 für Analyst und Clipping-Agent (Wächter, siehe unten). Offene Punkte dort zuerst.
- Advisor: `.claude/settings.json` → `advisorModel` (Fable läuft nur bis 16.11. → auf `opus` stellen, sobald Fable weg ist).
## Wo liegt was
| Pfad | Zweck |
|---|---|
| `pipeline/gh_jobs.py` → `gh_render.py` → `hyperframes/render_hf.py` (+`build_cd.py`, `words.py`, `cd_template.html`), `tts.py` (Kokoro am_puck), `music.py`, `preflight.py`, `qa.py` | Render-Farm für das tägliche GTA-6-Short (Auftrag `jobs/<name>.json` → `shorts/<name>.mp4/.json`, `shorts/qa/*.png`; `-tt` = TikTok-Kurzfassung aus `tiktok_lines`) |
| `pipeline/clipfabrik/clipfabrik.py` | **Der** Clip-Schneider für Kampagnen (nicht „make_clips"): `clipjobs/<name>.json` → `clips/<name>/<name>_<id>.mp4`, `qa/*.jpg`, `result.json`, `scan/` (Phase 1). Layouts `native` (Standard-Stil), `split` (Facecam), `full`, `framed` |
| `pipeline/stats/stats.py` | Views eigener Posts → `stats/latest.json/.md`, `history.json` |
| `pipeline/trendscout/`, `pipeline/kampagnen/`, `pipeline/reflab/` | → `trends/latest.*`, `campaigns/latest.*` (Content-Rewards-Radar), `refs/latest/report.json` |
| `pipeline/ai_assets.py`, `pipeline/scenes3d/` | Higgsfield-Bestand sichern / eigene 3D-Szenen → `assets/ai_library.json` (Higgsfield gekündigt: nichts Neues) |
| `pipeline/clipfabrik/camtest.py` | Facecam-Erkennungstest (von Hand) |
| `waechter/waechter.py`, `tests/` | Wächter, Smoke-Tests |
| **Veraltet, nicht benutzen:** `pipeline/render.py`, `render_clips.py` (alte Renderer), `campaign_clip.py`, `campaign_scan.py` (Vorläufer der Clipfabrik), `plan.py` (nur Plan-Helfer) | |
| `plan/countdown_plan.json` | Themen/Skripte der Tages-Shorts bis 26.11.; `jobs/` = daraus gebaute Aufträge (`-ai` = Variante mit AI-Bildern) |
## Actions (UTC; Berlin = UTC+1)
| Action | Wann | Ergebnis |
|---|---|---|
| `render` | alle 15 Min + Push `jobs/`, `pipeline/` | `shorts/<name>.*` (3 Versuche, dann gibt sie **still** auf) |
| `clipfabrik` | :07/:37 + Push `clipjobs/`, `pipeline/clipfabrik/` | `clips/<name>/…` (max. 4 Aufträge/Lauf; Drive-Ordner `clipjob-*.json` wird per Regex gelesen) |
| `stats` | 05:17, 11:17, 16:17 | `stats/latest.*` (Berlin 06:17, 12:17, 17:17 – **vor** dem 18:00-Post) |
| `trendscout` | 04:43, 10:43, 15:43, 19:43 | `trends/latest.*` (Reddit, Kick, GTA-6-News, Rockstar-YouTube) |
| `kampagnen` | 05:27, 11:27, 17:27 | `campaigns/latest.*` |
| `reflab` | Mo 03:23 | `refs/latest/` |
| `waechter` | 05:47, 11:37 (+ Push auf seine Dateien) | `stats/alerts.md` + Issues „alarm" |
| `tests` | jeder Push | rot/grün |
| `livewatch` (AUS), `livewatch-replay`, `camtest`, `ai_assets`, `scenes3d`, `tools-check` | Sonderfälle | nicht ohne Auftrag anfassen |
Geplante Claude-Aufgaben (keine Actions): Produzent 07:47, Clipping-Agent 12:47, Deal-Radar 05:13, Reel-Scout Mo 06:41, Analyst So 18:13, Stratege So 19:41 (Berlin).
## Was steuert `plan/*.json`
`stats.json` Konten (YouTube-ID, TikTok-Name) + Kampagnen (`match`-Hashtags, `min_views`) · `kampagnen.json` `joined` (beigetretene Kampagnen), Radar-Schwellen · `trendscout.json` Feeds/Subreddits/Kick-Kanäle · `reflab.json` Referenz-Konten · `waechter.json` Postzeit-Regeln, Schwellen, Ausnahmen, Kampagnen-Erwartung · `eingereicht.json` Einreich-Notiz · `gta6_launch.json` Streamer-Kandidaten (`enabled:false`) · `countdown_plan.json` Tages-Shorts · `camtest.json`, `higgsfield_shotlist.json` (alt). Neue Kampagne = Zeile in `stats.json`, `kampagnen.json` (`joined`) und `waechter.json`.
## Daten lesen statt rechnen (Raw-URL `https://raw.githubusercontent.com/pusnikg-media/pusnikg-media/main/<pfad>`)
`stats/alerts.md` Probleme · `stats/latest.md` Views, „Schwelle erreicht" · `trends/latest.md` Trends + GTA-6-News · `campaigns/latest.md` offene Kampagnen · `shorts/<name>.json` / `clips/<name>/result.json` Render-Ergebnis (`ok`, `error`, `hints`).
## Typische Fallen
1. **Grün ≠ gut:** Actions laufen bei Fehlern grün (`|| true`, `|| exit 0`). Wahrheit steht in `ok`/`attempts` der Ergebnis-JSONs und im `updated` der Ausgaben. Neu rendern: `shorts/<name>.json` löschen; Clip: `rev` im Clip hochzählen.
2. **Auftragsfelder ändern = Neurender:** Jede Änderung an `source/pill/fix/clips/layout/…` ändert die Signatur (`job_sig`) → alles neu (Zeit, Repo-Größe). Auftrags-`name` = Dateiname; Clip-ID `[A-Za-z0-9_-]`; Clip ≥ `min_len` (10 s), `hook` 0,8–5 s.
3. **Postzeiten:** Tages-Short 18:00. Kampagnen-Clips höchstens 2 pro Konto/Tag, nie um 18:00, **nie nach 19:30 (Europe/Berlin)**. Woche 16.–22.11. nur 09:00/09:30 (Spätschicht). Veröffentlichen nur mit Stevens „ja". YouTube über vidIQ: sofort hochgeladen, bis zur Planzeit PRIVAT (kein Fehler).
4. **TikTok bei Kampagnen-Clips:** vidIQ-Entwurf immer `brandContent: true`, `privacyLevel: PUBLIC_TO_EVERYONE`, `allowComment: true`, `isAiGenerated: false`, `musicUsageConfirmed: true`. Tages-Short: **kein** brandContent, `isAiGenerated: true`. Genau 5 Hashtags.
5. **Nur vidIQ postet** (`vidiq_social_post_*`, 0 Credits). Metricool/Buffer/Zapier-YouTube nicht. vidIQ-Credits 9 bis 01.12.: nichts, was Credits kostet. Higgsfield gekündigt.
6. **Einreichen** bei Content Rewards binnen 30 Min nach Veröffentlichung (Whop nur Auszahlung). Danach Post-URL in `plan/eingereicht.json` → sonst meldet der Wächter es.
7. **Stats-Lücken:** Instagram fehlt (→ `vidiq_instagram_owner_insights`, 0 Credits); privat geplante YouTube-Videos fehlen; Kampagnen-Zuordnung nur per Hashtag in `stats.json`; `min_views` meist `null`.
8. **Clip-Stil:** `layout: native` + EIN Kontextsatz (`caption`, 9–15 Wörter, Name zuerst, „…" + 1–2 Emojis), Originalton, 10–35 s. `split`: bei GTA-Material `facecam` von Hand `[x,y,b,h]` setzen (`auto` nimmt Spielfiguren), sonst fällt der Clip **still** auf `native` zurück (Prüfen: `layout` in `result.json`).
9. **Quellen:** YouTube-Links werden von Cloud-Servern oft geblockt → Drive-/Direktlink (Steven lädt in den Drive-Ordner „Pusnik G Render-Aufträge", „Jeder mit dem Link"). GTA-6-Kampagnen nur mit Rechteinhaber/Partner. Preme/Drake und Gattouz: nicht machen.
10. **Pushes:** Livewatch pusht alle 1–2 Min inkl. `raw_*.mp4` (Repo wächst, Wächter prüft die Größe). Bot-Pushes lösen keine Tests aus.
11. **Nicht getestet** (nur im Action-Log sichtbar): Whisper, Kokoro-TTS, HyperFrames-Render (`npx`), `facecam: auto`/`track` (braucht OpenCV), echte Netzabfragen (Drive, Reddit, Kick, TikTok, Content Rewards).
## Wächter (`waechter/waechter.py`, `plan/waechter.json`)
Vergleicht `jobs/*.json`, `clips/*/result.json`, Kampagnen-Posts mit `stats/latest.json`; prüft Alter von stats/trends/campaigns, den letzten Lauf der Actions, 19:30-Regel, Einreich-Notiz, Repo-Größe. Unlesbare Plattform = ein „Daten"-Alarm statt „nicht live"; ein Tag wird erst 2 h nach der Planzeit beurteilt. Von Hand/lokal: `python3 waechter/waechter.py --dry --no-api`. Ausnahme eintragen: `plan/waechter.json` → `ignorieren`. Details: `claude/haertung-stand.md`.
