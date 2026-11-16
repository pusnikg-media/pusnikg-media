"""Wächter: jede Prüfung mit künstlichem Repo-Stand und festem 'jetzt' (kein Netz, keine Issues)."""
import datetime as dt, json, os
import pytest
from conftest import load, ROOT

W = load("waechter/waechter.py", "waechter_t")
REAL = json.load(open(os.path.join(ROOT, "plan", "waechter.json")))
CFG = dict(REAL, kampagnen=[])                                      # Kampagnen-Zahlen nur im eigenen Test
NOW = dt.datetime(2026, 11, 18, 5, 47, tzinfo=dt.timezone.utc)      # 06:47 Berlin, Mittwoch


def post(plat, pid, pub, camp=None, acc="Pusnik G", title="t"):
    p = {"platform": plat, "id": pid, "url": f"https://x/{plat}/{pid}", "account": acc, "published": pub, "title": title, "views": 10}
    if camp: p["campaign"] = camp
    return p


def repo(tmp_path, posts, updated="2026-11-18T05:20:00Z", problems=None, jobs=("2026-11-17",), eingereicht=None):
    r = tmp_path
    for d in ("stats", "trends", "campaigns", "plan", "jobs", "shorts", "clips"): os.makedirs(r / d, exist_ok=True)
    json.dump({"updated": updated, "accounts": {"Pusnik G": {}, "Pusnik IRL": {}}, "posts": posts, "problems": problems or ["Instagram: not collected"]}, open(r / "stats/latest.json", "w"))
    for f in ("trends", "campaigns"): json.dump({"at": "2026-11-18T04:00:00Z", "errors": [], "items": []}, open(r / f / "latest.json", "w"))
    json.dump(eingereicht or {"seit": "2026-11-16", "eingereicht": [], "nicht_noetig": []}, open(r / "plan/eingereicht.json", "w"))
    for d in jobs:
        n = f"pusnikg-{d}-x"; json.dump({"name": n, "date": d}, open(r / "jobs" / f"{n}.json", "w")); json.dump({"ok": True, "name": n}, open(r / "shorts" / f"{n}.json", "w"))
    return r


def keys(tmp_path, posts, now=NOW, runs=None, **kw):
    r = repo(tmp_path, posts, **kw); probs, uns = W.evaluate(str(r), CFG, now, runs)
    return sorted(p.key for p in probs), uns


SHORT_OK = [post("youtube", "y1", "2026-11-17T17:00:00Z"), post("tiktok", "t1", "2026-11-17T17:00:01Z")]


def test_all_fine(tmp_path):
    assert keys(tmp_path, SHORT_OK)[0] == []


def test_short_missing_on_tiktok(tmp_path):
    assert keys(tmp_path, SHORT_OK[:1])[0] == ["short:2026-11-17:tiktok"]


def test_short_not_judged_before_stats_catch_up(tmp_path):
    """Zahlen von 17:20 (vor dem 18:00-Post) dürfen keinen 'fehlt'-Alarm auslösen."""
    assert keys(tmp_path, [], updated="2026-11-17T16:20:00Z", now=dt.datetime(2026, 11, 17, 18, 47, tzinfo=dt.timezone.utc))[0] == []


def test_blind_platform_is_not_reported_as_missing(tmp_path):
    k, uns = keys(tmp_path, SHORT_OK[:1], problems=["Pusnik G TikTok: HTTP 403", "Instagram: x"])
    assert k == ["daten:stats:Pusnik G:tiktok"] and "Pusnik G tiktok" in uns       # EIN Daten-Alarm statt 'Short fehlt'


def test_stale_stats_is_reported_and_unsafe(tmp_path):
    k, uns = keys(tmp_path, SHORT_OK, updated="2026-11-17T05:20:00Z")
    assert "daten:stats:alt" in k and uns


def test_ignore_list_and_since(tmp_path):
    cfg = dict(CFG); r = repo(tmp_path, [], jobs=("2026-11-12", "2026-11-13"))
    probs, _ = W.evaluate(str(r), cfg, NOW, None)
    assert [p for p in probs if p.group == "short"] == []                           # vor 'seit' bzw. ignoriert
    cfg2 = dict(CFG, seit="2026-11-01", ignorieren=[]); probs, _ = W.evaluate(str(r), cfg2, NOW, None)
    assert {p.key for p in probs if p.group == "short"} == {f"short:2026-11-1{d}:{pl}" for d in (2, 3) for pl in ("youtube", "tiktok")}


def test_post_after_1930(tmp_path):
    late = [post("tiktok", "t9", "2026-11-17T18:50:00Z"), post("tiktok", "t8", "2026-11-17T18:30:01Z")]     # 19:50 / 19:30:01 (Toleranz)
    assert [k for k in keys(tmp_path, SHORT_OK + late)[0] if k.startswith("postzeit")] == ["postzeit:tiktok:t9"]


