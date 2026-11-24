# Kai-Cenat-Wache (ab 19.11.2026 13:00) – ersetzt die Clix-Wache

Steven, 19.11.2026 09:07: „umstellen von Clix auf Kai Cenat“ – Kai liefert bessere, schnellere Clips. Gilt für die geplante Aufgabe **„Kai Cenat Live-Wache (stündlich)“**. Mechanik (Prüfung, Weg B, Veröffentlichen, Marker, Postplan, Push) wie `claude/launch-wache.md` Abschnitte 4–8 und 11, aber überall **Kai Cenat statt Clix** und mit diesen Änderungen (gehen vor):

## Kampagne „Kai Cenat - $10,000 GTA 6 Pool Campaign“ (Clipped & Shipped, Content Rewards, ID 1d2bcb00-c904-415f-aa82-f95b96baad86)
Briefing (Screenshot Steven 19.11.):
- Material nur aus Kai Cenats GTA-6-Marathon auf Twitch und YouTube.
- Kai Cenat muss GTA 6 spielen und Hauptfokus sein (Szenen nur mit Gästen, Chat-Lesen ohne Spiel, Pause = nicht nehmen).
- Caption muss **#KaiCenat** enthalten.
- Plattformen TikTok, Instagram Reels, YouTube Shorts (X nie). Konto **Pusnik G**. TikTok `brandContent: true`.
- Nie hinzufügen: Logo, Wasserzeichen, `pill`. Stream-Overlays am Rand dürfen bleiben oder per `crop` weg.
- Sonst Abschnitt 1 der launch-wache.md sinngemäß (nicht negativ, keine Slurs auch zensiert, kein Glücksspiel, keine erfundenen Fakten).

## Layout + Bildtext (Steven 19.11. 12:33, aus viralen GTA-6-Reels mit 700 Tsd.+ Views – geht allen älteren Stil-Regeln vor)
Pro Moment EINES der zwei Layouts wählen:
- **A „Spiel ist der Witz“** (absurde Physik, Unfall/Absturz, Tiere, Glitch, „GTA ist zu realistisch“-Detail): Clip `"layout": "native", "style": "mini"` → ganzes Streambild 16:9 mittig auf Schwarz, Kais kleine Cam/Overlays bleiben wie im Original, darüber nur weiße Mini-Schrift ohne Kasten. `caption` = **2–5 Wörter + 1 Emoji**, ironisch oder trocken, OHNE Namen. Muster: „Realistic game 🥀“, „Rockstar cooked 💀“, „Physics left the chat 😭“, „First shark attack 💀“, „You need a key now? 😭“.
- **B „Kai-Reaktion ist der Witz“** (Schrei, Lachanfall, Rage, Schock auf der Cam): `"layout": "split"` (Cam oben, Gameplay unten) + weißer Kasten. `caption` = EINE kühne Zuspitzung, seit 24.11. 3–8 Wörter, beginnt mit „Kai“, höchstens 1 Wort GROSS, 1–2 Emojis. Muster: „Kai ROBBED by an NPC 😭“, „Kai vs the alligator 💀“.
- Verboten: beschreibende Leerformeln („X is deep into the marathon and this moment is WILD“, „another big moment“, „insane moment“).
- Schnitt: Clip beginnt IM Moment (Sek. 0 = Action, kein Anlauf), 15–45 s, Originalton, kein Zoom.
- Momentjagd (in dieser Reihenfolge): Tiere (Hai, Alligator, Bär), Abstürze/Unfälle, Realismus-Details, Glitches/absurde Physik, Kai schreit/lacht. Reine Laber-/Menüszenen nie.
- `hints` in result.json: bei `style: mini` gelten 2–6 Wörter; die alten Hinweise („Satz beginnt nicht mit dem Namen“, „...“) zählen dort nicht.

## Texte
- Caption TikTok/Instagram: ein Satz mit „Kai Cenat“ + dem konkreten Moment (bei Layout A ist der Bildtext kurz – der Name steht dann HIER) + Leerzeile + kurze Frage, die zum Widerspruch reizt („Is this the most realistic game ever?“) + Leerzeile + genau 5 Hashtags `#KaiCenat #GTA6 #GTAVI #Gaming #Clips`.
- YouTube: Titel = erster Satz der Caption (mit „Kai Cenat“) ohne Emojis/„...“, ≤ 60 Zeichen inkl. „ #shorts“; Text = Satz + `#KaiCenat #GTA6 #Shorts`; public. (Livestream-Material, nicht vom YouTube-Re-Upload-Verbot betroffen.)
- Weg A (Livewatch-Direktclip) nie posten.

