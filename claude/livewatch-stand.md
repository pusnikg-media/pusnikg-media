# Livewatch – Stand 19.11.2026 (Clix GTA-VI-Marathon, v0.7)

## Messung und Änderung (Steven-Auftrag 19.11. 07:50 Berlin)
- **Befund:** Clix streamt seit ca. 11:30 Berlin am Vortag (Marathon-Timer im Bild ~20 h); bis ca. 07:30 Berlin IRL, GTA 6 nur 07:40–08:15, danach Schlaf bis ca. 15:30. Livewatch lief ab 05:45 mit min_chat 4,5 / co_chat 2,5 / min_hype 9: **ein einziger Treffer in ca. 2 h** (07:51, chat x3,29 – Bootfahrt + Smalltalk, kein Highlight, übersprungen). Die Launch-Werte waren für Clix zu streng.
- **Neue Werte (plan/livewatch.json, Kanal clix):** `min_chat 3.0`, `co_chat 1.8`, `min_hype 7`, `warmup_s 180`, `per_hour 6`, `max_clips 14` (vorher 4,5 / 2,5 / 9 / 480 / 4 / 10). Kontrolle: 2–4 Kandidaten/Std. gewünscht; > 8/Std. → `min_chat` wieder um 0,5 anheben.
- **Neue Signale (v0.7, `pipeline/clipfabrik/livewatch.py`, 14 neue Tests):**
  1. *Chat-Inhalt:* KEKW, LUL, OMEGALUL, LMAO, 💀 😂, „CLIP IT“, „NO WAY“, BRO, einzelnes W/L → Anteil in der Chat-Spitze hebt das Chat-Verhältnis bis x1,6 (`chat_boost`).
  2. *Zuschauer-Clips:* `ClipWatch` liest alle 45 s die Erstellzeiten der Twitch-Clips von Clix (GQL, anonym). ≥ 2 Clips innerhalb 25 s = stärkster Beweis, löst allein aus (`kind: viewer-clips`, Moment ca. 14 s vor dem Klick). Ob Twitch die Abfrage zulässt, ist **ungeprüft** (im Log steht „clipwatch: …“ bei Fehler).
  3. *Stimm-Ausbruch:* `find_outburst` = lauteste 4 s gegen den Median der letzten 2 Min (nicht 10 Min). ≥ `min_burst` (9 dB) + Chat ≥ 0,8 × co_chat löst aus (`kind: outburst`).
  4. *Sicherheitsnetz:* 30 Min ohne Auslöser → Moment mit der höchsten Punktzahl (hype/min_hype + chat/min_chat + burst/min_burst + 2 bei Zuschauer-Clips) wird Kandidat (`safety: true`, `score`); Aufnahmestücke bleiben dafür 35 statt 15 Min. Wird nur gepostet, wenn die Bildkontrolle es hergibt.
- **Ergebnis der neuen Werte:** 5 Kandidaten in 12 Min, 19 gesamt, **0 brauchbar** (IRL, Cutscene-Lärm). Die Lautstärke triggert auf Spiel-Dialog, nicht auf Clix; ohne Clix-Reaktion (Facecam) bleibt es Kandidatenfinder. Idee: Facecam-Mund/Bewegung oder Mikro-Lautstärke trennen. Zuschauer-Clip-Abfrage (GQL `clips`) lieferte 0 – ungeklärt, ob geblockt.
- Replay-Modus v0.7: `vod` = Kanalname reicht (neuester Archiv-Stream per GQL/yt-dlp, ging beim 3. Versuch), `start` = ISO-Zeit; `replay_info.json` zeigt, was aufgelöst wurde.
- Lauf neu gestartet 08:00 Berlin (alter Lauf abgebrochen, Aufnahme-Puffer weg, 3 Min Aufwärmzeit).

> **Update 18.11.2026 abends:** Livewatch gehört jetzt der Clix-Kampagne (`plan/livewatch.json`: nur `twitch.tv/clix`, `from` 19.11. 05:45, `until` 12:45; Jason entfernt). Anleitung für die Launch-Wache und Generalprobe-Ergebnis: `claude/launch-wache.md`. Neu in v0.6: `from`, Aufnahme endet bei `until`, Kanal-Feld `caption`/`crop`, Marker `clips/live-<name>/posted/<id>.json`, Testmodus mit `min_chat`/`co_chat`/`warmup`. Clipfabrik v6: `crop`.

