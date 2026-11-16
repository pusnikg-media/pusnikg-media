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