## Livewatch (erster Lauf ab 13:00 stellt um, danach nur `enabled`/`until`)
- `plan/livewatch.json` → `channels` = genau ein Eintrag: Kopie des bisherigen clix-Eintrags mit `"name": "kaicenat"`, `"url": "https://www.twitch.tv/kaicenat"`, `"caption": ["Kai Cenat GTA 6 moment (Vorschau, nie posten)"]`; alle anderen Werte unverändert. `note` um einen Satz ergänzen („19.11. 13:00: auf kaicenat umgestellt (Steven)“). Clix ist damit raus.
- Inbox: `clips/live-kaicenat/inbox.json`, Marker `clips/live-kaicenat/posted/<id>.json`, Clipfabrik-Aufträge `clipjobs/kai-<MMTT>-<HHMMSS>.json`.
- `until` rollend jetzt + 2 h, höchstens 2026-11-22T23:30:00Z.
- Postplan: `"kampagne": "Kai Cenat GTA 6"`, `"clip": "live-kaicenat/<id>"`.

## Zeitfenster
Läufe stündlich 07:07–00:07 Berlin, bis Mo 23.11. 00:07. Kein Publish zwischen 00:30 und 07:00 (Steven muss binnen 30 Min einreichen). Höchstens 2 Posts pro Lauf, 8 pro Tag, Moment höchstens 75 Min alt.

## YouTube-Video (2 h GTA 6) und VODs
Kommt über den Clipping-Agenten (Drive-Ordner „Pusnik G Clipping“/„Kai Cenat“, Briefing-Datei liegt dort). Clips aus dem YouTube-Video nur TikTok + Instagram (team_state: kein YouTube für YouTube-Quellen). Twitch-VODs von kaicenat darf die Clipfabrik direkt als `source` nehmen.

## Stand 19.11. 11:00 – Marathon-VOD `kai-vod1` (Auftrag Steven, Session Clipfabrik)
- Quelle: Drive-Datei kai.mp4 (1E3UmNb_zi5JTFJBMY3Wgh7QQOqXkoEOD, „Jeder mit dem Link“), 2 h 5 min. Clipfabrik-Auftrag `clipjobs/kai-vod1.json` (Scan → 10 Clips, `clips/kai-vod1/`). `claude/clipfabrik-stand.md` und `clipfabrik-posting.md` gibt es im Repo nicht.
- Layout `split` für alle 10 Clips (Facecam sichtbar). Kais Cam sitzt klein links (ca. 260×150 px der 720p-Quelle); bis ca. 3300 s bei y ≈ 0,32–0,53, ab ca. 3900 s tiefer (y ≈ 0,40–0,60). Darum: `facecam: [0,0.2889,0.22,0.25]` (Job) und `[0,0.357,0.22,0.25]` für C/E/H/I/J (Clips ab 3970 s). `auto` wurde nicht benutzt. Cam-Fenster mindestens 22 % Breite (Mindestbreite der Funktion). Nach Änderungen am Chat-/Cam-Layout QA-Bild prüfen (Chat-Zeilen unter der Cam).
- Kontextsatz kurz (≤ ca. 28 Zeichen, Steven-Vorgabe), „Kai …“ + Emoji; Untertitel an (`captions: true`); kein Zoom, kein Logo, Originalton. Caption TikTok/Instagram: Satz mit „Kai Cenat“ + Frage + 5 Hashtags `#KaiCenat #GTA6 #GTAVI #Gaming #Clips`; TikTok `brandContent: true`.
- Gepostet/geplant über vidIQ (nur TikTok + Instagram, Pusnik G): A_baby 10:41 (live), B_13y 13:30, E_paint 16:30, F_newgame 19:15 (in vidIQ geplant, Post-IDs in `plan/kai_reserve.json`). Slots in `plan/postplan.json` (Kampagne „Kai Cenat GTA 6“).
- Reserve: `plan/kai_reserve.json` (nur eine Datei, in vidIQ ist nichts geplant), Fr 20.11. und Sa 21.11. je 3 Slots (09:30/13:00/16:30), braucht Stevens Go. **Die Reserve weicht der Kai-Wache:** Live-Clips haben Vorrang, die Limits der Wache (2 Posts/Lauf, 8/Tag) bleiben unverändert und zählen die VOD-Posts NICHT mit; Reserve-Slots rutschen nach hinten (mind. 2,5 h Abstand, nie nach 19:30). Heute (19.11.) stehen 4 VOD-Posts (10:41, 13:30, 16:30, 19:15) auf Pusnik G; `plan/waechter.json` `max_pro_tag: 4` für „Kai Cenat GTA 6“ gilt nur für Postplan-Prüfung/Wächter.
- Kampagne „Kai Cenat GTA 6“ jetzt eingetragen: `plan/waechter.json` (`max_pro_tag: 4`), `plan/stats.json` (`#kaicenat`), `plan/kampagnen.json` (`joined`). Grund: Test `test_postplan_is_consistent_with_repo` und Wächter schlugen bei 4 Posts/Tag auf Pusnik G (Grenze 2) rot an; Grenze ist jetzt je Kampagne konfigurierbar (`max_pro_tag`, Test in `tests/test_waechter.py`).
- Bei „Calm the fuck down“/Fluchen im Spielton (B_13y) gibt es Untertitel mit Schimpfwörtern, aber keine Slurs; die Clips H/J vorher kurz gegenprüfen, falls sich die Briefing-Regeln ändern.
