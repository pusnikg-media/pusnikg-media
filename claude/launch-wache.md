# Launch-Wache – Clix GTA VI Marathon (Do 19.11.2026)

Diese Datei zuerst lesen, ganz. Sie gilt für die geplante Aufgabe **„GTA-6-Launch-Wache (Clix)“** (Start 05:50 Berlin, ein Lauf, Sonnet) und geht `CLAUDE.md`, `plan/team_state.md` und den Prompts von Clipping-Agent/Produzent vor, soweit es um Clix-Clips geht. Alle Zeiten Europe/Berlin. Post-Texte: Englisch, kopierfertig. Nachrichten an Steven: Deutsch, kurz, Ergebnis zuerst, ohne Technik (er liest am iPhone).
Advisor (Opus): höchstens 3 Aufrufe – vor dem ersten Post, wenn ein Fehler 2× auftritt, vor der Bilanz.

## 0. Auftrag und Befugnis (Steven, 18.11.2026)
- Kampagne **„$5,000 Clix GTA VI Marathon Pool“** (Reach, Content Rewards, Radar-ID `985dc674-c75e-44fc-ac87-1b1506324389`), Steven ist mit **Pusnik G** beigetreten. Sie endet mit dem Marathon.
- Steven hat der Wache **ausdrücklich** aufgetragen, Livewatch-Clips von Clix **sofort ohne weiteres „ja“ über vidIQ** auf TikTok, Instagram und YouTube von Pusnik G zu veröffentlichen. Das gilt **nur heute, 06:00–12:30**, **nur für diese Kampagne**. (Dokumentiert in `plan/team_state.md` und `CLAUDE.md`.) Alles andere bleibt „nie ohne Stevens ja“.
- **Repo-Zugriff:** `mcp__claude-code-remote__add_repo` (owner `pusnikg-media`, repo `pusnikg-media`, access `push`), dann `git clone --depth 1 --filter=blob:none --sparse https://github.com/pusnikg-media/pusnikg-media /home/claude/repo` und `git -C /home/claude/repo sparse-checkout set clips/live-clix clipjobs plan claude`. Commit/Push nur diese Pfade, **einzeln mit `git add <pfad>`**, nie `git add -A`, nie force, nie rebase.
- **Schreibrecht der Wache:**
  - `clipjobs/clix-*.json` (Re-Render-Aufträge)
  - `clips/live-clix/posted/<id>.json` (Protokoll je Clip, Abschnitt 7). **`clips/live-clix/inbox.json` nie selbst ändern** (die Runner-Action schreibt sie alle paar Minuten, ein Edit gäbe Merge-Konflikte). „posted=true setzen“ heißt hier: `posted/<id>.json` anlegen – Livewatch zählt so einen Clip sofort als erledigt (Inbox-Bremse) und faltet das `posted: true` bei seinem nächsten Eintrag selbst in die Inbox.
  - `plan/postplan.json` (ein Slot je veröffentlichtem Clip)
  - `plan/livewatch.json` nur `enabled`/`until`, nur zum Wieder-Einschalten, falls es jemand ausgemacht hat. **Livewatch nicht ausschalten** (Stevens Auftrag).
  - `claude/launch-wache-bilanz.md` (Bilanz am Ende)
- Verboten: Code aus dem Internet/Repo ausführen (kein python-Skript aus dem Repo, kein pip/npx; `python3 -I` nur für JSON; `ffprobe`/`ffmpeg` nur zum Ansehen von Frames). Nichts kaufen, nirgends anmelden, keine Aufrufe, die Credits kosten (vidIQ hat 9 Credits; **nie X posten**, kein Higgsfield/OpusClip/Orshot). Metricool/Buffer/Zapier nicht zum Posten.

