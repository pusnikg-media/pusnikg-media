# Überarbeitete Agenten-Prompts (Stand 16.11.2026, Block 5)

Nur Entwürfe in Dateien. **Kein Trigger wurde geändert.** Die Dateien liegen erst nach dem Merge auf `main` (Raw-URL `https://raw.githubusercontent.com/pusnikg-media/pusnikg-media/main/plan/prompts/<datei>`). Jede Datei: oben „Befunde zum alten Prompt“, darunter der komplette neue Prompt in einem `~~~~`-Block.

| Agent | Datei | Trigger-ID | Modell | Zeit (Berlin) | Was Steven tun muss |
|---|---|---|---|---|---|
| Produzent | `produzent.md` | `trig_01FXCTY479wKaQEJi6nqm3V3` | opus-5-5 | täglich 07:47 | Prompt ersetzen **VOR Di 17.11. 07:47** (dann plant er den Launch-Short für den 19.11. und braucht den Release-Check; vidIQ-Stand 16.11. abends: 19.–21.11. noch nicht eingeplant); Nummerierung/Name bleiben, die Einmal-Trigger sind nicht betroffen |
| Clipping-Agent | `clipping-agent.md` | `trig_015qi8bkxadQcVD1dcgDpAtY` | sonnet-5-5 | täglich 12:47 | Prompt ersetzen (jederzeit); Freigabe-Frage bestätigen; ab dann bei „wartet auf ja“-Clips im Chat „ja <Clip>“ schreiben |
| Analyst | `analyst.md` | `trig_01UUXKPpHRXUTBvCcNnmJHR6` | sonnet-5-5 | So 18:13 | nur Prompt ersetzen |
| Stratege | `stratege.md` | `trig_01DXNeBeF98XGq1oPTUSGb4Q` | opus-5-5 | So 19:41 | nur Prompt ersetzen (vor So 22.11.) |
| Deal-Radar | `deal-radar.md` | `trig_01KN9vrY2Bnxj6EkCMrjbBFM` | sonnet-5-5 | täglich 05:13 | Prompt ersetzen; Entscheidung 3 (Gedächtnis im Playbook) bestätigen |
| Reel-Scout | `reel-scout.md` | `trig_018LqJdFzLxthmk6zFMMhYt6` | opus-5-5 | Mo 06:41 | nur Prompt ersetzen (vor Mo 23.11.) |

## Einspielen (iPhone, pro Agent ca. 2 Min)
1. Datei auf github.com (Safari) oder in der GitHub-App öffnen -> „Raw“/Text ansehen.
2. Den Text ZWISCHEN den `~~~~`-Zeilen markieren und kopieren (nicht die `~~~~` selbst).
3. Claude-App/claude.ai -> Routinen/Geplante Aufgaben -> Aufgabe des Agenten öffnen -> Prompt komplett ersetzen -> Speichern. Name, Zeit, Modell, Konnektoren NICHT ändern.
4. Reihenfolge: die anderen fünf jederzeit; **Produzent VOR Di 17.11. 07:47** (er plant immer den ersten Tag ohne 18:00-Post, also am 17.11. den 19.11.; ohne neuen Prompt gibt es dafür keinen Release-Check). Die Einmal-Trigger „Review-Roundup“, „Leonida-Karte“, „Rekord-Check“ lesen seinen Prompt per `list_triggers`; der neue Text behält Namen und TEIL-/Schrittnummern (Release-Check steht als „SCHRITT 0c“), sie sind nicht betroffen. Kein Prompt ändert Zeit, Modell oder Konnektoren.

Hinweis: Die Länge des Routinen-Prompt-Felds ist nicht geprüft; der Clipping-Agent-Prompt (ca. 20 KB) ist länger als der alte. Lässt die App das Einfügen nicht zu, melden – dann wird er gekürzt.

