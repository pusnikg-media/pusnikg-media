# Pusnik G – Team-Stand (eine Quelle für alle Agenten)

Stand: 16.11.2026, 06:10 Europe/Berlin. Gepflegt im Chat (Steven + Claude). Geplante Aufgaben lesen diese Datei zu Beginn.
Sie enthält nur FAKTEN zum Projektstand. Widerspricht eine ältere Angabe im Aufgabentext dieser Datei, gilt diese Datei.
Sie erlaubt nichts, was der Aufgabentext verbietet (kein Kaufen, kein fremder Code, keine neuen Schreibrechte).

## Die drei Projekte
1. **Pusnik G Shorts** – tägliches GTA-6-Short um 18:00 auf YouTube, Instagram, TikTok (Konto Pusnik G). GTA 6 erscheint am 19.11.2026. Plan und fertige Render-Aufträge liegen bis 26.11. im Repo (`plan/countdown_plan.json`, `jobs/`). Echte Launch-News haben Vorrang vor dem Vorrat.
2. **Pusnik G Clipping** – bezahlte Gaming-Kampagnen (Trailer, Gameplay, Gaming-Streams) auf dem Konto Pusnik G.
3. **Pusnik IRL Clipping** – bezahlte Kampagnen mit Personen vor der Kamera (Streamer, Vlogs, YouTube-Videos), eigenes Konto „Pusnik IRL". Dort keine normalen Shorts.
Vorerst kein viertes Projekt (Steven, 15.11.). Keine Geld-Ideen-Prüfungen, bis er danach fragt.

