# Zahlen-Diagnose Pusnik G – 16.11.2026 (Daten: stats/latest.json 18:31, history.json, campaigns/latest.json, refs/latest/report.json)

## Ergebnis zuerst
1. **TikTok hat eine harte Decke bei ca. 250 Views.** 36 von 43 TikTok-Posts liegen zwischen 150 und 450, Median 258. Kein einziger Post ≥ 2.500 (0 von 43), nur 1 von 43 ≥ 1.000 (Jan.-Weltraum-Post, 1.204).
2. **Verdienst bisher realistisch 0 $.** Kein Kampagnen-Clip über der Schwelle (`reached` = 0 überall). Rein rechnerische Obergrenze, falls jede View ohne Schwelle zählte: ca. 5–10 $ (5.854 Kampagnen-Views x 0,75–2 $/1K). Auszahlungsdaten (Whop) liegen nicht im Repo.
3. **Mit dem aktuellen Ansatz ist die Schwelle nicht realistisch.** Wir brauchen das 10–20-Fache der Decke und selbst ein Treffer zahlt nur ca. 4–6 $.
4. **Alter gegen viralen Clip-Stil: nicht messbar.** Bisher ist kein Clip im neuen Stil online (n = 0 neu, n = 2 alt auf TikTok).

## 1. Views pro Post (nur was die Daten hergeben)
| Konto / Plattform | n | Median | Spanne | Auffällig |
|---|---|---|---|---|
| G TikTok | 40 | 258 | 87 (neu, 30 Min alt) bis 1.204 | Streuung klein: 22 Nov.-Posts >24 h alt: Median 258 |
| G YouTube (datiert, >24 h) | 15 | 302 | 2 bis 1.342 | 4 von 15 ≥ 1.000; 4 Posts ≤ 25 Views |
| G YouTube (undatiert, Weltraum-Altbestand) | 24 | 1.100 | 19 bis 2.900 | 13 von 24 ≥ 1.000 – YouTube ist der Kanal mit Reichweite |
| IRL TikTok | 3 | 239 | 236 bis 849 | n zu klein |
| IRL YouTube | 3 | 1 | 0 bis 2 | praktisch tot |
| Instagram | – | – | – | nicht erfasst (Lücke) |
- **Plateau-Kurve (history.json):** TikTok erreicht ca. 240–265 Views nach 3–4 h und wächst dann um 0–10 in 1,5 Tagen (z. B. 98 nach 0,5 h, 263 nach 4 h, 267 nach 19 h). Das sieht nach einer festen Testgruppe ohne zweite Welle aus. Das ist eine Deutung der Kurve, bewiesen ist nur das Plateau.
- **Entwicklung:** Weltraum Jan./Feb. (n = 16): Median 315, 5 Posts ≥ 500, Like-Quote 3,5 %. GTA/Kampagne Nov. (n = 22): Median 258, Like-Quote 1,7 %. Schwächere Interaktion, die Reichweite ändert sich kaum.
- **Format/Uhrzeit/Länge:** Kein Zusammenhang erkennbar. Tages-Short (n = 14, Median 267, max 401) und Kampagnen-Clips auf G (n = 7, Median 256, max 277) sind gleich; alle Uhrzeiten landen bei ca. 250. Die Decke überdeckt jeden Effekt, die Stichprobe ist klein.
- **YouTube streut stark:** „Do This Before GTA 6 Spoilers Hit" 1.080 (756 nach 4 h), „Pre-Load Is Live" 2. Hook/Thema wirken dort. Ursache der 2–25er-Posts (Thema oder Verteilung) ist aus den Daten nicht zu trennen.

## 2. Schwellen gegen Realität
| Kampagne | Satz | Schwelle | Unser Bestwert | Anteil |
|---|---|---|---|---|
| TJR (IRL) | 0,75–1 $/1K | 5.000 | 239 (n = 2 TT) | 5 % |
| MW4 DMZ | 2 $/1K | 3.000 | 277 (n = 3) | 9 % |
| Warzone S1 | 2 $/1K | 2.500 | 244 (n = 2); Topf fast leer (1.000 $) | 10 % |
| SEGA VF | unbekannt | unbekannt | 1.279 YouTube | – |
| Jason-Pool (IRL) | Topf 9K $, 2.400 Clipper | – | 849 TikTok | Anteil ca. 0 |
- Selbst bei Schwelle erreicht: 3.000 Views x 2 $/1K = ca. 6 $, 5.000 x 1 $ = ca. 5 $. Treffer-Quote TikTok ≥ 2.500: 0 von 43 (95 %-Obergrenze ca. 7 %). Erwartung pro Clip: unter 0,40 $.
- Annahme: Schwelle gilt pro Clip (so in `plan/stats.json` für TJR). Bei Warzone/MW4 zahlt nur TikTok/Instagram, YouTube zählt dort nicht.

