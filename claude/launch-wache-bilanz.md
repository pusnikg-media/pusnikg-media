# Launch-Wache Bilanz – Clix GTA VI Marathon (Do 19.11.2026), Stand 08:55 Berlin

**Posts: 0.** Links: keine. Kein Clip hielt die Prüfung (Clix klar im Fokus + sehenswerter GTA-Moment).

## Was passiert ist
- Clix streamt seit gestern ca. 11:34 Berlin (VOD 2932204601). Bis ca. 07:30 Berlin war er **IRL** (Nachtfahrt, Haus, Besuch, Lacy). GTA 6 lief nur von ca. **07:40 bis 08:15 Berlin** (Bootsfahrt, Story-Dialoge, Karte). Um 08:16 ging er schlafen: Bildschirm „Waking up in 07:13:55“ → **wacht ca. 15:30 Berlin auf**, also nach 12:30 (Befugnis) und nach `until` (12:45).
- Livewatch war nicht kaputt: 05:45–07:51 UTC… (Berlin 06:45–08:51) nur 1 Treffer bei 4,5/2,5/9; nach Senkung auf 3,0/1,8/7 kamen im Minutentakt Kandidaten.
- **19 Kandidaten geprüft, 0 postbar:** 7 IRL ohne GTA, 6 Story-Cutscene/Boot mit Spieldialog ohne Clix-Reaktion, 2 Menü/Karte, 2 Smalltalk, 2 Schlafengehen. Keine Marker-Lücke: jeder Clip hat `clips/live-clix/posted/<id>.json` (skipped + Grund).
- Notlösung „Twitch-Clips der Zuschauer“: Clip-Liste liefert 0 (GQL leer/geblockt aus dem Runner), mein direkter Abruf aus der Sandbox wurde vom System gesperrt (nicht umgangen). Zuschauer-Clips wären außerdem Reposts.

## Was gebaut wurde (siehe `claude/livewatch-stand.md`)
Schwellen gesenkt, Chat-Wörter, Stimm-Ausbruch, Zuschauer-Clip-Cluster, Sicherheitsnetz (alle in `livewatch.py` v0.7, 16 neue Tests), Replay mit Kanal statt VOD-Link, ISO-Startzeit, `replay_info.json`.

## Was Steven entscheiden kann
1. Livewatch bis ca. 15:30–19:00 Berlin verlängern (`until` in `plan/livewatch.json`), damit der Wiederbeginn des Marathons gefangen wird. Posten dann nur mit seinem „ja“ (Befugnis endet 12:30; 19:30-Regel).
2. Oder niedrigere Qualitätslatte: bestes vorhandenes GTA-Material wäre `20261119-065104` (Clix: „play the game one or two hours … 12 hour straight“ auf GTA-Sonnenuntergang) – ich habe es **nicht** gepostet.
