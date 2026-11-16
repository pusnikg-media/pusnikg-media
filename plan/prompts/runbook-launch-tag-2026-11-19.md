# Runbook Launch-Tag Donnerstag 19.11.2026 (GTA 6) – Stand 16.11.2026

Alle Zeiten Europe/Berlin. Spätschicht-Woche 16.–22.11.: **Steven ist 12:00–21:30 nicht erreichbar, nur 09:00/09:30 sind Einreichen-Slots.** Actions laufen laut Messung 13.–16.11. oft 50–90 Min später als der Cron (Wächter läuft deshalb zusätzlich direkt nach jedem stats-Lauf). Abkürzungen: **S** = Steven (iPhone), **A** = geplanter Agent, **W** = Wächter/Action, **C** = Chat-Session (Steven schreibt im Pusnik-G-Chat).

## Vorabend Mi 18.11.
| Zeit | Schritt | Wer / Wo | Prüfkriterium |
|---|---|---|---|
| 06:47 | Wächter-Lauf | W; `stats/alerts.md` | `stand_utc` jünger als 15 h; keine offenen Punkte, sonst im Chat melden |
| 07:47 | Produzent plant den ersten Tag ohne 18:00-Post. Er arbeitet oft einen Tag voraus (Shorts werden vorab eingeplant) – **nicht annehmen, prüfen:** | A; **S oder C: vidIQ `social_post_list` 18.–20.11.** | Posts 18:00 für **18.11. und 19.11.** vorhanden (Status `scheduled`). Fehlt einer: sofort im Chat einplanen lassen (Auftrag `shorts/pusnikg-2026-11-18-day1(-ai).json` bzw. `…-19-launch(-ai).json`, beide am 16.11. `ok: true`). Ist der 19.11. schon eingeplant, kann eine echte Launch-News ihn nicht mehr ersetzen (vidIQ nicht rücknehmbar) – dann Zusatz-Short statt Ersatz |
| 09:00 / 09:30 | TJR-Clips C (`tjr4/C_brother`, `tjr5/C_worst`) gehen auf Pusnik IRL live | vidIQ | Link-Erinnerungen 09:03 und 09:33 kommen |
| bis 09:30 + 30 Min | **S** reicht beide Clips bei Content Rewards ein und hakt im Issue „Einreichen 2026-11-18“ ab | S; GitHub-App -> Issues | Haken gesetzt; sonst Alarm „Einreichen“ nach ca. 10 h |
| 12:47 | Clipping-Agent läuft | A | nichts Neues = keine Nachricht (Material TJR/Warzone verbraucht) |
| ca. 15:47 | Einmal-Trigger „Review-Roundup“ (nur wenn Review-Embargo gefallen) | A | Zusatz-Short frühestens ca. 16:15, NICHT 17:45–18:30 |
| 18:00 | Tages-Short Day 1 geht live | vidIQ | YouTube + TikTok sichtbar bis 18:45 (Wächter-Fenster 17:30–18:45) |
| 19:30 | Warzone F (`wzs1/F_free`) Pusnik G TikTok+IG | vidIQ | live; **S** kann die 30-Min-Frist wegen Spätschicht nicht halten -> Frist verpasst, Wächter-Alarm „Einreichen“ erwartet; S entscheidet am nächsten Morgen, ob er noch versucht einzureichen (siehe Notfall „Einreichen“) |
| 20:17–20:47 | stats 20:17, Wächter 20:47 | W | `alerts.md` aktualisiert |
| ca. 21:17 | Einmal-Trigger „Review-Roundup 2. Versuch“ | A | **Post ca. 21:32 liegt nach 19:30** (Entscheidung offen, README Punkt 2) |
| Abend | Launch-Vorbereitung prüfen: Kampagnen-Radar `campaigns/latest.md`, News `trends/latest.md` | S oder C | Gibt es eine GTA-6-/Streamer-Kampagne mit Rechteinhaber? Nein = Livewatch bleibt AUS |

**Regel Vorlauf:** GitHub-Crons kommen 50–90 Min zu spät, `render`/`clipfabrik` liefen am 16.11. nur ca. 1×/h (Lücken bis 3 h). Jeder Render-/Clip-Auftrag muss mindestens 4 h vor der Postzeit im Drive/Repo liegen; sonst Action von Hand starten (Safari -> github.com/pusnikg-media/pusnikg-media/actions -> render/clipfabrik -> Run workflow) oder den Vorrat (`shorts/…` mit `ok: true`) nehmen.

