# Pusnik G Short-Pipeline (0 €)
1. `bash pipeline/setup.sh`
2. `script.txt` – ein Satz pro Zeile (Englisch, letzte Zeile = CTA)
3. `python3 pipeline/tts.py script.txt vo am_puck 1.0` (Stimme: Kokoro am_puck, nie schneller als 1.0)
4. `python3 pipeline/music.py <sek> music.wav <seed>` (eigene Synthwave-Musik, lizenzfrei)
5. `job.json` (timing, music, out, day_label, hook, big, big_sub, cta) → `python3 pipeline/render.py job.json`
6. QA: ffprobe (h264+aac, 1080x1920), ebur128 ≈ -14 LUFS, kein Silence > 1 s, Frame 0 zeigt Hook
7. MP4 nach `shorts/` committen + pushen → URL: https://raw.githubusercontent.com/pusnikg-media/pusnikg-media/main/shorts/<datei>.mp4