# Livewatch – Stand 16.11.2026 abends (v0.4, JasonTheWeen / Kampagne Reach „$9,000 Jason Pool")
Regeln der Kampagne: `claude/jason-kampagne.md`. `plan/livewatch.json`: `enabled false`, Kanal `jasontheween`, `profile: irl`.

## Ergebnis in einem Satz
**Nichts gepostet.** Der Fotobuch-Clip hat Logos, die sich nicht sauber entfernen lassen. Das VOD-Training (4 Fenster, 3 VODs) lieferte 5 Kandidaten (alt) / 4 (neu), **0 brauchbar** → Trefferquote nicht verbessert, Grund unten ist nicht der Chat-Filter, sondern das Bildmaterial.

## Schritt 1 – Fotobuch-Clip: NICHT gepostet (vidIQ-Entwurf 1f8d6104… bleibt Entwurf, Termin keiner)
Rohbild (TwitchCon, 17,5 s) enthält in jedem Frame: Chat-Overlay (oben links), Zähler „16338/17000" (oben rechts), **Valorant-Schild** (links, ragt in den Buchbereich), **Roblox-Lanyard** an Jason (zw. 29 und 33 s riesig im Vordergrund, wackelt stark, Jasons Gesicht zeitweise aus dem Bild), **Represent-Logo** auf dem Shirt. Crop auf Jason entfernt Chat/Zähler/Schild nur teilweise, Roblox und Shirt-Logo hängen mitten im Motiv und bewegen sich. Verpixeln hieße 3 bewegte Objekte über 17 s von Hand tracken → ohne Tracking nicht sauber, Rest-Risiko für ein Logo im Bild. Regel: nicht posten. Der Entwurf in vidIQ (mit der alten Datei mit Logos) darf **nicht** veröffentlicht werden. Rohdatei und Clip wurden aus dem Repo gelöscht.