## Launch-Tag Do 19.11.
| Zeit | Schritt | Wer / Wo | Prüfkriterium |
|---|---|---|---|
| 06:47 | Wächter-Lauf | W | wie oben; Probleme zuerst lösen |
| 07:47 | Produzent plant den nächsten freien Tag (je nach Vorlauf 19.11., 20.11. oder später); **Prüfen wie am 18.11.:** Post 19.11. 18:00 muss `scheduled` sein | A + **S/C: vidIQ-Liste** | Post für 19.11. 18:00 vorhanden. Nachricht „✅ Ist eingeplant …“ an S. Antwort „raus“ nur bis 11:30 sinnvoll |
| 09:00 / 09:30 | TJR-Clips E (`tjr4/E_seats`, `tjr5/E_outro`), **letzte TJR-Clips** | vidIQ | Erinnerungen 09:03 / 09:33; danach Erinnerung „neues TJR-Video in den Drive-Ordner TJR“ |
| bis 10:00 | **S** reicht ein + hakt ab (Issue „Einreichen 2026-11-19“) | S | Haken gesetzt |
| **bis 11:30** | **S letzte Kontrolle vor der Schicht:** (1) vidIQ: Post 19.11. 18:00 `scheduled`? (2) Livewatch-Entscheidung (siehe nächste Zeile). (3) Kampagne beitreten? (nur S kann beitreten); Material in Drive „Pusnik G Clipping“. (4) „ja“/„raus“ zum Short. (5) **Release-Check:** `trends/latest.md` GTA-6-News + rockstargames.com: Steht dort eine Verschiebung („delay“, „postponed“, „pushed back“) oder eine andere Release-Zeit als im Short („GTA 6 is finally out“)? Dann „raus“ für den Launch-Short (YouTube per Zapier privat, Instagram/TikTok löscht S in der App) und kein „Launch“-Short mehr einplanen, bis es stimmt. **Danach 12:00–21:30 fängt niemand einen Fehler ab** (Wächter urteilt erst ca. 20:47) | S im Chat | alle fünf Punkte beantwortet, sonst gilt der Stand von 11:30 |
| 12:47 | Clipping-Agent UND Einmal-Trigger „Leonida-Karte“ (gleiche Minute) | A | Karten-News nur aus offizieller Quelle; Zusatz-Short publishAt 15:00 (nicht 17:45–18:30); Clipping-Agent nur bei neuer Datei aktiv |
| **vor 11:30** | **Livewatch einschalten – NUR wenn** (1) Streamer-Kampagne oder schriftliche Erlaubnis existiert, (2) Steven **vor 11:30** im Chat ausdrücklich „Livewatch an“ sagt (danach ist er nicht erreichbar). Ablauf: `plan/gta6_launch.json` Feld `campaign` füllen; Kampagne in `plan/stats.json`, `plan/kampagnen.json` (`joined`) und `plan/waechter.json` eintragen; Kanal aus `livewatch_template` in `plan/livewatch.json` (`layout: native`, `max_clips` klein, `until`/`max_minutes`), `"enabled": true`, push auf `main` | **C** (nicht der Clipping-Agent: Livewatch-Dateien gehören einer eigenen Session) | Action `livewatch` läuft alle 20 Min; `clips/live-<kanal>/inbox.json` füllt sich; Repo-Größe < 3500 MB (Wächter) |
| 15:00 | Zusatz-Short „Leonida-Karte“ geht live (falls erzeugt) | vidIQ | YouTube/TikTok sichtbar |
| 17:17 + | stats-Lauf (vor dem Short; evtl. 50–90 Min später) | W | `stats/latest.md` jünger als 16 h |
| 18:00 | **Launch-Short geht live** (der Text sagt „GTA 6 is finally out“ – nur korrekt, wenn der Release-Check von 11:30 bestanden ist) | vidIQ | Post `completed` auf YouTube + TikTok bis 18:45; Wächter-Fenster 17:30–18:45 |
| 20:17 / 20:47 | stats + Wächter; 20:05 Issue für morgen | W | `alerts.md` ohne „Tages-Short“-Alarm |
| (jederzeit) | **Livewatch ausschalten:** `enabled: false` pushen reicht NICHT für einen laufenden/wartenden Lauf – zusätzlich Actions -> livewatch -> Lauf abbrechen | C oder S (Safari) | kein Lauf „in progress“, keine neuen Commits `livewatch: …` |
| 21:30+ | S wieder erreichbar: Live-Clips aus Livewatch NICHT heute posten (nach 19:30 verboten); mit „ja“ für Freitag 09:00/09:30 einplanen lassen | S + C | Slots Fr 20.11. 09:00 und 09:30 je Konto (max. 2 pro Konto/Tag) |

