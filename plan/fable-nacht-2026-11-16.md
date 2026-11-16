# Fable-Nacht 16.11.2026 – Ergebnis

Stand: 16.11. ca. 21:00 Berlin. Alles nach `main` gemergt (Action `tests` auf main grün, lokal 273 Tests grün). Nichts gepostet, keine Credits, kein Trigger geändert. Kleine Commits auf `fable-nacht`/`main`.

## Zusammenfassung
- **Fertig:**
  - Block 1: 5 wahrscheinliche Ausfälle gefunden; Livewatch-Warten, Trendscout/Kampagnen-Publish, OpenCV-Rückfall, Wächter-nach-stats und Postplan-Regeln per Code gefixt und auf dem Runner bestätigt; Release-Check/Vorlauf per Runbook.
  - Block 3: `tests/clip_regression.py` (Video-/Audio-Hash + Sync) und Review der Clipfabrik mit 5 behobenen Fehlern.
  - Block 4: Zahlen-Diagnose, 3 Experimente mit Prüfer (Analyst) in `plan/team_state.md`.
  - Block 5: 6 überarbeitete Prompts + Launch-Runbook in `plan/prompts/` (Produzent und Clipping-Agent gegengelesen).
- **Block 2 nur teilweise:** Pipeline läuft Ende-zu-Ende live (2 Läufe auf dem Runner, 4 Clips), aber **0 von 4 Clips brauchbar** (wie schon 0 von 4 im VOD-Training davor). Am Donnerstag liefert Livewatch Kandidaten, keine postbaren Clips; jeder braucht Bildkontrolle + Kontextsatz. Detektion nicht verbessert gemessen (kein Replay-Vergleich).
- **Offen:**
  - Alte Prompts nicht gesichert (Subagent-Lauf vom System gestoppt) → vor dem Überschreiben selbst kopieren.
  - Review-Reste Clipfabrik: Hochformat-Quelle wird in native/framed beschnitten; Emoji-Darstellung (Hauttöne/Flaggen); `probe()` bei `r_frame_rate 0/0`; Livewatch-Fallbackschnitt nicht an Satzgrenzen.
  - Ohne eigenen Test: Livewatch-Aufwärmzeit, Wortsortierung der `words.json`, Inbox-Bremse nur als Funktion getestet, `loop()` nur live.
  - Prompts: Analyst, Stratege, Deal-Radar, Reel-Scout nicht gegengelesen; Liste nicht eingearbeiteter Funde in `plan/prompts/README.md`.
  - Livewatch: Werbepausen/Watchdog live ungeprüft; Kick ohne Chat-Signal; Golden-Hashes nur für lokalen ffmpeg-Build.
  - Stevens Nachname stand in den neuen Prompt-Dateien und ist in der Git-Historie (öffentliches Repo) der ersten Commits; in den Dateien jetzt entfernt.
  - vidIQ-Liste (lesend): YouTube 17.11. fehlt vermutlich nur, weil der Upload vor dem Abfragefenster lag (wie der 16.11., der laut Wächter live ist); nicht erneut geprüft.
- **Steven muss selbst (3 Punkte):**
  1. **Prompts einspielen und drei Entscheidungen im Chat** (`plan/prompts/README.md`): Analyst, Stratege, Deal-Radar, Reel-Scout, Clipping-Agent jederzeit (Analyst vor So 22.11. 18:13), **Produzent erst nach dem Lauf Di 17.11. 07:47, vor Mi 18.11. 07:47**. Entscheiden: (a) „Dauer-Freigabe gilt“ oder „nur mit ja“ (Schalter in team_state, aktuell „nicht bestätigt“), (b) Zusatz-Shorts nach 19:30 („Review-Roundup 2. Versuch“ Mi 18.11. 21:17, „Rekord-Check“ Fr 20.11. 20:30) erlauben oder abschalten, (c) die Warzone-Erinnerungen D/E/F sagen „Whop“ (richtig: Content Rewards).
  2. **Do 19.11. bis 11:30** (danach 12:00–21:30 nicht erreichbar), Runbook Zeile „bis 11:30“: Release-Check (Verschiebung in `trends/latest.md`? dann „raus“), Post 18:00 in vidIQ `scheduled`?, „Livewatch an“ nur mit Kampagne/Erlaubnis für den Streamer.
  3. **Einreichen abhaken** (GitHub-App, Issue „Einreichen“): ab Di jeden Morgen 09:00/09:30; die Warzone-Slots 17.11. 15:00/19:30 und 18.11. 19:30 liegen in der Schicht (30-Min-Frist nicht haltbar, Wächter-Alarm „Einreichen“ zu erwarten).