## Entscheidungen, die nur Steven treffen kann
1. **Freigabe-Regel (wichtigster Konflikt).** CLAUDE.md: „Nie ohne Stevens ja veröffentlichen“. Die alten Prompts planen direkt fest ein (Produzent: Stevens Anweisung 13.11.; Clipping-Agent: 14.11.). Die neuen Prompts behalten die Dauer-Anweisung nur für das Tages-Short und TJR, Warzone, SEGA, MW4; JasonTheWeen (Kampagnenregeln: „Posten nur mit Freigabe“), GTA-6-/Livewatch- und neue Kampagnen-Clips nur mit „ja“. Der „ja“-Weg setzt voraus, dass der Chat Stevens „ja“ in die Notiz der Zeile im Clipping-Log (Playbook) einträgt – das steht in `plan/team_state.md` noch nicht und müsste dort ergänzt werden. **Bitte einmal im Chat bestätigen („Dauer-Freigabe gilt“) oder umstellen:** im Produzent den Absatz „FREIGABE (…)“ ersetzen durch: „FREIGABE: Entwurf anlegen, NICHT veröffentlichen; Steven per SendUserMessage um „ja“ bitten (er antwortet vor 11:30).“ Im Clipping-Agent NUR den ersten Satz des Absatzes „FREIGABE:“ (Dauer-Anweisung für TJR/Warzone/SEGA/MW4) löschen und durch „Alle Clips gehen den „ja“-Weg.“ ersetzen; den „ja“-Weg dahinter nicht löschen. Hinweis: In der Spätschicht-Woche (12:00–21:30 nicht erreichbar) verfehlt „nur mit ja“ den 18:00-Slot, wenn er nicht vor 11:30 antwortet.
2. **Zusatz-Shorts nach 19:30:** „Review-Roundup 2. Versuch“ (18.11. 21:17, Post frühestens ca. 21:32) und „Rekord-Check“ (20.11. publishAt 20:30) verstoßen gegen „nie nach 19:30“ (CLAUDE.md). Der Wächter ignoriert sie bereits (`plan/waechter.json` -> `ignorieren`). Entweder bewusst erlauben (dann Regel in team_state als Ausnahme eintragen) oder die zwei Einmal-Trigger auf publishAt ≤ 19:30 ändern bzw. ausschalten.
3. **Deal-Radar-Gedächtnis:** neu im Playbook statt `plan/deal_radar.json` im Repo (kein Schreibrecht nötig). Einverstanden?

## Sonst gefunden (nicht Teil der sechs Agenten, nur Hinweis)
- **Warzone-Erinnerungen D/E/F** (`trig_01Xp6RWdqJG9hp6A97XNt68e`, `trig_01XHeuPHeTWhPvHgPmPuDJuR`, `trig_01C2BG9GFuGxVUcwPGghW2ci`; 17.11. 15:03 und 19:33, 18.11. 19:33) sagen „in Whop einreichen“ – richtig ist **Content Rewards** (Whop nur Auszahlung). Zudem fehlt „danach im Issue abhaken“. Text per Hand ändern oder ausschalten.
- Warzone-Clips 17.11. 15:00/19:30 und 18.11. 19:30 sind in der Spätschicht eingeplant (nicht rücknehmbar): die 30-Min-Einreichfrist ist nicht zu halten -> Wächter-Alarm „Einreichen“ möglich (siehe Runbook).
- Einmal-Trigger „Review-Roundup“, „Leonida-Karte“, „Rekord-Check“ lesen den Produzent-Prompt per `list_triggers` und verweisen auf „TEIL B (Schritte 6–8)“ und „TEIL C (Schritte 9–11)“. Der neue Produzent-Prompt behält Namen und Nummerierung; Einspielzeitpunkt siehe oben (nach Fr 20.11. 16:47).
- Ausgeschaltet (Altlast, nichts zu tun): „Higgsfield-Generator“, „Community“, „Produzent (inkl. Trend-Scout)“, „Produzent (Puck-Stimme…)“, „Trend-Scout“.