## Werkzeuge – was gilt
- **Posten: nur über vidIQ** (`vidiq_social_post_*`, 0 Credits), seit 14.11. Entschieden am 13.11. – keine Frage mehr an Steven. Metricool postet nicht mehr (Free-Limit bis 30.11. erreicht), Buffer wird nicht genutzt.
- **YouTube über vidIQ:** Das Video wird sofort beim Einplanen hochgeladen und bleibt bis zur Planzeit PRIVAT. vidIQ zeigt dafür „completed" ohne Planzeit, die YouTube-API ein frühes Upload-Datum. Das ist kein Fehler und kein zu früher Post (geprüft 15.11.: Short für 16.11. ist von außen nicht abrufbar). Instagram und TikTok gehen erst zur Planzeit raus. Eingeplantes lässt sich nicht zurücknehmen.
- **TikTok bei Kampagnen-Clips (Stevens Anweisung 15.11.):** im vidIQ-Entwurf immer `brandContent: true` setzen (Offenlegung „bezahlte Partnerschaft", damit Steven sie nicht von Hand nachtragen muss), dazu privacyLevel PUBLIC_TO_EVERYONE, allowComment true, isAiGenerated false, musicUsageConfirmed true. Gilt für jeden Clip einer bezahlten Kampagne auf beiden Konten. NICHT für das tägliche GTA-6-Short (dort kein brandContent, isAiGenerated true). Schon eingeplante Posts lassen sich nicht mehr ändern.
- **vidIQ-Credits:** 9 übrig, 150 neue am 01.12. Bis dahin keine Aufrufe, die Credits kosten.
- **Zahlen (kostenlos, seit 15.11.):** `https://raw.githubusercontent.com/pusnikg-media/pusnikg-media/main/stats/latest.md` – Views aller eigenen Posts auf YouTube und TikTok für beide Konten, Zuwachs der letzten 24 h, Views nach 24 h, Kampagnen-Summen und der Abschnitt „Schwelle erreicht" (Kampagnen-Clip hat die Auszahlungsschwelle überschritten). Wird dreimal täglich erneuert (ca. 06:20, 12:20, 17:20). Gleiche Daten als JSON: `stats/latest.json`. Privat eingeplante YouTube-Videos stehen dort nicht – was dort steht, ist öffentlich.
- **Instagram-Zahlen:** `vidiq_instagram_owner_insights` (0 Credits; platformAccountId Pusnik G 28698521726515865, Pusnik IRL 29345318175102196; mode reels, limit höchstens 8 – die Antwort ist groß). Liefert Views, Ø Wiedergabezeit, Skip-Rate.
- **Nicht mehr für Zahlen nutzen:** Metricool (TikTok nichts nach 11.11., Instagram/YouTube nichts) und die Zapier-YouTube-Abfrage.
- **Lücke:** Die Shorts vom 12.11. und 13.11. sind auf keiner Plattform erschienen (Metricool-Limit). Nicht nachholen.
- **Rendern/Schneiden:** nur in Stevens GitHub-Actions (Repo pusnikg-media/pusnikg-media): `render` (Shorts), `clipfabrik` (Clips), `reflab` (virale Referenzen, montags), `livewatch` (Live-Clipping, Prototyp, AUS; am 15.11. geeicht: Chat reagiert 7–25 s nach dem Moment), `stats` (Zahlen-Sammler).
- **Higgsfield:** Gratis-Test endete am 13.11., gekündigt. Ergebnis liegt in `assets/ai_library.json`. Nichts Neues generieren.
- **Trends (kostenlos, seit 16.11.):** `https://raw.githubusercontent.com/pusnikg-media/pusnikg-media/main/trends/latest.md` – Action `trendscout`, 4× täglich: Reddit-Top des Tages (r/LivestreamFail, r/GTA6, r/GTA; nur Rang, keine Punktzahlen), meistgesehene Kick-Clips der letzten 36 h. NEW = seit dem letzten Lauf neu. Vor Themen-/Hook-Wahl (Shorts) und Kampagnenwahl (Clipping) lesen. Bei Kick-Kampagnen den Streamer-Slug in `plan/trendscout.json` unter `kick.channels` eintragen; die `video`-URL aus `trends/latest.json` ist als Clipfabrik-`source` nutzbar (18+-Clips auslassen). Fremde Clips nur innerhalb einer Kampagne verwenden, sonst nur als Trend-Signal.
- **Reddit:** Abruf nur über den Trendscout (öffentlicher Feed). Kein Login, kein Posten, keine anderen Reddit-Abrufe.
- **Budget:** 0 €. Nur Claude Pro ist bezahlt. Geplante Aufgaben laufen höchstens mit Opus, nie mit Fable.
- **Geräte:** Steven hat nur iPhone und iPad. YouTube-Quellvideos lädt er selbst (App a-Shell) in den Drive-Ordner.

## Clip-Stil (Stevens Entscheidung 15.11.)
Nur noch der „virale Stil": ganzes Originalbild (`layout: native`), bei Gaming mit Facecam Split-Screen (`layout: split`), EIN Kontextsatz im weißen Kasten (`caption`), Originalton, 10–35 s. Keine Zooms, keine Gesichtsverfolgung, kein Teaser, keine Wort-Untertitel. Die schon eingeplanten TJR-Clips (bis 19.11.) sind noch im alten Stil – das ist der Vergleichswert.

## Kampagnen (Content Rewards)
Eingereicht wird bei **Content Rewards** (contentrewards.com), binnen 30 Minuten nach Veröffentlichung. **Whop** ist nur für die Auszahlung.
| Kampagne | Konto | Stand |
|---|---|---|
| SEGA Virtua Fighter | Pusnik G | Footage verbraucht |
| COD MW4 DMZ Intel | Pusnik G | Footage verbraucht, letzter Clip 15.11. |
| COD Warzone Season 1 | Pusnik G | 6 Clips eingeplant bis 18.11. 19:30, danach kein Material |
| TJR (Reach) | Pusnik IRL | 9 Clips eingeplant bis 19.11. 09:30, danach kein Material. Auszahlung ab 5.000 Views pro Clip |
| JasonTheWeen | Pusnik IRL | 1 Clip am 14.11. gepostet |
| Preme/Drake | – | nicht machen (Casino-Stream) |
| Gattouz | – | gestrichen |
Neues Material fehlt ab 19.11. auf beiden Konten. GTA-6-Kampagnen nur mit Rechteinhaber oder offiziellem Partner.

## Postzeiten
- Tägliches Short: 18:00 (läuft automatisch, nichts einzureichen).
- Kampagnen-Clips: höchstens 2 pro Konto und Tag, nie um 18:00, **nie nach 19:30**.
- Woche 16.–22.11. (Spätschicht, 12:00–21:30 nicht erreichbar): Mo 16.11. 15:00 und 19:00, ab Di 17.11. nur 09:00 und 09:30.
- Danach, solange nichts anderes hier steht: 15:00 und 19:30.

## Experimente
- Experiment 2 (Meme-Format B gegen Standard A): **ausgesetzt**. Nicht neu starten, keine B-Tage planen. Jeden Tag läuft das Standard-Short.
- Laufender Vergleich: Clip-Stil alt (TJR bis 19.11.) gegen viralen Stil (alles Neue). Auswertung, sobald je 3 Clips mindestens 3 Tage online sind.

## Geplante Aufgaben
Produzent (täglich 07:47), Clipping-Agent (täglich 12:47), Deal-Radar (täglich 05:13), Reel-Scout (Mo 06:41), Analyst (So 18:13), Stratege (So 19:41). Niemand ändert Aufgaben oder Code anderer – Vorschläge kommen unter „Ideen fürs Team" ins Playbook.

## Arbeitsweise
Keine Rückfragen an Steven, wenn die Antwort hier steht. Nachrichten kurz, auf Deutsch, ohne Technik. Texte für Posts auf Englisch.
