# Livewatch – Stand 16.11.2026 (Test robcdee live + VOD-Modus mit JasonTheWeen)

## Kurzfassung
- Live-Test mit Twitch-Streamer **robcdee** (Just Chatting, IRL Tokyo, EN, 4.009 Zuschauer; einziger EN-Stream >= 3.000 in IRL/Just Chatting, IRL-Kategorie hatte nur nix/RU 13k, Amouranth 1,4k). Aufnahme + Chat-Signal laufen auf dem Runner.
- **Ergebnis live: 5 Clips, 0 Treffer, 5 Fehlalarme.** Nichts gepostet (Plan A abgebrochen). Gründe unten.
- **Plan B (VOD-Modus) gebaut und getestet** mit JasonTheWeen-VOD vom 13.11. (TwitchCon, 5 h): 3 Fenster à 50-60 Min = 19 Clips, davon 1 sehr brauchbarer (Fotobuch), 2-3 mittelmäßig, Rest Gelaber/Fluchen. Daraus 1 Entwurf (Pusnik IRL), Freigabe steht bei Steven.

## Live-Lauf robcdee (10:43-11:29 UTC, Aufnahme danach hängengeblieben)
| Clip | Signal | Was wirklich war | Urteil |
|---|---|---|---|
| 10:26 | laut 10, Chat x2,33 | Rob erzählt beim Gehen vom Loft | Fehlalarm |
| 10:28 | laut 9, Chat x3,14 | Gehen nachts, redet über Essen | Fehlalarm |
| 10:33 | laut 9, Chat x3,0 | Bits-Alert wird vorgelesen | Fehlalarm |
| 10:36 | laut 9, Chat x3,44 | **Twitch-Werbepause** („Commercial break in progress") | Fehlalarm |
| 11:05 (Lauf 2, min_chat 4,5) | Chat x5,86 | vorgelesener Donation-Alert + „special video", Rob läuft | Fehlalarm |
Lauf 2 sah weitere Chat-Spitzen (x8,9 / x7,1 / x4,67), die alle von Alerts/Donation-Ketten kamen; eine Spitze scheiterte mit „recording for that moment is gone" (Ursache nicht geklärt, 1x).
- Chat-Verzögerung live: Moment lag **18-27 s** vor der Chat-Spitze (Mittel ca. 20 s).
- Verzögerung Moment -> fertiger Clip im Repo: ca. **2-3 Min** (bis zu 60 s bis das Stück voll ist + ca. 55 s Render).
- Robs Stream war ein **Gehen-durch-die-Stadt-POV**: kaum Gesichter, kaum echte Reaktionen. Als Quelle für diese Art Clips ungeeignet. Um ca. 12:00 UTC wechselte er auf World of Warcraft.

## Was am Chat-Signal angepasst werden muss
1. **Chat-Spitzen durch Streamer-Alerts** (Bits, Donations, Subs, Raids, Werbepause) sind der Hauptfehlalarm. Fix-Ideen: Nachrichten mit Bot-/Alert-Muster (Name streamlabs/streamelements/nightbot, „cheered", „subscribed") nicht zählen; Chat-Spitze nur gelten lassen, wenn viele **verschiedene Nutzer** schreiben (Anteil Emotes/LUL/KEKW/OMEGALUL oder 'lmao' gegen Gesamtzahl).
2. **min_chat für IRL 4,5, co_chat 2,5** (Default 3,0/2,0 war zu locker: 4 Clips in 13 Min). In Jasons VOD-Chat (gleichmäßiger, 100k+ Zuschauer) liegen echte Spitzen bei x3-4, dort reicht 3,5. Wert **pro Kanal** setzen (steht in plan/livewatch.json).
3. **Sprach-Filter (neu, v0.3):** Clip wird verworfen, wenn im Fenster < 12 Wörter gesprochen werden (fing die Werbepause und 2 Musik-/Stille-Momente in den VOD-Läufen ab).
4. **per_hour** nicht zu klein: bei 4 war das Limit nach 13 Min mit Fehlalarmen verbraucht, der Lauf lief 45 Min blind. Besser: Limit zählt nur Clips, die den Sprachfilter bestanden haben (noch nicht gebaut).
5. **Recorder-Watchdog fehlt:** Nach Minute 46 kam kein Stück mehr (ffmpeg hing, vermutlich Stream-Neustart/Spielwechsel), der Lauf lief bis zum Zeitlimit leer. Fix: kein neues Stück seit 3 Min -> ffmpeg neu starten (neue HLS-URL holen).
6. Streams mit viel Laufen/Musik/Alerts meiden; gut sind Facecam-/Talk-/Event-Streams mit mehreren Personen (Jason auf der TwitchCon).
7. `python -u` (jetzt im Workflow): bei Abbruch gingen alle Log-Zeilen verloren, weil stdout gepuffert war. Das Log eines laufenden Jobs ist per API nicht lesbar, nur nach Ende.

## VOD-Modus (neu, Plan B)
- `python3 pipeline/clipfabrik/livewatch.py replay <twitch-vod-url> <start-sek> <minuten> . [min_chat]`, Workflow `livewatch-replay` (manuell, Eingaben vod/start/minutes/min_chat). Gleiche Erkennung, gleiche Clips (`clips/live-<kanal>/`, inbox.json, wird pro Clip gepusht). Kanalname/Layout aus dem ersten Eintrag in plan/livewatch.json, `enabled` nicht nötig.
- Chat-Replay per GQL (`VideoCommentsByOffsetOrCursor`, anonym). **Nur Offset-Paging geht** (Cursor-Paging scheitert am Integrity-Check), ca. 58 Nachrichten pro Abruf; 60 Min Chat = ca. 400 Abrufe = 5 Min.
- Dauer: 50-60 Min VOD in ca. 7-10 Min Laufzeit.
- **Achtung Eichung:** In der VOD ist der Chat fast synchron zum Bild (Verzögerung 0-5 s statt 18-27 s live). Die Erkennung (Treffer/Fehlalarm) lässt sich damit prüfen, die Live-Verzögerung nicht.
- VOD-Moment kann direkt als Clipfabrik-Quelle dienen: `source` = raw-URL des `raw_<stamp>.mp4`.

## Jason-VOD: Ergebnis
- 19 Clips in 170 VOD-Minuten. Gut: Fotobuch-Moment (TwitchCon, „I've never seen this photo"), mit Einschränkung Geschenk-Übergabe. Mittel: Begegnungen auf der Messe ohne Pointe. Schlecht: Autotalk mit „kill myself" (nicht posten), mehrere mit Fluchen.
- Trefferquote grob **10-15 %** brauchbar. Ohne Mensch, der die Vorschauen ansieht, würden die meisten Clips Fehlgriffe sein: Livewatch bleibt ein Kandidatenfinder, kein Autoposter.
- Entwurf: vidIQ postId 1f8d6104-4d61-401e-9a51-0cd0274471f5 (Pusnik IRL: TikTok brandContent an, Instagram, YouTube privat), noch **nicht** veröffentlicht und ohne Termin. Clip: `clips/jasonvod1/jasonvod1_A.mp4`, Quelle `clips/live-jasontheween/raw_20261116-123357.mp4` (bleibt im Repo, bis gepostet).
- Hinweis: Im Rohbild sind Logos des Streams sichtbar (Chat-Overlay, kleines „Valorant"-Schild einer Person, Roblox-Band an Jason). Wenn die Kampagne das ausschließt, anderen Moment nehmen.

## Annahmen / Abweichungen vom Auftrag
- `claude/jason-kampagne.md` existiert im Repo nicht; es galten die Regeln aus dem Auftragstext (Name im Text, #JasonTheWeen, nichts Negatives über Jason, Twitch ja / Kick nein, keine Logos).
- 19:00 auf Pusnik IRL war schon durch TJR belegt (15:00 und 19:00); das hätte für Plan A 19:15 bedeutet. Es wurde nichts gepostet.
- Änderungen an `plan/livewatch.json` und dem Skript liefen über PR + Merge-Commit nach `main`, weil der Workflow nur `main` liest.
- Config nach dem Test: `enabled false`, Kanal wieder `jasontheween` (Twitch-Handle per GQL geprüft, existiert, aktuell offline).
- Unveröffentlichte Rohclips (live-robcdee komplett, live-jasontheween bis auf den einen Quell-Clip) gelöscht.