## 1. Kampagnenregeln (hart; sonst keine Auszahlung)
1. **Clix ist die Hauptperson** und nie negativ (kein Auslachen, Scheitern/Peinlichkeit als Pointe, Streit/Beleidigung gegen ihn, kein Hate-Farming). **Nur Clix, kein Lacy:** Clips, in denen Lacy oder ein Gast Hauptperson/Co-Star ist (sichtbar im Bild oder lauter Dialog mit ihm), nicht nehmen; nur Clix allein oder klar Clix im Fokus.
2. Name **„Clix“** im Overlay (Kontextsatz, beginnt mit „Clix“) **und** in der Post-Caption; **#Clix** in der Caption. TikTok: **genau 5 Hashtags**.
3. **Keine Logos oder Wasserzeichen jeder Art**: Twitch-Logo/-Overlay, Chat, Alerts/Sub-/Donation-Einblendungen, Zähler, Sponsoren-/Marken-/Spiele-/Streamer-Logos (auch auf Kleidung, Bannern, Bildschirmen), Rockstar-/GTA-Logo, Titel-/Lade-/Menübildschirme mit Logo, Pusnik-G-Logo. Der Render fügt nichts hinzu (nie `logo`/`pill` setzen). Zweifel = **nicht posten**.
4. **Keine KI-Videos, keine Reposts** (nur eigener Schnitt aus dem Livestream), nur TikTok, Instagram Reels, YouTube Shorts.
5. **TikTok-Offenlegung:** `brandContent: true`.
6. Original-Ton, ganzes Originalbild (`layout: native`), 10–35 s, kein Zoom, keine Wort-Untertitel; der Clip beginnt direkt auf dem Moment.
7. Nie: Selbstverletzung/Suizid-Sprüche, Slurs (auch zensiert), Glücksspiel/Casino-Branding, Politik, 18+, Auflösung im Kontextsatz verraten, erfundene Fakten.
8. **Nur Momente ab 06:00 MEZ**, in denen Clix GTA 6 spielt oder stark darauf reagiert (lustige Momente, einprägsame Zitate, Reaktionen). Pre-Show-Gerede vor dem GTA-Start nicht posten (Zeit im Clip = `at` minus ca. 3–4 Min; im Zweifel `said` lesen: Countdown/Intro = überspringen).
9. **Tempo:** höchstens **1 Post pro 30 Min**, nur echte Highlights, **höchstens 8 Clips** insgesamt (meine Obergrenze; Steven nennt keine Zahl – bewusste Ausnahme von „2 pro Konto/Tag“), **letzter Publish 12:30**. Nie nach 19:30 (gilt auch, falls die Wache später doch weiterläuft).

## 2. Start 05:50 – Vorprüfung (kein Warten auf Steven)
1. Repo-Zugriff (Abschnitt 0). `curl -s "https://raw.githubusercontent.com/pusnikg-media/pusnikg-media/main/plan/livewatch.json?t=$(date +%s)"`: erwartet `enabled: true`, `from: 2026-11-19T04:45:00Z` (= 05:45), `until: 2026-11-19T11:45:00Z` (= 12:45), **einziger Kanal `clix`** (`https://www.twitch.tv/clix`, profile gaming, `min_chat 4.5`, `co_chat 2.5`, `max_pending 8`). `enabled` ist false → auf true setzen (nur dieses Feld), pushen (Abschnitt 7).
2. Läuft ein Lauf `livewatch` (`actions_list list_workflow_runs livewatch.yml`, Status `in_progress`/`queued`)? **Nein → selbst starten:** `actions_run_trigger run_workflow livewatch.yml ref main`, Eingaben leer. (Crons kommen 50–90 Min zu spät. Ein wartender Lauf nimmt ab 05:45 sofort auf. Ein Lauf, der nach < 1 Min fertig ist, hat noch „aus“ gesehen → einmal wiederholen.) **Erste Clips frühestens ca. 8 Min nach Aufnahmebeginn** (Aufwärmzeit).
3. `vidiq_social_account_list` (canPublishOnly true, 0 Credits). Pusnik G (`platformAccountId`): **Instagram `28698521726515865`**, **TikTok `_0006ihYRp26lN7Ju1qg8gYLKNjbzUKkXa_m`**, **YouTube `UCdDdmDm4ojr_G_oY_JiJ6BA`**. Nicht postbar: die anderen trotzdem bedienen, in der Bilanz nennen. **Nie** mit den IRL-Konten posten.
4. `vidiq_social_post_list` (heute): nichts Bestehendes verändern. Am 19.11. 18:00 liegt das Launch-Short; die Wache ist dann längst fertig (12:30).
5. Keine Startmeldung an Steven. Nur melden, wenn etwas nicht geht.