def test_campaign_post_needs_submission_note(tmp_path):
    cp = post("tiktok", "70010000001", "2026-11-17T08:00:00Z", camp="TJR", acc="Pusnik IRL")
    assert "einreichen:tiktok:70010000001" in keys(tmp_path, SHORT_OK + [cp])[0]
    ok = {"seit": "2026-11-16", "eingereicht": ["https://x/tiktok/70010000001"], "nicht_noetig": []}
    assert keys(tmp_path / "b", SHORT_OK + [cp], eingereicht=ok)[0] == []
    assert keys(tmp_path / "c", SHORT_OK + [cp], eingereicht={"seit": "2026-11-16", "eingereicht": [], "nicht_noetig": ["70010000001"]})[0] == []


def test_campaign_post_not_flagged_when_too_fresh_or_old(tmp_path):
    fresh = post("tiktok", "7002", "2026-11-18T05:30:00Z", camp="TJR"); old = post("tiktok", "7003", "2026-11-14T08:00:00Z", camp="TJR")
    assert keys(tmp_path, SHORT_OK + [fresh, old])[0] == []


def test_render_missing_for_upcoming_date(tmp_path):
    r = repo(tmp_path, SHORT_OK); json.dump({"name": "pusnikg-2026-11-19-x", "date": "2026-11-19"}, open(r / "jobs" / "pusnikg-2026-11-19-x.json", "w"))
    json.dump({"ok": False, "attempts": 3, "error": "tts"}, open(r / "shorts" / "pusnikg-2026-11-19-x.json", "w"))
    assert [p.key for p in W.evaluate(str(r), CFG, NOW, None)[0]] == ["render:2026-11-19"]


def test_clipjob_failed_and_missing(tmp_path):
    r = repo(tmp_path, SHORT_OK); os.makedirs(r / "clipjobs"); os.makedirs(r / "clips" / "bad")
    json.dump({"name": "bad", "source": "https://x/y.mp4", "clips": [{"id": "A", "a": 0, "b": 20, "title": "x"}]}, open(r / "clipjobs/bad.json", "w"))
    json.dump({"name": "nores", "source": "https://x/y.mp4", "clips": [{"id": "A", "a": 0, "b": 20, "title": "x"}]}, open(r / "clipjobs/nores.json", "w"))
    json.dump({"ok": False, "attempts": 3, "clips": [{"id": "A", "ok": False}], "error": "boom"}, open(r / "clips/bad/result.json", "w"))
    assert sorted(p.key for p in W.evaluate(str(r), CFG, NOW, None)[0]) == ["clipjob:bad:fehler", "clipjob:nores:fehlt"]


def run(name, concl, hours_ago):
    t = (NOW - dt.timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"status": "completed", "conclusion": concl, "updated_at": t, "html_url": "u"}


def test_actions_health(tmp_path):
    ok = {n: [run(n, "success", 1)] for n in CFG["max_alter_actions_stunden"]}
    assert keys(tmp_path, SHORT_OK, runs=ok)[0] == []
    bad = dict(ok, stats=[run("stats", "failure", 1), run("stats", "success", 5)], trendscout=[run("t", "success", 40)], reflab=None)
    k, uns = keys(tmp_path / "b", SHORT_OK, runs=bad)
    assert k == ["action:stats:fehler", "action:trendscout:alt"] and any("reflab" in u for u in uns)


def test_cancelled_runs_are_ignored(tmp_path):
    runs = {n: [run(n, "cancelled", 0), run(n, "success", 1)] for n in CFG["max_alter_actions_stunden"]}
    assert keys(tmp_path, SHORT_OK, runs=runs)[0] == []


def test_campaign_incomplete_after_end(tmp_path):
    r = repo(tmp_path, SHORT_OK + [post("youtube", "i1", "2026-11-17T09:00:00Z", camp="TJR", acc="Pusnik IRL")], eingereicht={"seit": "2026-11-16", "eingereicht": ["https://x/youtube/i1"], "nicht_noetig": []})
    os.makedirs(r / "clips" / "tjr4")
    json.dump({"ok": True, "phase": "rendered", "clips": [{"id": str(i), "ok": True} for i in range(9)]}, open(r / "clips/tjr4/result.json", "w"))
    late = dt.datetime(2026, 11, 20, 8, 0, tzinfo=dt.timezone.utc)
    k = {p.key for p in W.evaluate(str(r), dict(CFG, kampagnen=[k for k in REAL["kampagnen"] if k["name"] == "TJR"]), late, None)[0] if p.group == "kampagne"}
    assert k == {"kampagne:TJR:youtube", "kampagne:TJR:tiktok"}                      # 1 bzw. 0 von 9 live nach Ende


def test_markdown_only_open_problems(tmp_path):
    r = repo(tmp_path, SHORT_OK[:1]); probs, uns = W.evaluate(str(r), CFG, NOW, None)
    md = W.markdown(probs, uns, NOW)
    assert "Tages-Short nicht live" in md and "short:" not in md and "Keine offenen" not in md
    assert "Keine offenen Probleme" in W.markdown([], [], NOW)


class FakeGH(W.GH):
    def __init__(s, issues): s.issues, s.log = issues, []; s.repo = "r"
    def call(s, method, path, body=None):
        s.log.append((method, path.split("?")[0], body))
        return s.issues if method == "GET" else {}