## Block 4 – Zahlen-Diagnose (fertig, Details: `plan/zahlen-diagnose-2026-11-16.md`)
- TikTok Pusnik G: harte Decke bei ca. 250 Views (36 von 43 Posts bei 150–450, Median 258, keiner über 2.500). Uhrzeit/Format ohne erkennbaren Effekt.
- Verdient: realistisch 0 $. Nötig sind 2.500–5.000 Views pro Clip, unser Bestwert liegt bei 244–277.
- Alter gegen viraler Stil: nicht messbar (n=0 im neuen Stil).
- Experimente Launch-Woche: siehe Datei; Stopp-Regel: scheitern Exp. 1 und 2, Clipping einstellen.

## Block 1 – Launch-Pre-Mortem (fertig; Beleg: Actions-Läufe 13.–16.11., Wächter-Zeitreise, Code)
Die 5 wahrscheinlichsten Ausfälle und was damit geschah:
1. **Crons kommen 50–90 Min zu spät, render/clipfabrik nur ca. 1×/h statt alle 15/30 Min** (Lücken bis 206 Min; stats-Lauf "vor dem 18:00-Post" lief 18:31). Folge: ein Drive-Auftrag kann 3 h liegen, der Wächter urteilt auf alten Zahlen. **Maßnahme:** `waechter.yml` läuft jetzt zusätzlich nach JEDEM stats-Lauf (`workflow_run`). Runbook: Aufträge ≥ 4 h vor der Postzeit, Launch-Tag nichts auf den Cron verlassen, Action von Hand starten.
2. **Livewatch sieht den Streamstart nicht** (Cron-Lücke bis 197 Min; früher beendete ein Offline-Lauf sofort). **Fix v0.5:** `watch()` fragt bei Offline alle 90 s (`poll_seconds`) nach bis `max_minutes`/`until`; 4 neue Tests.
3. **trendscout/kampagnen scrapen bei jeder Push-Kollision neu** (trendscout 11,7 von 15 Min Limit am 16.11., danach still grün ohne Veröffentlichung). **Fix:** einmal scrapen, nur Publish wiederholen (6×), danach ROT statt still grün (Wächter sieht es). Schleife lokal gegen Bare-Repo mit Konflikt getestet.
4. **Release-Annahme im Vorrat:** der Short vom 19.11. sagt "GTA 6 is finally out". Verschiebt sich der Release, wäre das ein falscher, nicht rücknehmbarer Post. **Maßnahme:** Release-Check im Produzent-Prompt (täglich) und im Runbook (Steven bis 11:30). Kein Code (inhaltlich).
5. **OpenCV ≥ 5 hat keine Gesichtserkennung** (lokal fiel `facecam: auto` damit um): Workflows sind auf `<5` festgenagelt, aber ein Absturz statt Rückfall wäre teuer. **Fix:** clipfabrik fällt jetzt auf native/Mitte zurück.
Zusätzlich: Wächter prüft den **Postplan vorbeugend** (nach 19:30, 18:00, > 2 pro Konto/Tag, derselbe Clip doppelt; 2 Tests). Warzone-Slots 17.11. 15:00/19:30 und 18.11. 19:30 liegen in Stevens Schicht (Einreichen-Frist nicht haltbar; nicht änderbar, nur dokumentiert).
Nicht geändert (bewusst): `|| exit 0` bei stats (Selbstheilung 4×/Tag), render/clipfabrik-Push-Schleifen (selbstheilend: Auftrag bleibt offen, nächster Lauf holt ihn). Repo: `.git` 2,5 GiB (Grenze Wächter 3500 MB), `raw_*.mp4` aus Livewatch bleiben ein Wachstumsrisiko → siehe Block 2.