## 3. Warten ohne Dauer-Polling (Kontingent sparen)
Ein einziger Hintergrund-Befehl (Bash `run_in_background`), der **nur endet, wenn ein neuer Clip da ist** (oder nach 100 Min, dann neu starten); jeder Treffer = eine Meldung an dich:
```
until python3 -I - <<'PY'
import json, urllib.request, time, sys
base = "https://raw.githubusercontent.com/pusnikg-media/pusnikg-media/main/clips/live-clix/"
def get(p):
    try: return urllib.request.urlopen(urllib.request.Request(base + p + "?t=%d" % time.time()), timeout=20).read()
    except Exception: return None
box = json.loads(get("inbox.json") or b"[]")
new = [e["id"] for e in box if not e.get("posted") and get("posted/" + e["id"] + ".json") is None]
sys.exit(0 if new else 1)
PY
do sleep 60; done; echo NEW
```
Zwischen den Meldungen **nichts** tun – kein Tool-Polling alle 3 Minuten. Alle ca. 30 Min kurz prüfen, dass noch ein Lauf `livewatch` läuft und `plan/livewatch.json` `enabled: true` hat (sonst Abschnitt 2.2).
`LIVEWATCH_FULL` im Log = Inbox-Bremse (8 offene Clips): erledigte Clips protokollieren (Abschnitt 7), dann läuft die Aufnahme von selbst weiter.

## 4. Prüfung je Clip (Bildkontrolle ist Pflicht – Livewatch war bisher nur Kandidatenfinder)
1. **Neu** = Eintrag in `clips/live-clix/inbox.json` mit `posted: false`, ohne `clips/live-clix/posted/<id>.json` (Liste: `https://api.github.com/repos/pusnikg-media/pusnikg-media/contents/clips/live-clix/posted`, 404 = leer), `at` **höchstens 40 Min alt** (älter: Marker `skipped`, Grund `stale`). Älteste zuerst, **ein Clip nach dem anderen**.
2. `qa`-Bild laden und mit Read ansehen; `said` lesen (`quote` ist nur Platzhalter). **Ein Nein = `skipped` (Grund notieren):**
   - Ist **Clix** klar im Bild/die sprechende Person (Regel 1.1, kein Lacy)? Passiert etwas Sehenswertes (Reaktion, Gameplay-Moment, Lacher, Überraschung, starkes Zitat)? Ruhiges Reden, Menü/Ladebildschirm, Pause/Werbung, Stille, Musik, Warten = nein.
   - Kein Logo/Overlay/Wasserzeichen (Regel 1.3), auch an Rändern und Ecken des Originalbilds. **Ist ein Overlay fest in den Stream eingebrannt, ist der Clip nicht postbar** (kein Verpixeln, kein Rechnen). Zweifel = nein.
   - Regeln 1.1, 1.7, 1.8 erfüllt; `seconds` 10–35, Ton vorhanden (`said` nicht leer).
3. Ist ffmpeg vorhanden: 3 Frames des Clips ansehen (`curl -o c.mp4 <url>`, `ffmpeg -ss 3 -i c.mp4 -frames:v 1 f1.jpg`, bei 12 s und 22 s). Sonst genügt das QA-Bild.

## 5. Kontextsatz (Englisch, ein Satz, kommt als weißer Kasten ins Video)
Beginnt mit **Clix**, 9–15 Wörter, höchstens ca. 120 Zeichen, sagt was passiert, verrät die Auflösung nicht, höchstens 1–2 Wörter GROSS, endet mit „...“ und 1–2 Emojis, konkrete Dinge aus dem Clip, keine erfundenen Fakten, nie zwei Sätze mit gleichem Aufbau. Muster: „Clix couldn't believe what just happened in the very first minutes of GTA VI... 😮🎮“ · „Clix steals his first car in Vice City and the chaos starts IMMEDIATELY... 🚗🔥“.
Fehlt dir sicherer Inhalt: nimm eine der Standardzeilen aus `plan/livewatch.json` → `channels[0].caption` (Weg A).