def test_issue_sync_creates_updates_closes_without_duplicates():
    pr = lambda g, k, t: W.P(g, k, t)
    existing = [{"number": 1, "body": "<!-- waechter-group: short -->\n- alt", "pull_request": None},
                {"number": 2, "body": "<!-- waechter-group: render -->\n- x"}, {"number": 3, "body": "<!-- waechter-group: render -->\n- x"},
                {"number": 4, "body": "<!-- waechter-group: repo -->\n- y"}, {"number": 5, "body": "kein Wächter-Issue"}]
    existing[0].pop("pull_request")
    g = FakeGH(existing); g.sync_issues([pr("short", "k", "neu"), pr("einreichen", "e", "e1")], sicher=True)
    calls = [(m, p.rsplit("/", 1)[-1] if m != "POST" or "comments" in p else p, (b or {}).get("state") or (b or {}).get("title")) for m, p, b in g.log if m != "GET"]
    assert ("PATCH", "1", None) in calls                              # Issue short aktualisiert (Body geändert)
    assert ("PATCH", "3", "closed") in calls                          # doppeltes render-Issue geschlossen
    assert ("PATCH", "2", "closed") in calls and ("PATCH", "4", "closed") in calls   # nicht mehr vorhanden + sicherer Lauf
    assert any(m == "POST" and p == "/issues" and b["title"].startswith("Alarm: Kampagnen-Clip") for m, p, b in g.log)   # neues Issue
    assert not any(p.endswith("/5") for _, p, _ in g.log)


def test_issue_sync_never_closes_when_unsure():
    g = FakeGH([{"number": 9, "body": "<!-- waechter-group: short -->\n- alt"}]); g.sync_issues([], sicher=False)
    assert not [1 for m, p, b in g.log if m != "GET" and p.endswith("/9")]


def test_repo_size_alarm():
    assert W.check_repo(CFG, 1000) == [] and W.check_repo(CFG, None) == []
    assert [p.key for p in W.check_repo(CFG, 9000)] == ["repo:groesse"]


def test_fresh_jobs_get_grace_period(tmp_path):
    r = repo(tmp_path, SHORT_OK); os.makedirs(r / "clipjobs")
    json.dump({"name": "new", "source": "https://x/y.mp4", "clips": [{"id": "A", "a": 0, "b": 20, "title": "x"}]}, open(r / "clipjobs/new.json", "w"))
    assert [p.key for p in W.evaluate(str(r), CFG, NOW, None)[0]] == ["clipjob:new:fehlt"]
    assert W.evaluate(str(r), CFG, NOW, None, fresh=lambda p: p == "clipjobs/new.json")[0] == []


def test_campaign_platforms_respected(tmp_path):
    """Warzone läuft nur auf TikTok: fehlendes YouTube darf nach Kampagnen-Ende keinen Alarm geben."""
    r = repo(tmp_path, SHORT_OK + [post("tiktok", f"w{i}0000000", "2026-11-17T09:00:00Z", camp="Warzone S1") for i in range(6)])
    os.makedirs(r / "clips" / "wzs1"); json.dump({"ok": True, "phase": "rendered", "clips": [{"id": str(i), "ok": True} for i in range(6)]}, open(r / "clips/wzs1/result.json", "w"))
    cfg = dict(CFG, kampagnen=[k for k in REAL["kampagnen"] if k["name"].startswith("COD Warzone")])
    late = dt.datetime(2026, 11, 20, 8, 0, tzinfo=dt.timezone.utc)
    assert not [p for p in W.evaluate(str(r), cfg, late, None)[0] if p.group == "kampagne"]


def test_real_config_platforms_match_stats_reality():
    assert {k["name"]: k["plattformen"] for k in REAL["kampagnen"]}["COD Warzone Season 1"] == ["tiktok"]


def test_issue_gets_comment_when_new_problem_joins_open_group():
    g = FakeGH([{"number": 7, "body": "<!-- waechter-group: einreichen -->\n- alt eins\n\n_x_"}])
    g.sync_issues([W.P("einreichen", "a", "alt eins"), W.P("einreichen", "b", "neu zwei")], sicher=True)
    c = [b for m, p, b in g.log if m == "POST" and p.endswith("/7/comments")]
    assert len(c) == 1 and "neu zwei" in c[0]["body"] and "alt eins" not in c[0]["body"]
    g2 = FakeGH([{"number": 7, "body": "<!-- waechter-group: einreichen -->\n- alt eins\n- alt zwei\n\n_x_"}])
    g2.sync_issues([W.P("einreichen", "a", "alt eins")], sicher=True)           # nur etwas weggefallen: still aktualisieren, kein Kommentar
    assert not [1 for m, p, b in g2.log if m == "POST" and "comments" in p] and [1 for m, p, b in g2.log if m == "PATCH"]


def test_markdown_has_machine_readable_stand():
    assert "stand_utc: 2026-11-18T05:47:00Z" in W.markdown([], [], NOW)