## 3. Stil alt gegen viral
- Alle bisher geposteten Kampagnen-Clips sind alter Stil (`layout: full`, Zoom/Untertitel). Ergebnis: TJR 236/239, Jason 849 (n = 3). Neuer Stil: n = 0.
- Referenzvergleich (reflab, n = 16 virale Fremd-Clips gegen 5 eigene, die Fremd-Clips sind nach Viralität ausgewählt): Referenz 25,6 s, 0 Schnitte/10 s, erster Schnitt 7,1 s, 1,3 Wörter/s. Wir 19,0 s, 0,5 Schnitte, erster Schnitt 3,0 s, 3,6 Wörter/s. Referenzen sind länger und ruhiger. Referenz-Median 251.100 Views (Like-Quote 6 %), das ist das ca. 1.000-Fache von uns. Der Stilunterschied erklärt das nicht allein, vermutlich zählt Konto-Reichweite mehr. Nicht belegt.
- Auffällig: Der einzige Ausreißer auf IRL (849) ist ein Jason-Clip. Lacy/Jason-Material liegt bei den Referenzen bei 310.000–884.000 Views (n = 3).

## 4. Ehrliche Einschätzung
- **Schwelle über Clipping auf diesen Konten:** nein, nicht in dieser Woche. Aufwand/Ertrag: ca. 30 Clips für ca. 0 $.
- **Mehr bringt bei gleichem Aufwand (Reihenfolge nach Datenlage):**
  a) **Weniger, bessere Clips statt 2/Tag/Konto.** Die Decke gilt für alle, mehr Posts schieben sie nicht.
  b) **Kampagnen mit niedriger Schwelle** (Radar: 750–1.000 Views, z. B. Viral Clips Streaming 3 $/1K ab 1K; Roblox 1 $/1K ab 1K). Aber: max. 1–3 $ pro Treffer, Töpfe 400–500 $, und nur 4 von 43 TikTok-Posts erreichen 849+. Kein Ausweg.
  c) **YouTube statt TikTok:** dort liegen die Treffer (4 von 15 ≥ 1.000, Altbestand Median 1.100). Aber die CoD-Kampagnen zahlen nur TikTok/IG. Für den Tages-Short ist YouTube der bessere Kanal.
  d) **Launch-Woche:** GTA-6-Nachfrage ist der einzige echte Hebel dieser Woche, dafür gibt es aber keinen bezahlten Anlass (keine GTA-Kampagne, Rechteinhaber nötig). Gilt für den Tages-Short, nicht für Geld.
  e) **IRL-Konto:** YouTube dort (n = 3, 0–2 Views) lohnt nicht, weglassen spart Arbeit.
- Grenzen: 1,5 Tage History, keine Instagram-Zahlen, keine Follower-Zahlen, keine Auszahlungsdaten. Daher Aussagen zu Zeit/Format nur als Hinweis.

## 5. Drei Experimente Launch-Woche (alle 0 €, keine Credits, nur mit Stevens „ja")
1. **Launch-Decke (Tages-Short 18:00, 17.–22.11., 6 Posts).** Frage: Bricht die TikTok-Decke bei Launch-News? Basis: 14 Tages-Shorts, Median 267, max 401. **Erfolg:** Median `views_24h` der 6 TikTok-Shorts ≥ 500 UND mind. 1 Short ≥ 1.000. **Wann/Quelle:** 24.11. 07:00, `stats/latest.json` (Feld `views_24h`). Misserfolg (Median < 350) = Decke hängt am Konto, nicht am Thema.
2. **Stil-Test an 3 neuen Clips (nur 09:00/09:30, 18.–20.11., Konto IRL, Material einer beigetretenen Kampagne (z. B. JasonTheWeen; fremdes Material ohne Kampagne nur als Trend-Signal)).** Neuer Stil (`native`, 1 Satz, Originalton, ungeschnitten 20–30 s), wie in den Referenzen. Basis: 2 TJR-Clips (236, 239) + 1 Jason-Clip (849). **Erfolg:** Median `views_72h` der 3 Clips ≥ 500 (2x Basis). **Wann/Quelle:** 23.11. 07:00, `stats/latest.json` (`views_72h`, Kampagne JasonTheWeen). Pool zahlt kaum, es geht nur um Reichweite.
3. **Instagram-Messung (kein Posten).** Frage: Liegt IG über der TikTok-Decke? Einmal `vidiq_instagram_owner_insights` (0 Credits, mode reels, limit 8, beide Konten). **Erfolg:** IG-Median ≥ 500 Views je Reel (2x TikTok) → IG vor TikTok priorisieren. **Wann/Quelle:** 17.11. und 23.11., vidIQ-Antwort, Median in `plan/` notieren. Stopp-Regel: Liegen Exp. 1 und 2 beide unter Erfolg, Clipping nach 23.11. einstellen und nur Tages-Short (YouTube zuerst) weiterführen.