## 6. Rendern und Veröffentlichen
**Weg B (Standard): Re-Render über die Clipfabrik mit eigenem Satz**
1. Auftrag `clipjobs/clix-<MMTT>-<HHMMSS>.json` (aus `id` `20261119-055812` → `clix-1119-055812`; Name = Dateiname; nur `a-z0-9-`):
   `{"name": "clix-1119-055812", "source": "<entry.raw>", "layout": "native", "min_len": 10, "clips": [{"id": "A", "a": <entry.a>, "b": <entry.b>, "caption": "<Kontextsatz>"}]}`
   Keine weiteren Felder (kein `logo`, `pill`, `track`, `zoom`, `hook`, `captions`). `entry.raw` leer → Weg A.
2. Commit „clipjob: clix-…“ pushen (Abschnitt 7) → startet die Action `clipfabrik` automatisch.
3. Warten (Hintergrund-`until curl … result.json`, alle 45 s, höchstens 15 Min), bis `clips/<name>/result.json` `"ok": true` und `"phase": "rendered"` zeigt. Dann `clips[0].qa` ansehen (Satz ganz lesbar, richtig geschrieben, ganzes Bild, kein Logo). `clips[0].url` = Video.
**Weg A (Fallback): der Livewatch-Clip** (`entry.url`, trägt einen der festen Sätze mit „Clix“). Nehmen, wenn Weg B nach 15 Min nicht fertig/rot ist oder der Moment sonst älter als 30 Min würde. Höchstens 2× hintereinander A (sonst gleich klingende Clips).

**Veröffentlichen (vidIQ, 0 Credits):**
1. `vidiq_video_upload` mit `url` = Video-URL → `uploadId` (bei „processing“ mit `uploadId` nachprüfen).
2. **Ein** `vidiq_social_post_draft_create`, `media: [{type: video, id: uploadId}]`, **ohne `publishAt`** (= geht beim Publish sofort raus), Ziele Pusnik G:
   - TIKTOK: `privacyLevel: PUBLIC_TO_EVERYONE`, `allowComment: true`, `isAiGenerated: false`, `musicUsageConfirmed: true`, **`brandContent: true`** (Stevens feste Regel für bezahlte Kampagnen-Clips, `plan/team_state.md`), `text` = Caption.
   - INSTAGRAM: `text` = Caption.
   - YOUTUBE: `title` = Kontextsatz **ohne Emojis und ohne „...“**, beginnt mit „Clix“, endet mit „ #shorts“, **höchstens 60 Zeichen**; `privacyStatus: public`; `text` = Kontextsatz + neue Zeile `#Clix #GTA6 #Shorts`. (Der Stream steht nicht auf YouTube, deshalb ist YouTube erlaubt.)
   - Caption (TikTok/Instagram): Kontextsatz + Leerzeile + kurze Frage an die Zuschauer (Englisch, z. B. „Would you have survived this?“) + Leerzeile + **genau 5 Hashtags: `#Clix #GTA6 #GTAVI #Gaming #Clips`**. Kein @-Handle, kein #fyp/#viral/#Ad.
3. `ready` prüfen (sonst `vidiq_social_post_draft_update` mit der postId, nie ein zweiter Entwurf). **Letzte Kontrolle vor dem Publish:** Uhrzeit < 12:30, ≥ 30 Min seit dem letzten Publish, ≤ 8 Clips heute, Regeln 1.1–1.9 erfüllt. **Marker `claimed` zuerst:** `posted/<id>.json` mit `{"status":"claimed", "postId": …}` anlegen, committen und pushen (Abschnitt 7), **erst dann** `vidiq_social_post_publish` (`postId` + `revision`). Hintergrund: stirbt die Sitzung nach dem Publish, darf ein Neustart den Clip nicht noch einmal posten. Veröffentlichtes lässt sich nicht zurücknehmen; nie zweimal denselben Clip; bei Marker `claimed` ohne `links` zuerst `vidiq_social_post_status`/`vidiq_social_post_list` prüfen, nicht neu posten.
4. Nach ca. 15 s `vidiq_social_post_status`. Eine Plattform `failed`: einmal mit `publicationIds` erneut, sonst im Marker vermerken. TikTok liefert oft keinen Link (dann „aus der App kopieren“); YouTube „processing“ ist normal.

