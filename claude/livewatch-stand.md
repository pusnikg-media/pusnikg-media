# Livewatch – Stand 16.11.2026 abends (v0.5, JasonTheWeen / Kampagne Reach „$9,000 Jason Pool")
Regeln der Kampagne: `claude/jason-kampagne.md`. `plan/livewatch.json`: `enabled false`, Kanal `jasontheween`, `profile: irl`.

## Ergebnis in einem Satz
**Nichts gepostet. Trainingslauf 2: 0 brauchbare von 5 Kandidaten (Lauf 1: 0 / 5 alt, 0 / 4 neu) → Empfehlung: Jason-Kampagne einstellen** (Abbruchkriterium „< 2 brauchbar von ~5“ erfüllt). Der Fehler liegt nicht an den Filtern, sondern am Material: Jasons Streams liefern kaum saubere, logofreie Momente mit Jason groß im Bild.

## Lauf 2 (v0.5: crop 0,17 + Gesicht-im-Bild + Multi-Fenster-Prüfung), gleiche 4 Fenster, Branch-Code, Ergebnisse nur im Action-Log
| Fenster (VOD, Start, Minuten) | Kandidaten | Ergebnis |
|---|---|---|
| 2926143637 (11.11.) ab 3900 s, 55 | 3 | 2× verworfen „Gesicht nur 14 % / 11 % der Zeit“ (Preisrede am Geländer, Geh-/POV-Szene), 1× Selbstverletzungs-Wörter |
| 2924380274 (09.11.) ab 900 s, 55 | 0 | – |
| 2927412068 (13.11.) ab 300 s, 50 | 0 | – |
| 2926143637 (11.11.) ab 20900 s, 55 | 2 | 2× verworfen „68 % / 48 % des Bildes schwarz“ (Multi-Fenster, „Your stream is still coming“) |
| **gesamt (≈ 3,6 h)** | **5** | **0 gepostet, 0 brauchbar** |
Alle 4 verworfenen Kandidaten sind genau die Fehlalarme aus Lauf 1: die neue Prüfung hält sie zuverlässig zurück (vorher kamen sie als fertige Clips durch). Gute Clips erzeugt sie nicht: der Kandidatenfinder liefert bei Jason keine. Nichts wurde nach `main` oder in Branches geschrieben (Testlauf-Modus `push_branch`; es wurden nur die Action-Logs erzeugt).

## Was neu gebaut ist (PR #15, v0.5)
- **`crop`** (Clipfabrik, pro Job/Clip; Livewatch-Profil `irl`: 0,17). Der eingebrannte Chat reicht bis ca. **15,8 %** der Bildhöhe (23 Rohclips gemessen) → 0,15 lässt die unterste Chatzeile angeschnitten, 0,17 ist sauber. Zähler (oben rechts) liegt bei 0–4,4 %.
- **Jason im Bild** (`check`, `pipeline/clipfabrik/framecheck.py`, OpenCV Haar, kostenlos, lokal): Gesicht ≥ 7 % der Bildbreite in ≥ 45 % der Zeit, keine Lücke > 6 s, sonst Clip verworfen. Geeicht an 23 echten Jason-Rohclips (TwitchCon, Balkon, POV, Multi-Fenster). Grenzen: es erkennt nur *ein* Gesicht, nicht *wessen* (ein Gast im Bild genügt), und Haar ist schwach bei Mützen/abgewandtem Kopf (zu strenge Ablehnung eher als zu lasche).
- **Multi-Fenster-Layouts**: dauerhafte gerade Kanten oder > 30 % schwarzes Bild → verworfen (erkennt die beiden Fehlalarme aus Lauf 1).
- **Logo-Warnung** (nie Verwerfen, `warnings` in `result.json`): statische Overlays (z. B. Zähler, eingebrannte Caption) und große Schriftzüge. **Logos auf Kleidung, Lanyards, Schildern, Geräten sind nicht erkennbar** – bewegen sich mit dem Motiv. **Jeder Clip der Kampagne muss von Hand geprüft werden (6–8 Frames).**
- `livewatch-replay.yml`: neue Eingaben `ref` und `push_branch` (Testläufe mit Branch-Code, Ergebnisse nie auf `main`). 279 Tests grün.

## Schnelltest: Jasons eigener Upload als Quelle (1 Stichprobe)
- **YouTube: von Cloud-Servern nicht abrufbar** („Sign in to confirm you're not a bot“) → nicht testbar, nur über Drive-Upload von Steven.
- **TikTok `@jasontheween`** (Beitrag „Almost had him“, 16,7 s, 1080×1080): Jason groß im Bild (Gesicht in 100 % der Zeit), kein Zähler, Chat nur noch ein kleiner Rest oben links, keine Multi-Fenster → **deutlich sauberer als die Twitch-VODs**. Aber: (1) fremdes eingebranntes Caption-Overlay im Bild (die Prüfung warnt zu Recht), (2) nicht belegt, dass das Jasons *eigenes* Konto ist (Titel „(Twitch-Jasontheween)“ sieht nach Clip-Seite aus) und die Kampagne verbietet **Reposts** → vor einer Nutzung müsste Reach bestätigen, dass Jasons eigene Uploads als Quelle zulässig sind. Logos (Shirt, Auto-Emblem) bleiben auch dort Handarbeit.
- Fazit: bessere Bildquelle, aber kein Ausweg aus der Logo-/Repost-Frage; löst nicht das Kandidaten-Problem.
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
- crop + Jason-im-Bild-Prüfung sind gebaut (v0.5, oben), Trainingslauf 2 gelaufen: 0 / 5. **Empfehlung: Jason-Kampagne einstellen** (oder nur von Hand, ohne Livewatch). Steven entscheidet.
- Live-Lauf noch nicht empfehlenswert. Jasons Streamzeiten (aus den VOD-Startzeiten 02.–13.11., Berlin): Start meist **21:00–23:00**, Ausnahme 07:15 (13.11., kurz), Dauer 5–8 h bis in die Nacht. Clips von dort sind wegen 19:30-Regel erst am nächsten Morgen (Di–Fr 10:00–11:00) postbar.
- Werbepausen-Erkennung und Watchdog sind live nicht erprobt.
- `chat replay` hängt an einem persistierten GQL-Hash (`VideoCommentsByOffsetOrCursor`); bricht bei Twitch-Änderung.
- Frühere Erkenntnisse (robcdee-Live-Test: Chat-Verzögerung 18–27 s, Clip 2–3 Min nach dem Moment im Repo; VOD-Modus Chat fast synchron) gelten weiter.
- Aufgeräumt: `clips/live-jasontheween*`, `clips/jasonvod1`, `clipjobs/jasonvod1.json` gelöscht. `enabled` bleibt `false`.