## Block 2 – Livewatch (teilweise)
- Testmodus: `livewatch.yml` per `workflow_dispatch` mit `urls` (Komma-Liste), `minutes`, `profile` – ignoriert `enabled`, ändert main nicht.
- Echtlauf 16.11. 19:45 Berlin auf dem Runner: yt-dlp erreicht Twitch, Offline-Erkennung sauber ("not currently live" für xqc, kaicenat, caseoh_, jynxzi, tarik); **kein Kanal live → keine Aufnahme getestet**. Aufnahme live bereits am 15.11. (robcdee) getestet; Werbepausen/Watchdog bleiben live ungeprüft.

### Block 2 – Ergebnis Live-Lauf (Nachtrag 20:20)
- Testlauf (Eingabe `urls`: 14 Twitch-Kanäle, 90 Min, Profil gaming) auf main: Der Runner fand **zackrawrr live**, nahm auf, erkannte 3 Treffer und rendert 3 fertige 9:16-Clips (1080x1920, Ton, 13–16 s) samt `raw_*.mp4`, QA-Bild und `inbox.json`, Veröffentlichung im Repo 6–10 Min nach Aufnahmebeginn. Pipeline Ende-zu-Ende **bestätigt** (Twitch-Zugriff, HLS-Aufnahme, Chat-IRC, Whisper, Clipfabrik, Push). Lauf danach abgebrochen, Clips gelöscht (bleiben in der Git-Historie, Repo ist öffentlich).
- **Qualität schlecht:** 3 Clips in den ersten 9 Minuten (erwartet ca. 0,5 bei 3/h), alle drei Alltagsmomente (Browser-Fenster, Gespräch), Chat-Verhältnis x3,07–x3,77 knapp über der Schwelle 3,0. Peaks bei Aufnahmesekunde 272/494/755. **Zweiter Live-Lauf auf dem Endstand** (19:29 UTC, mit Aufwärmzeit 480 s, Lückenprüfung, `snap_to_words`, `-ac 2`): 1 Clip nach 10 Min, Chat x5,74 (über der irl-Schwelle 4,5), Inhalt vorgelesene Politik-Rede. Endstand-Code läuft live fehlerfrei (Aufnahme → Chat → Whisper → Schnitt → Render 1080x1920 → Push), **0 von 4 Clips brauchbar**: Chat-Spitze/Lautstärke sagen nichts über Qualität, Livewatch bleibt ein Kandidatenfinder mit Pflicht-Bildkontrolle. Für Talk-Streams Profil `irl` (4,5/2,5) nehmen. Nicht nachgemessen.
- Detektion gelesen: Chat-Treffer rückt den Moment um die Verzögerung zurück (lauteste Sekunde in den 28 s vor der Chat-Spitze, Schnitt −30/+12 s, gemessene Verzögerung 7–25 s → passt). Bei Chat-Treffern entscheidet nur das Chat-Verhältnis; `hype ≥ 9` wird dort auf `min_hype` gesetzt und trennt nichts. **Ohne Chat (Kick, oder IRC fällt aus) entscheidet allein die Lautstärke gegen 9 dB und die ist bei lauten Streams fast immer erfüllt → viele Fehlalarme.** Deshalb: Kick-Streamer nur mit `min_hype` 14 / `per_hour` 2 oder Twitch nutzen (Hinweis in `plan/gta6_launch.json`).
- Neu: Wartet auf den Streamstart (v0.5), Inbox-Bremse (max. 12 ungepostete Clips pro 24 h, ca. 120 MB/Tag), Aufnahmelücke → Clip verworfen statt falscher Timecode, Aufwärmzeit (noch nicht live gelaufen), Testmodus per `workflow_dispatch`. Alles in `pipeline/README.md` („Livewatch v0.5").
- Am Donnerstag nur noch: Streamer in `plan/livewatch.json` eintragen + `enabled: true` (+ `until`). Vorher sinnvoll: Testmodus mit dem Kanal (Workflow `livewatch`, Eingaben `urls`/`minutes`/`profile`).

## Block 3 – Ergebnis
- `tests/clip_regression.py` (+ `test_clip_regression.py`, Golden `tests/fixtures/clip_hashes.json`): 9 Layout-Fälle + Quelle ohne Ton; Hash über dekodierte Frames/Ton, Sync < 0,1 s, Frameanzahl. Vorher/Nachher: `save VORHER` → ändern → `compare VORHER`. Läuft in der Action `tests` (nur Struktur auf dem Runner-ffmpeg; Golden nur lokaler Build).
- Review (Subagent, jeder Befund mit Experiment): **behoben** (nur NEUE Clips betroffen, `job_sig` unverändert, nichts rendert neu): (1) Livewatch-Schnitt bei Aufnahmelücke gab stillen Fehl-Timecode; (2) Schnitt mitten im Wort / Fade-out (0,35 s) fraß das letzte Wort (6 von 11 echten Agent-Clips betroffen: tjr4 D_test/E_seats, tjr5 A_key/B_seat/C_worst/E_outro) → `snap_to_words`; (3) `words.json` aus Hotspot-Scans war nicht zeitsortiert; (4) Mehrkanal-Quellen (5.1) → jetzt Stereo (`-ac 2`; Golden-Argumente angepasst, Bild-Hashes identisch); (6) `fix_word` mit Anführungszeichen/Possessiv/Groß-Klein. Ton-Bild-Sync, Untertitel-Timing, Hook-Teaser, Quelle ohne Ton, VFR, andere Seitenverhältnisse: ohne Befund.
- **Offen (nicht behoben, belegt):** Hochformat-Quelle in `native`/`framed` wird auf die Mitte beschnitten (Doku sagt „nichts beschnitten“); `caption_box`: Hauttöne/Flaggen/ZWJ-Emojis falsch, Titel-Schrift ohne ✓★♥; `probe()` bei `r_frame_rate 0/0` falsche Fehlermeldung. **Unsicher:** Livewatch-Fallbackschnitt (`pk-16..pk+8`) nicht an Satzgrenzen; `facecam: auto` bei GTA nur mit 3 GTA-Clips belegt (Schwellen nicht nach Gefühl ändern, CLAUDE.md 13).

## Block 5 – Ergebnis
`plan/prompts/`: `produzent.md`, `clipping-agent.md`, `analyst.md`, `stratege.md`, `deal-radar.md`, `reel-scout.md`, `README.md` (Tabelle, Einspielen, Entscheidungen), `runbook-launch-tag-2026-11-19.md`. Je Datei oben „Befunde zum alten Prompt“. Wichtigste Altlasten: Freigabe-Widerspruch (CLAUDE.md „nie ohne ja“ gegen Dauer-Anweisung), Wächter-Schritt 0 fehlte, Deal-Radar schrieb ins Repo (kein Schreibrecht) und nutzte 7 Suchen/Tag, Stratege nutzte WebFetch statt Radar und Zapier für Zahlen, Experiment-2-Reste im Produzent, „Whop“ in drei Warzone-Erinnerungen, zwei Zusatz-Shorts nach 19:30. Ergänzt von mir: **Release-Check** (Verschiebung des GTA-6-Releases → kein „is out“-Short) im Produzent und im Runbook. Kein Trigger geändert.

### Nachtrag 20:45 – vidIQ lesend (0 Credits, Subagent)
Stand 16.11. abends: Pusnik-G-Tages-Short 17.11. und 18.11. eingeplant (IG/TikTok scheduled, YouTube 18.11. bereits hochgeladen/privat), **19.–21.11. noch nicht** (der Produzent plant immer den ersten freien Tag: am 17.11. den 19.11.). Keine Post nach 19:30, nie mehr als 2 Kampagnen-Posts pro Konto/Tag, keine Entwürfe, keine Doppelten. Folge: **den neuen Produzent-Prompt VOR Di 17.11. 07:47 einspielen** (Release-Check), nicht erst nach dem 20.11. – README/Runbook angepasst; Punkt 1 der Steven-Liste gilt dafür zuerst für den Produzenten.

### Nachtrag 20:50 – Wächter-Kette bestätigt
`stats` von Hand gestartet (19:42 UTC) → `waechter` startete automatisch per `workflow_run` (19:43), schrieb `stats/alerts.md` (20:43 Berlin, „Keine offenen Probleme“) auf main. Neue Trendscout-/Kampagnen-Publish-Schleifen liefen am 18:59 UTC auf main grün mit `PUBLISHED`. Nach den Pipeline-Pushes hat weder `render` noch `clipfabrik` etwas neu gerendert (keine `short:`-/`clipfabrik:`-Commits). Kein `clips/live-*` auf main, `plan/livewatch.json` `enabled: false`. Nicht geprüft: Abbruchfall der neuen Publish-Schleife unter echter Dauerlast (nur Konflikt lokal simuliert).
