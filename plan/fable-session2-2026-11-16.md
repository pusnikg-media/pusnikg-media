# Session 2 (16.11.2026 nachts) – laufender Bericht

Baut auf `plan/fable-nacht-2026-11-16.md` auf. Jede Aufgabe wird nach Abschluss hier eingetragen und committet (Branch `claude/peaceful-pasteur-7p6hd7`). Nichts gepostet, keine Credits, kein Trigger geändert.

## 1. Alte Prompts sichern – BLOCKIERT (Filter)
- Alle Trigger mit `list_triggers` gelesen (5 Seiten, vollständig).
- Das wörtliche Abschreiben der Prompt-Texte hat ein Sicherheitsfilter beim **ersten Trigger (Produzent v4, `trig_01FXCTY479wKaQEJi6nqm3V3`)** gestoppt. Danach kein weiterer Versuch (Systemvorgabe: nicht wiederholen, auch nicht umformuliert). Die anderen Agenten (Clipping-Agent, Analyst, Stratege, Deal-Radar, Reel-Scout) und die Einmal-Trigger sind deshalb **auch nicht gesichert**.
- Statt der Texte: Verzeichnis aller Trigger (ID, Zeit, Modell, Änderungsstand, Auffälligkeiten) in `plan/prompts/backup-2026-11-16/README.md`.
- Nebenbefund: Alle alten Agenten-Prompts enthalten Stevens Nachnamen. Wortgetreu dürften sie ohnehin nicht ins öffentliche Repo.
- **Steven:** vor jedem Tausch den alten Text in der App kopieren und in Apple Notizen sichern (1 Min pro Agent).

## 2. Vier Prompts gegengelesen – erledigt
Geprüft: Analyst, Stratege, Deal-Radar, Reel-Scout gegen Inhaltsregeln, Zeiten/Slots, „Whop“ statt „Content Rewards“ und das Runbook. Keiner der vier postet, schreibt `eingereicht.json` oder verbraucht vor 01.12. Credits; „Whop“ steht nur korrekt als Auszahlung.
**Direkt korrigiert** (je Datei Befund „Gegenlesen Session 2“):
- Analyst: Exp. 1 zählte „5 reife Shorts“ am 22.11. Das Short vom 21.11. hat um 17:17 noch kein `views_24h` (`at_age` braucht ≥ 24 h) → nur gesetzte Werte, n nennen. Instagram wurde doppelt abgefragt → einmal.
- Reel-Scout: Prüfung „älter als 8 Tage“ ließ bei ausgefallenem `reflab` den Bericht der Vorwoche durch → 2 Tage. Den Merge-Ablauf im flachen Sparse-Klon habe ich lokal nachgestellt: funktioniert.
- Deal-Radar: Suche „unter 30 €“ und Filter „≤ 15 €“ widersprachen sich → 15 €.
- Stratege: kein eindeutiger Fehler.
- `plan/prompts/README.md`: Für den Produzenten standen drei verschiedene Einspieltermine (Tabelle: nach Di 07:47 / Fußnote: nach Fr 20.11. / Fable-Nacht-Nachtrag: vor Di 07:47). Jetzt gilt überall **nach dem Lauf Di 17.11. 07:47, vor Mi 18.11. 07:47**. Das passt zu Stevens Plan „ab Di 07:47“. Der Launch-Short für den 19.11. entsteht also noch mit dem alten Prompt, abgesichert durch den Release-Check im Runbook bis 11:30.
- **Neu: `plan/prompts/warzone-erinnerungen-DEF.md`** mit fertigen Ersatztexten (Content Rewards, Issue abhaken, Schicht-Hinweis, postIds unverändert). **D bis Di 17.11. 12:00 tauschen.**
**Offene Fragen (Steven):** (1) Deal-Radar darf bis 15 € melden, obwohl das Budget 0 € ist: so lassen? (2) Deal-Radar mit 4 Suchen pro Tag ist für das Pro-Abo viel: auf 2–3 Tage pro Woche begrenzen? (3) Die drei Entscheidungen aus `plan/prompts/README.md` sind weiter offen (Dauer-Freigabe, Zusatz-Shorts nach 19:30, Deal-Radar-Gedächtnis).
**Nebenbefund Produzent (nicht geändert, war schon gegengelesen):** Schritt 8 wartet höchstens 50 Min auf den Render („Action schaut alle 15 Min“). Gemessen kommt `render` aber nur etwa 1×/h, also läuft der Agent bei einem News-Short meist ins Leere und nimmt den Vorrat. Das ist sicher, aber das News-Short fällt aus. Mehr dazu in Aufgabe 6.

