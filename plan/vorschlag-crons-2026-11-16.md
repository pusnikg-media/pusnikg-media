# Vorschlag: verspätete GitHub-Crons (Session 2, 16.11.2026) – NUR Vorschlag, nichts umgesetzt

**Problem (gemessen 13.–16.11.):** Geplante Actions starten 50–90 Min zu spät, `render`/`clipfabrik` laufen statt alle 15/30 Min nur etwa 1×/h, Lücken bis 3 h. GitHub garantiert für `schedule` keine Pünktlichkeit; zur vollen Stunde und bei hoher Last ist es am schlimmsten. Mehr Cron-Zeilen helfen kaum.
**Gut:** Push-Auslöser (`jobs/`, `clipjobs/`) und `workflow_run` (Wächter nach stats) starten sofort. Claude-Aufgaben feuern pünktlich (gemessen ±1 Min).

## Empfehlung (Reihenfolge = Nutzen pro Aufwand)
1. **Agent startet die Action selbst (0 €, kein neues Konto).** Die Agenten haben den GitHub-Konnektor. Nach dem Ablegen eines Auftrags im Drive ruft der Agent `actions_run_trigger` (workflow_dispatch) für `render.yml` bzw. `clipfabrik.yml` auf, statt auf den Cron zu warten. Das sind ein Satz im Produzent-Prompt (TEIL B Schritt 7) und einer im Clipping-Agent-Prompt (Drive-Weg). Damit fällt das 50-Min-Warteproblem des Produzenten weg. Risiko: gering, nur Start eines vorhandenen Workflows. *Entscheidung Steven: diese Erlaubnis in die Prompts aufnehmen?*
2. **Livewatch startet beim Einschalten sofort:** in `livewatch.yml` einen `push`-Auslöser auf `plan/livewatch.json` ergänzen (wie `render` auf `jobs/`). Ein Lauf mit `enabled: false` endet sofort. Erst **nach** dem Launch und mit Test umsetzen, denn bis Do gilt die Regel „nichts auf main, was Donnerstag ändert“.
3. **Vorlauf als feste Regel behalten** (steht im Runbook): Aufträge ≥ 4 h vor der Postzeit; am Launch-Tag nichts auf den Cron verlassen.
4. **Crons weg von :00/:30 und Lastspitzen:** Die Minuten sind schon krumm (:17, :43). Zusätzlich könnte `render` von `*/15` auf wenige feste Zeiten **vor** den Bedarfspunkten gehen (z. B. 05:07, 06:07, 15:07, 16:07 UTC). Weniger Läufe, gleiche Wirkung, aber nur mit Punkt 1 sinnvoll.
5. **Externer Wecker (nur falls 1 nicht reicht):** ein kostenloser Dienst wie cron-job.org ruft pünktlich die GitHub-API `workflow_dispatch` auf. Dafür braucht es einen fein eingeschränkten GitHub-Token, der bei einem Fremddienst liegt. Das ist ein Sicherheitsrisiko, deshalb nicht empfohlen, solange 1 genügt.

Nicht empfohlen: eine Claude-Aufgabe nur zum Anstoßen von Actions (kostet Pro-Kontingent bei jedem Lauf).