## Schritt 2 – was gebaut ist (v0.4, PR #7, 28 Tests in `tests/test_livewatch.py`)
- **Chat-Signal ohne Alerts:** Bots (Streamelements, Nightbot …, Namen auf „bot"), `!Commands`, Cheers/Bits (`bits`-Tag, `Cheer100`), Bot-Zeilen („just donated", „gifted 5 subs"), IRC-`USERNOTICE` (Gift-Subs, Raids) zählen nicht. Ein Fenster zählt **verschiedene Chatter**. Ist eine Spitze zu ≥ 25 % Alert-Kette (mind. `alert_max` 3 Alerts im Fenster) → übersprungen.
- **Werbepausen (live):** `AdWatch` liest alle 5 s die HLS-Playlist (`twitch-stitched-ad` / `X-TV-TWITCH-AD`), Momente im Werbeblock ±8 s werden übersprungen. Nur live testbar (nicht im VOD); die Erkennung der Playlist-Marker ist per Test nachgebildet, **nicht gegen einen echten Werbeblock geprüft**.
- **Profile:** `profile: irl` = min_chat 4,5 / co_chat 2,5; `gaming` = 3,0 / 2,0 (Standard). Eigene `min_chat`/`co_chat` im Kanaleintrag gewinnen.
- **Watchdog:** `Recorder` startet ffmpeg neu (frische HLS-URL, Stücknummer der aktuellen Streamzeit), wenn 2 Min nichts geschrieben wurde (max. 6 Neustarts). Lücke wird in der Lautstärke-Liste mit Stille aufgefüllt. Nur live relevant, nicht live getestet.
- **Filter vor dem Rendern:** Selbstverletzungs-Wörter („kill myself", kys, suicid…) → verworfen; < 0,8 gesprochene Wörter/s im Schnitt (Geh-/Fahr-Szene) → verworfen; < 12 Wörter im Fenster → verworfen (alt).
- **Replay `compare`:** gleiche Aufnahme zweimal (alt = Plain-Zählung ohne Filter; Ordner `clips/live-<name>-old` nur QA-Bilder), dann neu. Workflow-Eingabe `compare=true`, `min_chat` leer = Profil.

## Schritt 3 – Trainingslauf (4 Fenster à 50–55 Min, 3 VODs, nicht TwitchCon)
| Fenster | min_chat | alt: Clips | neu: Clips | brauchbar |
|---|---|---|---|---|
| VOD 11.11. (Streamer Awards) 1:05–2:00 | 4,5 | 4 | 2 | 0 |
| VOD 09.11. („Rice and crackers") 0:15–1:10 | 4,5 | 0 | 0 | – |
| VOD 13.11. („lets talk", Schreibtisch) 0:05–0:55 | 4,5 | 0 | 0 | – |
| VOD 11.11. 5:48–6:43 | 3,0 | 1 | 2 | 0 |
| **gesamt (≈ 3,6 h)** | | **5** | **4** | **0 / 0** |

Fehlalarme nach Typ (5 verschiedene Momente, alt 5 Treffer / neu 4): Preisrede am Geländer, ernst, nicht lustig (VOD 1:19, alt zusätzlich 1:21 doppelt); Geh-/POV-Szene mit Fluchen, Jason nicht im Bild (1:46); Jason schimpft den Chat an, Jason nicht im Bild (1:06, nur alt); 2× Multi-Fenster-Layout (6:40 und 6:41: Chat-Fenster, Browser, Webcam-Kacheln, „Your stream is still coming"-Bildschirm).
Alle Kandidaten tragen **Chat-Overlay + Zähler** im Bild – bei Jasons IRL-/Cam-Streams ist beides ins Bild eingebrannt.

Was die neuen Filter taten: alt → neu: 4 → 2 (Fenster 1) – ein Duplikat des Preisreden-Moments und ein Chat-Ausraster fielen weg; Fenster 4: +1 Kandidat (Chat-Verteilung wirkt dort anders). Der Filter entfernt Fehlalarme, erzeugt aber keine guten Clips. **Alert-Ketten kamen in Jasons Chat nicht als Spitzen vor** (`skipped alert 0`), der Alert-Fix war für den robcdee-Fall (4k Zuschauer) wichtig, bei Jason (100k, gleichmäßiger Chat) nicht.

## Warum die Quote nicht stieg (Erkenntnisse)
1. **Chat-Verhältnis bei Jason klein:** Spitzen meist x1,3–x2 gegen den Median, echte Momente x3–3,6. Mit 4,5 kaum ein Treffer, mit 3,0 mehr, aber nicht besser. Eher Lautstärke + Sprachdichte + Jason im Bild gewichten.
2. **Bildmaterial:** Eingebrannte Overlays (Chat oben links, Zähler oben rechts) auf jedem Frame; Multi-Fenster-Layouts; Jason oft nicht im Bild. Die Kampagnenregel „keine Logos/Overlays" ist so nur mit einem **Crop** (oberste ~15 % abschneiden) und Szenen mit Jason-Cam erfüllbar.
3. Lautstärke-Maß (`hype`) ist bei Jasons VODs fast immer > 9 (Dauerlärm), trennt nichts.

## Offene Punkte / Empfehlung
- **Clipfabrik-Option `crop` (oben ~15 % weg)** und Jason-im-Bild-Prüfung (Gesicht erkannt) bauen, dann nochmal Trainingslauf. Ohne das bleibt Livewatch nur Kandidatenfinder und jeder Clip braucht Bildkontrolle.
- Live-Lauf noch nicht empfehlenswert. Jasons Streamzeiten (aus den VOD-Startzeiten 02.–13.11., Berlin): Start meist **21:00–23:00**, Ausnahme 07:15 (13.11., kurz), Dauer 5–8 h bis in die Nacht. Clips von dort sind wegen 19:30-Regel erst am nächsten Morgen (Di–Fr 10:00–11:00) postbar.
- Werbepausen-Erkennung und Watchdog sind live nicht erprobt.
- `chat replay` hängt an einem persistierten GQL-Hash (`VideoCommentsByOffsetOrCursor`); bricht bei Twitch-Änderung.
- Frühere Erkenntnisse (robcdee-Live-Test: Chat-Verzögerung 18–27 s, Clip 2–3 Min nach dem Moment im Repo; VOD-Modus Chat fast synchron) gelten weiter.
- Aufgeräumt: `clips/live-jasontheween*`, `clips/jasonvod1`, `clipjobs/jasonvod1.json` gelöscht. `enabled` bleibt `false`.
