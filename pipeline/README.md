# Pusnik G Short-Pipeline (0 €)
1. `bash pipeline/setup.sh` (v2 seit 07.11.: espeak-ng per apt statt aus Quellcode, ca. 20 s)
2. `script.txt` – ein Satz pro Zeile (Englisch, letzte Zeile = CTA)
3. `python3 pipeline/tts.py script.txt vo am_puck 1.0` (Stimme: Kokoro am_puck, nie schneller als 1.0)
4. `python3 pipeline/music.py <sek> music.wav <seed>` (eigene Synthwave-Musik, lizenzfrei)
5. `job.json` (timing, music, out, day_label, hook, big, big_sub, cta) → `python3 pipeline/render.py job.json`
6. QA: `python3 pipeline/qa.py out.mp4` (ffprobe h264+aac 1080x1920, ebur128 ≈ -14 LUFS, kein Silence > 1 s, 3 Frames als PNG – Frame 0 zeigt Hook)
7. MP4 nach `shorts/` committen + pushen → URL: https://raw.githubusercontent.com/pusnikg-media/pusnikg-media/main/shorts/<datei>.mp4

## Preflight + QA (seit 07.11., spart Render-Zeit und Tokens)
- `python3 pipeline/preflight.py job.json` → `PREFLIGHT_OK …` oder `PREFLIGHT_FAIL` + genaue Liste (Exit 1). Prüft timing.json/WAVs, Anzahl `shots` = Skriptzeilen, jeder Clip existiert, dekodiert und ist lang genug für `start` + Slot (sonst friert das Bild ein), Musik, `card.line`/`card.word`, `punch`, Länge 18–35 s. Läuft automatisch am Anfang von `render_hf.py`.
- `python3 pipeline/qa.py out.mp4` → `QA_OK …` oder `QA_FAIL` + Liste (Exit 1): h264 1080x1920 + aac, A/V-Länge gleich, 18–35 s, −16…−12 LUFS, keine Stille > 1 s, kein Standbild > 2,5 s, Frame 0 nicht schwarz. Legt `out_qa_0.png`, `out_qa_mid.png`, `out_qa_end.png` neben das Video → diese 3 Bilder ansehen.
- Alle Pfade in job.json sind relativ zum job.json-Ordner. tts.py löscht ein altes `words.json`; Fehler enden immer mit `FAIL…`/`… FAIL` statt mit einem kaputten Video.

## Renderer v3 HyperFrames (STANDARD seit 04.11. abends, von Steven freigegeben) – `pipeline/hyperframes/render_hf.py`
`python3 pipeline/hyperframes/render_hf.py job.json` (Render ca. 3–4 Min, 0 Credits)
job.json: `vo_dir`, `shots` (pro Skriptzeile Liste `{"file","start"}`, Schnitte ≤2,3 s, Dateinamen eindeutig), `day`, optional `hook_big` (Standard = day), `hook_mid` ("DAYS LEFT"), `hook_sub` (Neugier-Zeile unter der Zahl, max. 22 Zeichen, seit 09.11. ab Frame 0 sichtbar), `badge`, `card` (Slam-Karte auf ein Schlüsselwort: `{"line","word","top","big","bottom"}`, z. B. NOV/19/2026 beim Wort „November"), `punch` (Liste von Wortanfängen, z. B. ["downgrade","console"]: Zoom-Punch 1,14→1 + kurzer Flash auf diesen Wörtern), `music`, `music_start`, `music_db` (−9), `out`.
Kann: wortgenaue Karaoke-Untertitel (Whisper base.en, auf echte Sprechzeit kalibriert, aktives Wort gelb + Pop), Riesen-Hook mit Pink-Glow im Frame 0, Slam-Karte, springender FOLLOW-Button auf der letzten Zeile, Ken-Burns-Zoom, Weiß-Flash pro Schnitt, Fortschrittsbalken, Stimme EQ+Kompressor, Musik geloopt + per Sidechain geduckt, −14 LUFS.
Dateien: `words.py` (Wort-Timing), `build_cd.py` (HTML-Komposition), `cd_template.html` (Look), `gsap.min.js`.

## Clip-Renderer v2 (Fallback) – `pipeline/render_clips.py`
`python3 pipeline/render_clips.py job.json`
job.json: `vo_dir` (tts.py-Ordner), `shots` (pro Skriptzeile Liste von `{"file","start"}`), `music` (Datei, geloopt), `music_start` (Intro überspringen, s), `music_db` (Standard −12, wird unter der Stimme automatisch abgesenkt), `badge` ("GTA 6 • DAY X"), `hook` (max. 6 Wörter), `out`, optional `gap` 0.22, `tail` 0.6, `max_shot` 2.3.
Kann: Anton-Font (pipeline/fonts), Karaoke-Untertitel (aktives Wort gelb), weißer Flash bei jedem Schnitt, pinker Fortschrittsbalken, automatische Schnitte ≤2,3 s mit wechselndem Zoom/Pan, Stimme EQ+Kompressor, Musik per Sidechain geduckt.
Musik: jeden Tag ein anderer Track – benutzte Tracks in `pipeline/music_log.txt` (Datum | Titel | Quelle) eintragen und vorher prüfen.

## Render-Farm (STANDARD seit 08.11.) – GitHub Action `.github/workflows/render.yml`
Geplante Claude-Läufe dürfen keinen heruntergeladenen Code ausführen (Sicherheitsprüfung, gestoppt am 07./08.11.). Deshalb rendert ein kostenloser GitHub-Runner:
- Auftrag = JSON im Format von `pipeline/gh_render.py` (script, shots mit Clip-URLs, music, hook_*, badge, card, punch). Quellen: `jobs/<name>.json` im Repo (im Chat angelegt) oder `job-<name>.json` im Drive-Ordner „Pusnik G Render-Aufträge" (ID 1sZgGx8xmJ5OX5UcGUhZn9u_UzenRGYwF, muss „Jeder mit dem Link" lesbar sein; vom geplanten Produzenten angelegt).
- Die Action läuft bei Push auf jobs/ und alle 15 Min (Cron), rendert offene Aufträge (TTS → HyperFrames v3, Fallback v2 → qa.py) und committet `shorts/<name>.mp4`, `shorts/qa/<name>_qa_*.png` und das Ergebnis `shorts/<name>.json` ({ok, urls.video, urls.pngs, error, attempts}). Fehlgeschlagene Aufträge werden bis zu 3-mal wiederholt. Seit 09.11. wirft gh_render.py unscharfe Clips raus (Laplace-Varianz < 15 bei 270x480), solange die Zeile noch einen anderen Clip hat. Neu rendern: `shorts/<name>.json` löschen und pushen. TikTok-Kurzfassung (seit 09.11.): Feld `tiktok_lines` (Skriptzeilen-Indizes, z. B. [0,1,4,5]) im Auftrag → die Action rendert zusätzlich `<name>-tt` (8–20 s, Karte nur wenn ihre Zeile drin ist, Punch-Wörter gefiltert) → `shorts/<name>-tt.mp4`/`.json`.
- Der Produzent liest nur noch: `https://raw.githubusercontent.com/pusnikg-media/pusnikg-media/main/shorts/<name>.json`, lädt Video + PNGs, prüft und plant in Metricool ein.

