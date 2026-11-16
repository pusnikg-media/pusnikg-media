# Fable-Nacht 16.11.2026 – Ergebnis

Stand: laufend (wird nach jedem Block ergänzt). Branch `fable-nacht`.

## Zusammenfassung (wird am Ende gefüllt)
- Fertig: –
- Offen: –
- Steven muss selbst (max. 3): –

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
