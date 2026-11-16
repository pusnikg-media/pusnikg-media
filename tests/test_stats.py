"""stats.py: Parser mit gespeicherten Beispielantworten (ohne Netz) + Verhalten bei Teilausfall (Risiko 2: stille Teildaten)."""
import json, os, shutil
import pytest
from conftest import load, ROOT

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture()
def st():
    return load("pipeline/stats/stats.py", "stats_t")


def test_selftest_of_script(st):
    st.selftest()


def test_youtube_rss_fixture(st):
    p = st.yt_rss(open(os.path.join(FIX, "yt_feed.xml"), "rb").read())
    assert [x["id"] for x in p] == ["abc123", "def456"]
    assert p[0]["views"] == 4900 and p[0]["likes"] == 12 and p[0]["published"] == "2026-11-15T18:00:28Z"


def test_tiktok_flat_fixture(st):
    p = st.flat(json.load(open(os.path.join(FIX, "tiktok_flat.json"))), "tiktok")
    assert len(p) == 2 and p[0]["views"] == 243 and p[1]["views"] is None   # ohne Views -> wird später aussortiert, nicht erfunden
    assert p[0]["published"].startswith("2026-")


def test_campaign_match_and_threshold_alert(st):
    cfg = {"campaigns": [{"name": "TJR", "match": ["#tjr"], "min_views": 5000}]}
    posts = st.yt_rss(open(os.path.join(FIX, "yt_feed.xml"), "rb").read())
    for q in posts: q["account"] = "Pusnik IRL"
    assert st.update(posts, {}, cfg) == []
    assert posts[0]["campaign"] == "TJR" and posts[0]["reached"] is False and "campaign" not in posts[1]


def _cfg_root(tmp_path):
    root = tmp_path / "repo"; (root / "plan").mkdir(parents=True); (root / "stats").mkdir()
    json.dump({"accounts": [{"name": "Pusnik G", "youtube": "UC1", "tiktok": "pusnikg"}], "campaigns": [], "scan": 5, "keep_days": 45}, open(root / "plan" / "stats.json", "w"))
    return root


def test_nothing_readable_keeps_old_files(st, tmp_path, monkeypatch):
    """Alles blockiert -> run() gibt 1 zurück und lässt latest.json UNVERÄNDERT (der Workflow bleibt grün: der Wächter muss 'updated' prüfen)."""
    root = _cfg_root(tmp_path); old = '{"updated": "2026-11-01T00:00:00Z", "posts": []}'
    open(root / "stats" / "latest.json", "w").write(old)
    monkeypatch.setattr(st, "get", lambda *a, **k: (_ for _ in ()).throw(OSError("blocked")))
    monkeypatch.setattr(st, "listing", lambda *a, **k: (None, "blocked"))
    assert st.run(str(root)) == 1
    assert open(root / "stats" / "latest.json").read() == old


def test_partial_failure_is_reported_in_problems(st, tmp_path, monkeypatch):
    """TikTok fällt aus, YouTube geht: latest.json enthält nur YouTube-Posts und eine problems-Zeile (der Wächter verlässt sich darauf)."""
    root = _cfg_root(tmp_path)
    monkeypatch.setattr(st, "get", lambda *a, **k: open(os.path.join(FIX, "yt_feed.xml"), "rb").read())
    monkeypatch.setattr(st, "listing", lambda url, n: (None, "HTTP 403") if "tiktok" in url else ([], ""))
    assert st.run(str(root)) == 0
    out = json.load(open(root / "stats" / "latest.json"))
    assert {p["platform"] for p in out["posts"]} == {"youtube"}
    assert any("TikTok" in x and "Pusnik G" in x for x in out["problems"]), out["problems"]
    assert os.path.exists(root / "stats" / "latest.md") and "Pusnik G" in open(root / "stats" / "latest.md").read()


def test_real_latest_json_is_parseable():
    d = json.load(open(os.path.join(ROOT, "stats", "latest.json")))
    assert {"updated", "accounts", "posts", "problems"} <= set(d)
