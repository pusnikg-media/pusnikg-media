# Pusnik G Short-Pipeline (0 €)
1. `bash pipeline/setup.sh`
2. `script.txt` – ein Satz pro Zeile (Englisch, letzte Zeile = CTA)
3. `python3 pipeline/tts.py script.txt vo am_puck 1.0` (Stimme: Kokoro am_puck, nie schneller als 1.0)
4. `python3 pipeline/music.py <sek> music.wav <seed>` (eigene Synthwave-Musik, lizenzfrei)
5. `job.json` (timing, music, out, day_label, hook, big, big_sub, cta) → `python3 pipeline/render.py job.json`
6. QA: ffprobe (h264+aac, 1080x1920), ebur128 ≈ -14 LUFS, kein Silence > 1 s, Frame 0 zeigt Hook
7. MP4 nach `shorts/` committen + pushen → URL: https://raw.githubusercontent.com/pusnikg-media/pusnikg-media/main/shorts/<datei>.mp4

## Renderer v3 HyperFrames (STANDARD seit 04.11. abends, von Steven freigegeben) – `pipeline/hyperframes/render_hf.py`
`python3 pipeline/hyperframes/render_hf.py job.json` (Render ca. 3–4 Min, 0 Credits)
job.json: `vo_dir`, `shots` (pro Skriptzeile Liste `{"file","start"}`, Schnitte ≤2,3 s, Dateinamen eindeutig), `day`, optional `hook_big` (Standard = day), `hook_mid` ("DAYS LEFT"), `hook_sub` (kleine Zeile, erscheint beim 3. Wort), `badge`, `card` (Slam-Karte auf ein Schlüsselwort: `{"line","word","top","big","bottom"}`, z. B. NOV/19/2026 beim Wort „November"), `punch` (Liste von Wortanfängen, z. B. ["downgrade","console"]: Zoom-Punch 1,14→1 + kurzer Flash auf diesen Wörtern), `music`, `music_start`, `music_db` (−9), `out`.
Kann: wortgenaue Karaoke-Untertitel (Whisper base.en, auf echte Sprechzeit kalibriert, aktives Wort gelb + Pop), Riesen-Hook mit Pink-Glow im Frame 0, Slam-Karte, springender FOLLOW-Button auf der letzten Zeile, Ken-Burns-Zoom, Weiß-Flash pro Schnitt, Fortschrittsbalken, Stimme EQ+Kompressor, Musik geloopt + per Sidechain geduckt, −14 LUFS.
Dateien: `words.py` (Wort-Timing), `build_cd.py` (HTML-Komposition), `cd_template.html` (Look), `gsap.min.js`.

## Clip-Renderer v2 (Fallback) – `pipeline/render_clips.py`
`python3 pipeline/render_clips.py job.json`
job.json: `vo_dir` (tts.py-Ordner), `shots` (pro Skriptzeile Liste von `{"file","start"}`), `music` (Datei, geloopt), `music_start` (Intro überspringen, s), `music_db` (Standard −12, wird unter der Stimme automatisch abgesenkt), `badge` ("GTA 6 • DAY X"), `hook` (max. 6 Wörter), `out`, optional `gap` 0.22, `tail` 0.6, `max_shot` 2.3.
Kann: Anton-Font (pipeline/fonts), Karaoke-Untertitel (aktives Wort gelb), weißer Flash bei jedem Schnitt, pinker Fortschrittsbalken, automatische Schnitte ≤2,3 s mit wechselndem Zoom/Pan, Stimme EQ+Kompressor, Musik per Sidechain geduckt.
Musik: jeden Tag ein anderer Track – benutzte Tracks in `pipeline/music_log.txt` (Datum | Titel | Quelle) eintragen und vorher prüfen.
