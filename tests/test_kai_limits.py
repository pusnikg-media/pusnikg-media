"""Kai-Cenat-Limits (19.11.2026): ein Satz Zahlen in waechter.json, kai_fenster.json, kai_reserve.json und kai-wache.md - sie widersprachen sich (8/Tag vs. max_pro_tag 4)."""
import json, os, re
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = lambda p: json.load(open(os.path.join(ROOT, p)))
hhmm = lambda t: int(t[:2]) * 60 + int(t[3:])
NAME = "Kai Cenat GTA 6"


def test_one_daily_limit_everywhere():
    cap = {k["name"]: k.get("max_pro_tag") for k in J("plan/waechter.json")["kampagnen"]}[NAME]
    f = J("plan/kai_fenster.json")
    assert cap == f["max_pro_tag"] == 8
    md = open(os.path.join(ROOT, "claude/kai-wache.md"), encoding="utf-8").read().replace("**", "")
    assert "höchstens 8 Kai-Posts pro Tag insgesamt" in md and "`max_pro_tag` steht auf 8" in md
    assert "hoechstens 8 pro Tag" in J("plan/kai_reserve.json")["note"] and "max. 4" not in J("plan/kai_reserve.json")["note"]


def test_windows_obey_the_rules():
    f = J("plan/kai_fenster.json"); gap_in, gap_between = f["abstand_im_fenster_min"], f["abstand_zwischen_posts_min"]
    assert f["pro_fenster"] == 2 and gap_in == 10 and gap_between == 60 and f["moment_max_alter_h"] == 4
    assert "2026-11-20" in f["tage"] and f["tage"]["2026-11-20"] == ["10:45", "13:15", "16:30", "19:00"]       # Stevens Pausen am Fr 20.11.
    for day, ws in f["tage"].items():
        assert re.fullmatch(r"\d{4}-\d\d-\d\d", day) and ws == sorted(ws) and len(ws) == len(set(ws))
        assert all(re.fullmatch(r"\d\d:\d\d", w) for w in ws)
        assert hhmm(ws[0]) >= hhmm(f["fruehestens"]) == 9 * 60                                                 # nichts vor 09:00
        assert hhmm(ws[-1]) + gap_in * (f["pro_fenster"] - 1) <= hhmm(f["spaetestens"]) == 19 * 60 + 30         # auch der zweite Post nie nach 19:30
        assert all(hhmm(b) - hhmm(a) >= gap_between + gap_in for a, b in zip(ws, ws[1:]))                      # Fenster liegen mind. 60 Min auseinander
        assert "18:00" not in ws and len(ws) * f["pro_fenster"] <= f["max_pro_tag"]                           # nie zur Short-Zeit, Fenster sprengen das Tageslimit nicht


def test_reserve_sits_in_windows_on_window_days():
    f = J("plan/kai_fenster.json"); r = J("plan/kai_reserve.json")["reserve"]
    seen = set()
    for x in r:
        assert (x["datum"], x["zeit"]) not in seen; seen.add((x["datum"], x["zeit"]))
        assert 9 * 60 <= hhmm(x["zeit"]) <= 19 * 60 + 30 and x["zeit"] != "18:00"
        if x["datum"] in f["tage"]: assert x["zeit"] in f["tage"][x["datum"]], x                              # Spaetschicht-Tag: nur Fensterzeiten
    assert len([x for x in r if x["datum"] == "2026-11-20"]) <= len(f["tage"]["2026-11-20"])                    # Reserve belegt je Fenster hoechstens den ersten Platz


def test_wache_doc_states_the_precedence():
    md = open(os.path.join(ROOT, "claude/kai-wache.md"), encoding="utf-8").read()
    for must in ("mindestens 60 Min zwischen zwei Posts", "Einzige Ausnahme (geht vor)", "10 Min auseinander", "Live-Clips (live + viewer-top, nach `score`) vor Reserve",
                 "bis 4 h alt", "Nichts vor 09:00", "10:45, 13:15, 16:30, 19:00", "Im Zweifel posten", "Ansehen statt Standbild"):
        assert must in md.replace("**", ""), must
