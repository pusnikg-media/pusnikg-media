"""Kai-Cenat-Limits (19.11.2026): ein Satz Zahlen in waechter.json, kai_fenster.json und kai_reserve.json - sie widersprachen sich (8/Tag vs. max_pro_tag 4).
Bewusst nur Zahlen-Invarianten (keine Textbausteine aus kai-wache.md, keine festen Tage): die Wache darf Reserve-Zeilen und Tage fortschreiben."""
import json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = lambda p: json.load(open(os.path.join(ROOT, p)))
hhmm = lambda t: int(t[:2]) * 60 + int(t[3:])
NAME = "Kai Cenat GTA 6"


def test_one_daily_limit_everywhere():
    cap = {k["name"]: k.get("max_pro_tag") for k in J("plan/waechter.json")["kampagnen"]}[NAME]
    f = J("plan/kai_fenster.json")
    assert cap == f["max_pro_tag"] == 8
    assert "max. 4" not in J("plan/kai_reserve.json")["note"]


def test_one_latest_post_time_everywhere():
    """19:30 gilt fuer jeden Postplan-Slot (Waechter + test_einreichen) - die 8/Tag-Zaehlung braucht je Post einen Slot, also darf kein Kai-Post spaeter liegen."""
    f = J("plan/kai_fenster.json")
    assert f["spaetestens"] == J("plan/waechter.json")["postzeit_ende"] == "19:30"
    assert f["fruehestens"] == "09:00"


def test_windows_obey_the_rules():
    f = J("plan/kai_fenster.json"); gap_in, gap_between = f["abstand_im_fenster_min"], f["abstand_zwischen_posts_min"]
    assert f["pro_fenster"] == 2 and gap_in == 10 and gap_between == 60 and f["moment_max_alter_h"] == 4
    assert f["tage"], "mindestens ein Fenster-Tag"
    for day, ws in f["tage"].items():
        assert re.fullmatch(r"\d{4}-\d\d-\d\d", day) and ws == sorted(ws) and len(ws) == len(set(ws))
        assert all(re.fullmatch(r"\d\d:\d\d", w) for w in ws)
        assert hhmm(ws[0]) >= hhmm(f["fruehestens"])                                                           # nichts vor 09:00
        assert hhmm(ws[-1]) + gap_in * (f["pro_fenster"] - 1) <= hhmm(f["spaetestens"])                        # auch der zweite Post nie nach 19:30
        assert all(hhmm(b) - hhmm(a) >= gap_between + gap_in for a, b in zip(ws, ws[1:]))                      # Fenster mind. 60 Min auseinander
        assert "18:00" not in ws and len(ws) * f["pro_fenster"] <= f["max_pro_tag"]                           # nie zur Short-Zeit, Fenster sprengen das Tageslimit nicht


def test_reserve_sits_in_windows_on_window_days():
    f = J("plan/kai_fenster.json"); r = J("plan/kai_reserve.json")["reserve"]
    seen = set()
    for x in r:
        assert (x["datum"], x["zeit"]) not in seen; seen.add((x["datum"], x["zeit"]))
        assert hhmm(f["fruehestens"]) <= hhmm(x["zeit"]) <= hhmm(f["spaetestens"]) and x["zeit"] != "18:00"
        if x["datum"] in f["tage"]:                                                                            # Fensterbeginn oder +10 Min (zweiter Platz)
            ok = {w for ws in f["tage"][x["datum"]] for w in (ws, "%02d:%02d" % divmod(hhmm(ws) + f["abstand_im_fenster_min"], 60))}
            assert x["zeit"] in ok, x