## Danach Fr 20.11.
- 09:00 / 09:30: erste Clips des Launch-Materials (nur mit „ja“, GTA 6 nur mit Rechteinhaber/Partner). Postplan-Eintrag je Clip durch den Clipping-Agenten (bzw. C). **S** reicht binnen 30 Min bei Content Rewards ein, Issue abhaken.
- 16:47: Einmal-Trigger „Rekord-Check“ (nur mit offiziellen Zahlen); publishAt 20:30 (nach 19:30, Entscheidung offen).

## Notfälle
| Fall | Erkennen | Sofortmaßnahme | Wer | Prüfkriterium danach |
|---|---|---|---|---|
| **Short fehlt** (18:00 nicht live) | **Vorbeugung:** S-Kontrolle bis 11:30 (Post `scheduled`?) – in der Schicht ist niemand erreichbar, der Wächter urteilt erst ca. 20:47. Alarm „Tages-Short“ oder Post nicht `completed` bis 18:45 | **Bis 11:30:** fehlt der Post, im Chat einplanen lassen (Auftrag fertig: `shorts/<name>.json` `ok: true`; sonst Render-Zeile unten; Reserve: `plan/countdown_plan.json` -> `spares` hat 2 fertige Skripte, aber keinen Render – nur Produzent-TEIL-B/Chat-Auftrag). **Nach 12:00:** nichts mehr zu retten, bis S wieder da ist. **Ab 21:30:** nach 19:30 wird nichts mehr gepostet; **S entscheidet**, ob das Short am nächsten Tag zu 18:00 nachgeholt wird (nie mehr als ein Short pro Tag) | S / C | Post live; Eintrag im Post-Log; Wächter-Alarm weg |
| **Render rot** (`ok: false` oder keine Datei) | `shorts/<name>.json` `ok:false`/`error`; Wächter „Render“ | Auftrag in `jobs/` prüfen, `shorts/<name>.json` löschen (löst Neurender aus), Action `render` von Hand starten (github.com -> Actions -> render -> Run workflow, Safari). 3 Versuche, dann gibt die Action still auf – Fehlertext aus dem Action-Log lesen | C | `ok: true`, `attempts` ≤ 3, mp4 + 3 QA-PNGs da |
| **Action tot** (Lauf zu alt) | Wächter „Action“ oder `updated` in `stats/latest.json` > 16 h; `alerts.md` `stand_utc` > 15 h = Wächter selbst tot | Safari -> github.com/pusnikg-media/pusnikg-media/actions -> betroffene Action (`stats`, `waechter`, `render`, `trendscout`, `kampagnen`) -> Run workflow. Cron kann 50–90 Min hängen: erst nach 2 h als tot behandeln. Bleibt es rot: Log lesen, im Chat melden | S (Starten), C (Ursache) | neuer Lauf grün UND `updated`/`stand_utc` frisch (Grün ≠ gut: Inhalt prüfen) |
| **Stats leer** | `stats/latest.md` ohne Posts, „problems“ in `latest.json` | Plattform unlesbar? Kurz warten, stats von Hand starten; Zahlen sind nur Info, **kein** Grund, ein Short zu stoppen. Instagram fehlt immer (`vidiq_instagram_owner_insights`). Privat geplante YouTube-Videos fehlen bis zur Planzeit (normal) | C | `latest.json` `updated` frisch; Wächter „Daten“-Alarm weg |
| **Schwelle/Alarm „Einreichen“** | Issue-Alarm, Clip nicht abgehakt (z. B. Warzone-Slots 17.11.–18.11. in der Spätschicht) | **S** reicht am nächsten Morgen nach (Content Rewards lehnt ggf. nach 30 Min ab – dann entscheidet S: Haken trotzdem setzen oder das Issue schließen (zählt als abgehakt); für einen bewusst nicht einreichbaren Clip eine Ausnahme unter `plan/waechter.json` -> `ignorieren` (Schlüssel `einreichen:…` aus dem Alarm). `plan/eingereicht.json` wird nie von Hand geändert) | S / C | Alarm weg |
| **Falscher Post live** | Nachricht von S: „raus“ | YouTube: Produzent/Chat setzt per Zapier-PUT auf privat (nur auf Stevens „raus“). Instagram/TikTok: S löscht in der App | C | YouTube-Video nicht mehr abrufbar |
