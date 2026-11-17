# Sicherung der alten Trigger-Prompts (16.11.2026) – NUR Verzeichnis, Texte NICHT gesichert

**Ergebnis:** Alle Trigger wurden am 16.11. mit `list_triggers` vollständig gelesen (5 Seiten, kein Lesefehler). Das **wörtliche Abschreiben der Prompt-Texte in Dateien hat ein Sicherheitsfilter gestoppt**, und zwar gleich beim ersten Trigger (Produzent v4, `trig_01FXCTY479wKaQEJi6nqm3V3`). Laut Session-Anweisung wurde danach kein weiterer Versuch gemacht, auch nicht umformuliert. Die halbe Datei wurde gelöscht.
Zusätzlich gilt: Alle alten Agenten-Prompts nennen Stevens Nachnamen („Steven D…s Kanal …“). Eine wortgetreue Kopie würde gegen die Regel „Nachname in keine Datei“ verstoßen. Ins Repo (öffentlich) dürfen sie also ohnehin nur mit geschwärztem Namen.

**Was Steven tun muss (vor dem Tausch, ca. 1 Min je Agent):** In der Claude-App die geplante Aufgabe öffnen, den alten Prompt komplett markieren und kopieren und in Apple Notizen einfügen (Notiz „Pusnik Prompts alt 16.11.“). Erst danach den neuen Text einfügen. Reihenfolge und Zeitpunkt laut `plan/prompts/README.md`.

## Verzeichnis (Stand 16.11.2026, abends)
### Aktiv – werden getauscht (Kopie vor dem Tausch!)
| Agent | ID | Zeitplan (Berlin) | Modell | zuletzt geändert (UTC) |
|---|---|---|---|---|
| Produzent v4 (vidIQ-Posting) | trig_01FXCTY479wKaQEJi6nqm3V3 | täglich 07:47 | opus-5-5 | 16.11. 07:58 |
| Clipping-Agent | trig_015qi8bkxadQcVD1dcgDpAtY | täglich 12:47 | sonnet-5-5 | 16.11. 14:40 |
| Analyst | trig_01UUXKPpHRXUTBvCcNnmJHR6 | So 18:13 | sonnet-5-5 | 15.11. 17:36 |
| Stratege | trig_01DXNeBeF98XGq1oPTUSGb4Q | So 19:41 | opus-5-5 | 15.11. 17:31 |
| Deal-Radar | trig_01KN9vrY2Bnxj6EkCMrjbBFM | täglich 05:13 | sonnet-5-5 | 13.11. 18:21 |
| Reel-Scout | trig_018LqJdFzLxthmk6zFMMhYt6 | Mo 06:41 | opus-5-5 | 15.11. 15:03 |

### Aktiv – Einmal-Trigger (bleiben, werden nicht getauscht)
| Name | ID | Feuert (UTC) | Hinweis |
|---|---|---|---|
| Launch: Review-Roundup | trig_01T6UUwsQNstSsn1G58pJBm1 | 18.11. 14:47 (15:47 Berlin) | liest Produzent-Prompt TEIL B/C |
| Launch: Review-Roundup (2. Versuch) | trig_01KMiQJwaexu2LmUzoaH3q82 | 18.11. 20:17 (21:17 Berlin) | Post nach 19:30 (Entscheidung offen) |
| Launch: Leonida-Karte | trig_01H6hpArsGfv5EEBML7YSYDu | 19.11. 11:47 (12:47 Berlin) | publishAt 15:00 |
| Launch: Rekord-Check | trig_01RGUWsmHy98nzcfFhUooJuA | 20.11. 15:47 (16:47 Berlin) | publishAt 20:30 (nach 19:30) |
| Warzone-Clip D Links | trig_01Xp6RWdqJG9hp6A97XNt68e | 17.11. 14:03 | sagt „Whop“ (falsch) |
| Warzone-Clip E Links | trig_01XHeuPHeTWhPvHgPmPuDJuR | 17.11. 18:33 | sagt „Whop“ (falsch) |
| Warzone-Clip F Links | trig_01C2BG9GFuGxVUcwPGghW2ci | 18.11. 18:33 | sagt „Whop“ (falsch) |
| TJR-Clip D / TJR5-Clip B Links | trig_01QaWDJHb9yeaVMvf9T8yXaG / trig_01PqviXmu6MP9ThLXcABtAwR | 17.11. 08:03 / 08:33 | Content Rewards (richtig) |
| TJR-Clip C / TJR5-Clip C Links | trig_01PKJxsvdW3Pddfptq6V2deZ / trig_01XQA4Y2o83YWckfK1ZmYoXs | 18.11. 08:03 / 08:33 | Content Rewards (richtig) |
| TJR-Clip E / TJR5-Clip E Links | trig_01KyGsUZ4Svq5QvDmpdy6Qnr / trig_0161jS2LVAnKYzJCZTwo9tur | 19.11. 08:03 / 08:33 | Content Rewards (richtig) |

Hinweis: Die TJR-Erinnerungen sagen „jetzt bei Content Rewards einreichen“, aber nicht „danach im Issue abhaken“. Das ist harmlos, der Wächter mahnt es an.

### Aus / abgelaufen (nicht gesichert, keine Wirkung mehr)
Ausgeschaltete Dauer-Aufgaben: Higgsfield-Generator (`trig_01LfNQheKQF9ao8mrnkwcHGQ`), Produzent (Puck-Stimme) (`trig_01N9qrfezsk1tno499TWanaZ`), Produzent (inkl. Trend-Scout) (`trig_014bEyNgPdwXe3wEX1p64oSe`), Community (`trig_013s4TxJhmqKz1yhKhLjexUk`), Trend-Scout (`trig_01FrDQNSrJuN26Xi4GfA9c3v`). Dazu ca. 30 abgefeuerte Einmal-Erinnerungen (SEGA, MW4, Warzone A–C, TJR A/B, Fable-Sessions, Scan-Prüfungen …).

Nachtrag: Die vollständigen alten Texte stehen noch in den `list_triggers`-Antworten dieser Session (https://claude.ai/code/session_01TnYkY8Kjf9JTqX3Y93NDme) und bis zum Tausch in den Aufgaben selbst.