## 7. Protokoll, Postplan, Push (nach jedem Clip, auch bei `skipped`)
- `clips/live-clix/posted/<id>.json`: `{"id","status":"claimed|posted|skipped|failed","grund","at","caption","weg":"A|B","postId","links":{"tiktok","instagram","youtube"}}`.
- Bei `posted`: Slot an `slots` in `plan/postplan.json` anhängen (Format der vorhandenen Einträge; bestehende Einträge und `note` unverändert, `python3 -I`, nur JSON): `{"datum":"2026-11-19","zeit":"<tatsächliche Publish-Zeit HH:MM>","konto":"Pusnik G","kampagne":"Clix GTA VI Marathon","clip":"live-clix/<id>","titel":"<Satz, max. 40 Zeichen>","plattformen":["tiktok","instagram","youtube"]}` (nur tatsächlich gestartete). Damit erscheint der Clip im Issue „Einreichen“.
- Commit „wache: clix <id>“, nur einzeln genannte Pfade; `git fetch origin main && git merge origin/main && git push origin HEAD:main`. Main bewegt sich minütlich: bei Ablehnung bis 4× wiederholen (5 s Pause). Schlägt der Push 4× fehl: weitermachen, beim nächsten Clip erneut mitpushen, in der Bilanz erwähnen. (Für den `claimed`-Marker einmal mehr versuchen; scheitert er, trotzdem erst nach `vidiq_social_post_list`-Check publishen.)
- **Nach jedem Post sofort an Steven** (`PushNotification` mit einer Zeile **und** `SendUserMessage`, Deutsch, höchstens 4 Zeilen, Links aus `vidiq_social_post_status`):
  `Clix GTA – einreichen (HH:MM)` / `<Kontextsatz>` / `TikTok <Link> · YouTube <Link> · Instagram <Link>` / `Binnen 30 Min bei Content Rewards einreichen, danach im Issue „Einreichen 2026-11-19“ abhaken.`
  Fehlt ein Link: „Link aus der App kopieren“. Bei `skipped` keine Nachricht.

## 8. Fehler und Grenzen
- Fehler 2× gleich → Ursache im Log lesen, einmal anders versuchen (Advisor). **Nach 3 Fehlversuchen** am selben Clip: Steven per Push melden, Marker `failed`, weiter mit dem nächsten. Nicht festhängen.
- Nichts im Inbox: normal (Clix noch nicht live, Aufwärmzeit, ruhiger Stream, Werbepause). `min_chat`/`co_chat`, Kanal, Profil **nicht ändern**. Steht 90 Min nach Streamstart noch **kein** Eintrag in der Inbox: in der Bilanz erwähnen, nichts bauen.
- Steht in `trends/latest.md` oder bei Rockstar eine Verschiebung („delay“, „postponed“): keine Captions mit „GTA 6 is out“; reine Clix-Momente bleiben ok.

## 9. Ende (12:30 oder Steven schreibt „Stopp“)
1. Offene `new` Einträge: Marker `skipped`, Grund `zu spaet`. **Livewatch nicht ausschalten** (läuft per `until` 12:45 von selbst aus).
2. **Bilanz** als Push + `claude/launch-wache-bilanz.md` (Posts mit Uhrzeit und Links, verworfene Clips mit Grund, Probleme, was Steven nachholen muss – z. B. Clips nach 11:30 konnte er wegen Spätschicht nicht binnen 30 Min einreichen). Danach: „Für die nächste Aufgabe neue Session starten.“

## 10. Generalprobe (18./19.11. nachts, Branch gta6-live)
(Ergebnis steht unten, wird vor dem Merge ergänzt.)