## Clipfabrik v2 (seit 14.11.) – GitHub Action `.github/workflows/clipfabrik.yml`, Skript `pipeline/clipfabrik/clipfabrik.py`
Kampagnen-Footage → fertige 9:16-Clips (nur Originalton), ohne dass ein Claude-Lauf Code ausführt. Läuft bei Push auf `clipjobs/` und alle 30 Min.
- Auftrag: `clipjobs/<name>.json` im Repo oder `clipjob-<name>.json` im Drive-Ordner „Pusnik G Render-Aufträge". Felder: `name`, `source` (https-URL der offiziellen Datei: Release-Asset, öffentlicher Drive-Link oder Direktlink), optional `pill` (gelbe Pflichtzeile), `fix` (verhörte Namen), `min_len` (Standard 10), `clips` `[{"id","a","b","title", optional "wide","pill","captions","rev"}]`.
- Phase 1 (ohne `clips`): `clips/<name>/scan/scan.json` (Sätze mit Zeiten, Schnitte, Kandidaten 10–24 s an Satzgrenzen), `words.json`, `cand_XX.jpg` (4 Bilder je Kandidat – ansehen, dann ehrlichen Titel schreiben).
- Phase 2 (mit `clips`): `clips/<name>/<name>_<id>.mp4`, Vorschaubild `qa/<name>_<id>.jpg`, `clips/<name>/result.json` (`ok`, `phase`, pro Clip `url`). Unveränderte Clips werden nicht neu gerendert; aus dem Auftrag entfernte Clips werden gelöscht. Abgelehnte Aufträge (Clip < `min_len`, außerhalb der Quelle, Titel zu lang) stehen mit Grund in `error`.
- Titel: Teil vor „:" gelb; max. ca. 32 Zeichen. `wide: true` zeigt 75 % der Bildbreite (für Texttafeln).
- **v3 IRL (14.11.):** `source` darf auch eine VOD-Seite sein (Twitch, Kick, YouTube, TikTok, X, Rumble) → yt-dlp (Scan in 480p, Render in `max_height`, Standard 1080p, ab 3 h 720p). YouTube blockt Cloud-Server oft → dann Drive-/Direktlink nehmen.
  Quellen > 15 Min: Hotspot-Scan – Lautstärke-Spitzen gegen den gleitenden 3-Min-Grundpegel (Schreien, Lachen, Menge) + YouTube-„Most replayed“, nur diese Stellen werden transkribiert. scan.json: `mode: hotspots`, `regions`, Kandidaten mit `hype` (dB über Grundpegel) und `peak_in`. `hot_k` = Anzahl Stellen (Standard 14).
  `layout: "full"` = Vollbild-9:16 (ohne Unschärferand, Titel oben mit dunklem Verlauf, Untertitel unteres Drittel); `track: true` = Ausschnitt folgt dem größten Gesicht (OpenCV, ruhige Kamera mit Totzone; ohne Gesicht Mitte). Beides auch pro Clip. IRL-Standard: `"layout": "full", "track": true`.