## 3. Clipfabrik-Reste – erledigt (mit Tests)
- **Hochformat-Quelle** (Handy-Video, 9:16, 4:5) in `native`/`framed`: Früher wurde nur das Mittelband gezeigt, oben und unten fehlten. Jetzt wird das ganze Bild schmal und mittig gezeigt, mit Unschärfe-Hintergrund an den Seiten. Querformat bleibt exakt gleich (`fg_w = W`).
- **Emojis:** Hautton (👍🏽), Flaggen (🇩🇪) und ZWJ-Familien wurden pro Codepunkt gezeichnet (👍 + Farbfeld, zwei Buchstabenkästen). Neu: `tokens()` fasst sie zu einem Zeichen zusammen. Ohne Shaping-Engine (raqm) zeichnet es nur das Grund-Emoji und lässt die Flagge weg. Dieselbe Zählung gilt in `caption_hints` (vorher Fehlalarm „mehr als 3 Emojis“).
- **`probe()` bei `r_frame_rate 0/0`:** Vorher Absturz mit „float division by zero“. Jetzt `avg_frame_rate`, sonst 30 fps. Den normalen ffprobe-Aufruf habe ich nicht geändert, nur in diesem Fall kommt eine Zusatzabfrage.
- **Tests:** 6 neue in `tests/test_clipfabrik.py`; die 5 Verhaltens-Tests sind mit dem alten Code rot. Gesamt lokal **279 grün, 0 übersprungen** (OpenCV installiert).
- **`tests/clip_regression.py compare VORHER`: GLEICH (alle Hashes identisch).** Bestehende Clips und Layouts sind unverändert, `job_sig` ist unberührt, nichts rendert neu.
- Nicht angefasst: Livewatch-Fallbackschnitt (`pk-16..pk+8`) an Satzgrenzen (gehört der Livewatch-Session).

## 4. Livewatch offline abgesichert – erledigt (`livewatch.py` unverändert)
- **Neue Tests `tests/test_livewatch_offline.py` (10, alle grün, ohne Netz):**
  - Der AdWatch-Thread liest eine echte Playlist-Datei, die von live → Werbung → live wechselt. Er meldet genau einen Bereich und sperrt Kandidaten darin. Kein Absturz bei nicht erreichbarer Playlist.
  - Watchdog: Hängt ffmpeg, wird es nach `stall` beendet und mit der Stücknummer der Stream-Zeit neu gestartet. Nach `max_restarts` gibt der Watchdog auf. Endet ffmpeg, startet er sofort neu. Ist der Stream beim Neustart offline, endet die Aufnahme.
  - `loop()` Ende-zu-Ende auf einer synthetischen 6-Min-Aufnahme: Der laute Moment bei 250 s wird genau ein Kandidat. Liegt er in einer Werbepause, entsteht kein Clip. Fehlt ein Stück (Recorder-Neustart), bleibt der Moment bei ~250 s (Zeit bleibt treu).
- **Befunde (nicht geändert, nur Statistik):** (1) Derselbe Werbe-Moment wird in jeder Folgeminute erneut gezählt (`skipped ad` 2 statt 1). (2) Ein Stück, das länger als 60 s ist (Keyframe-Abstand > 60 s), verschiebt die Zeitachse um den Überhang. Bei Twitch (Keyframe 2 s) ist das unkritisch. (3) Werbe-Erkennung setzt voraus, dass `live_url` die **Media-Playlist** liefert, denn eine Master-Playlist trägt keine Werbe-Marker. Das ist offline nicht prüfbar; am Donnerstag im Log nach „ad break started“ schauen.
- **Messskript `tests/livewatch_messen.py`:** liest das Action-Log eines livewatch-Laufs und listet jeden Kandidaten mit Minute, Position, Art (chat/laut), hype, Chat-Faktor, Ergebnis und Grund (Aufwärmzeit, unter Schwelle, ohne Chat-Bestätigung, Werbepause, Alert-Kette, zu wenig Sprache, Abstand/Limit, Clip). Mit `bewertung.json` (`{"kanal:pos": true}` = postbar) kommt die **Trefferquote je Art** dazu. Damit wird Donnerstag messbar: Kandidaten, Clips, postbar. 2 Tests.
- **Vorschlag Kick ohne Chat-Signal (nicht umgesetzt):**
  1. **Zuschauer-Clips als Signal:** Kick listet öffentlich die neuesten Clips eines Kanals (der Trendscout liest Kick-Clips schon). Erstellt ein Zuschauer einen Clip, wurde ein Moment von einem Menschen ausgewählt. Den Kanal alle 2–3 Min abfragen; jeder neue Clip wird Kandidat am Clip-Startpunkt. Das ist das stärkste Ersatzsignal.
  2. **Kick-Chat lesen:** Der Kick-Chat ist öffentlich über einen Websocket (Pusher) lesbar, ohne Login. Erst prüfen, ob das ohne Anmeldung und regelkonform geht; dann wäre es dasselbe Chat-Signal wie bei Twitch.
  3. **Bis dahin nur Lautstärke strenger:** `min_hype` 14, `per_hour` 2, dazu Pflicht „Sprache im Schnitt“ (gibt es schon) und eine Dauer-Bedingung (≥ 3 s über der Grundlinie statt einer einzelnen Spitze), damit Musik- und Effekt-Spitzen wegfallen.
  Empfehlung für Donnerstag: Kick-Streamer nur mit Variante 3, besser einen Twitch-Kanal nehmen.

## 5. Pre-Mortem Donnerstag – erledigt
Im Runbook `plan/prompts/runbook-launch-tag-2026-11-19.md` steht ein neuer Abschnitt „Pre-Mortem“: drei Fälle mit geprüfter Wirkung und je einer Ein-Satz-Anweisung für Steven (Cron 90 Min zu spät / Release verschoben / Livewatch 0 Kandidaten), dazu drei Lücken:
- Livewatch hat keinen Push-Auslöser, also braucht der erste Lauf einen Handstart.
- Die Livewatch-Zeile steht unter 12:47, gemeint ist aber „vor 11:30“.
- Ehrlich festgehalten: Bei einer Verschiebung sind Instagram und TikTok ca. 3,5 h falsch online (löschen erst ab 21:30).
Vorbeugung: Di und Mi morgens die News-Zeile ansehen, denn der alte Produzent-Prompt hat keinen Release-Check.
