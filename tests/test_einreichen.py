"""Einreich-Issues (waechter/einreichen.py): Haken -> plan/eingereicht.json, Tages-Issue, Wächter-Zuordnung per Slot. Alles mit gefälschtem GitHub-Client."""
import datetime as dt, json, os, re
import pytest
from conftest import load, ROOT

E = load("waechter/einreichen.py", "einreichen_t"); W = E.W
REAL = json.load(open(os.path.join(ROOT, "plan", "waechter.json")))
NOW = dt.datetime(2026, 11, 17, 5, 47, tzinfo=dt.timezone.utc)                 # 06:47 Berlin, Di 17.11. (erster Wächter-Lauf nach dem 16.11.)
BOT = "github-actions[bot]"


def post(plat, pid, pub, camp, acc):
    return {"platform": plat, "id": pid, "url": f"https://x/{plat}/{pid}", "account": acc, "published": pub, "title": "t", "views": 5, "campaign": camp}


# die vier Kampagnen-Posts vom 16.11. (15:00/19:00/19:30 Berlin = 14:00/18:00/18:30 UTC), nur im 05:17-Lauf des 17.11. sichtbar
FOUR = [post("tiktok", "t15irl", "2026-11-16T14:00:01Z", "TJR", "Pusnik IRL"), post("youtube", "y15irl", "2026-11-16T14:00:20Z", "TJR", "Pusnik IRL"),
        post("tiktok", "t15g", "2026-11-16T14:00:02Z", "Warzone S1", "Pusnik G"), post("tiktok", "t19irl", "2026-11-16T18:00:03Z", "TJR", "Pusnik IRL"),
        post("tiktok", "t1930g", "2026-11-16T18:30:04Z", "Warzone S1", "Pusnik G")]
SLOTS16 = ["Pusnik IRL|TJR|2026-11-16|15:00", "Pusnik G|COD Warzone Season 1|2026-11-16|15:00", "Pusnik IRL|TJR|2026-11-16|19:00", "Pusnik G|COD Warzone Season 1|2026-11-16|19:30"]


def repo(tmp_path, posts, eingereicht, slots=None, updated="2026-11-17T05:20:00Z"):
    r = tmp_path
    for d in ("stats", "plan"): os.makedirs(r / d, exist_ok=True)
    json.dump({"updated": updated, "accounts": {"Pusnik G": {}, "Pusnik IRL": {}}, "posts": posts, "problems": []}, open(r / "stats/latest.json", "w"))
    json.dump(dict({"seit": "2026-11-16", "eingereicht": [], "nicht_noetig": []}, **eingereicht), open(r / "plan/eingereicht.json", "w"))
    json.dump({"slots": slots if slots is not None else json.load(open(os.path.join(ROOT, "plan/postplan.json")))["slots"]}, open(r / "plan/postplan.json", "w"))
    json.dump(REAL, open(r / "plan/waechter.json", "w"))
    return str(r)


def alarms(root, now=NOW):
    st = W.jl(os.path.join(root, "stats/latest.json")); return sorted(p.key for p in W.check_einreichen(root, REAL, now, st, set()))


def test_ticked_slots_clear_the_posts_of_the_day(tmp_path):
    """Kern des Auftrags: 16.11. abgehakt, Stats 05:20Z mit den vier Posts, Wächter 05:47Z -> kein einreichen-Alarm."""
    assert alarms(repo(tmp_path, FOUR, {"slots": SLOTS16})) == []


def test_unticked_posts_alarm(tmp_path):
    assert len(alarms(repo(tmp_path, FOUR, {"slots": []}))) == 5


def test_nearest_slot_separates_0900_and_0930(tmp_path):
    ps = [post("tiktok", "a0900", "2026-11-17T08:00:02Z", "TJR", "Pusnik IRL"), post("tiktok", "b0930", "2026-11-17T08:30:02Z", "TJR", "Pusnik IRL")]
    assert alarms(repo(tmp_path, ps, {"slots": ["Pusnik IRL|TJR|2026-11-17|09:00"]}), now=dt.datetime(2026, 11, 17, 11, 0, tzinfo=dt.timezone.utc)) == ["einreichen:tiktok:b0930"]


def test_wrong_account_or_campaign_not_cleared(tmp_path):
    ps = [post("tiktok", "x1", "2026-11-17T08:00:02Z", "TJR", "Pusnik G")]
    assert alarms(repo(tmp_path, ps, {"slots": ["Pusnik IRL|TJR|2026-11-17|09:00"]}), now=dt.datetime(2026, 11, 17, 11, 0, tzinfo=dt.timezone.utc)) == ["einreichen:tiktok:x1"]


def test_post_ids_in_file_still_count(tmp_path):
    assert alarms(repo(tmp_path, FOUR[:1], {"posts": ["tiktok|t15irl"]})) == []


# ---------- Issue-Zyklus mit gefälschtem GitHub ----------
class FakeHTTP(Exception):
    def __init__(self, code): self.code = code


class FakeGH:
    def __init__(self): self.issues, self.n, self.comments = [], 0, []
    def call(self, method, path, body=None):
        if path == "/labels": raise FakeHTTP(422)
        if path.startswith("/issues?"): return [dict(i) for i in sorted(self.issues, key=lambda i: -i["number"])]
        if path == "/issues" and method == "POST":
            self.n += 1; i = {"number": self.n, "state": "open", "user": {"login": BOT}, "title": body["title"], "body": body["body"], "labels": body["labels"]}; self.issues.append(i); return dict(i)
        m = re.match(r"/issues/(\d+)(/comments)?$", path); i = next(x for x in self.issues if x["number"] == int(m.group(1)))
        if m.group(2): self.comments.append((i["number"], body["body"])); return {}
        if method == "PATCH": i.update({k: v for k, v in body.items() if k in ("body", "state", "title")}); return dict(i)
        return dict(i)
    def tap(self, number, key):                                              # Steven hakt in der App ab
        i = next(x for x in self.issues if x["number"] == number); i["body"] = i["body"].replace(f"- [ ] ", "- [x] ", 1) if key is None else re.sub(r"- \[ \](.*<!-- k:" + re.escape(key) + r" -->)", r"- [x]\1", i["body"])


NOW16 = dt.datetime(2026, 11, 16, 13, 30, tzinfo=dt.timezone.utc)


def test_first_issue_lists_todays_four_clips(tmp_path):
    root, gh = repo(tmp_path, [], {}), FakeGH()
    E.run(gh, root, REAL, NOW16)
    today = next(i for i in gh.issues if "einreichen-day: 2026-11-16" in i["body"])
    keys = list(E.parse_body(today["body"]))
    assert keys == [f"slot|{s}" for s in sorted(SLOTS16, key=lambda s: s.split("|")[3])] or sorted(keys) == sorted(f"slot|{s}" for s in SLOTS16)
    assert all(not v for v in E.parse_body(today["body"]).values()) and "Frist 15:30" in today["body"]
    assert any("einreichen-day: 2026-11-17" in i["body"] for i in gh.issues)       # morgen auch schon da
    assert not any("einreichen-day: 2026-11-15" in i["body"] for i in gh.issues)   # gestern nur, wenn es das Issue schon gibt


def test_tick_sync_writes_file_and_closes_when_all_done(tmp_path):
    root, gh = repo(tmp_path, [], {}), FakeGH(); E.run(gh, root, REAL, NOW16)
    num = next(i["number"] for i in gh.issues if "einreichen-day: 2026-11-16" in i["body"])
    for s in SLOTS16: gh.tap(num, f"slot|{s}")
    assert E.run(gh, root, REAL, NOW16) is True
    f = json.load(open(os.path.join(root, "plan/eingereicht.json")))
    assert sorted(f["slots"]) == sorted(SLOTS16)
    assert next(i for i in gh.issues if i["number"] == num)["state"] == "closed"
    assert E.run(gh, root, REAL, NOW16) is False                                  # nichts Neues


def test_ticks_are_monotonic_and_survive_body_rewrite(tmp_path):
    """Haken nur in der Datei (Issue-Text wurde überschrieben) -> Bot rendert die Vereinigung, nichts geht verloren."""
    root, gh = repo(tmp_path, [], {"slots": [SLOTS16[0]]}), FakeGH(); E.run(gh, root, REAL, NOW16)
    t = next(i for i in gh.issues if "einreichen-day: 2026-11-16" in i["body"])
    assert E.parse_body(t["body"])[f"slot|{SLOTS16[0]}"] is True


def test_live_links_filled_in_and_unplanned_post_gets_own_line_and_reopens(tmp_path):
    root, gh = repo(tmp_path, [], {}), FakeGH(); E.run(gh, root, REAL, NOW16)
    num = next(i["number"] for i in gh.issues if "einreichen-day: 2026-11-16" in i["body"])
    for s in SLOTS16: gh.tap(num, f"slot|{s}")
    E.run(gh, root, REAL, NOW16)
    assert gh.issues[num - 1]["state"] == "closed"
    extra = post("tiktok", "999000111", "2026-11-16T16:00:00Z", "TJR", "Pusnik IRL")               # 17:00 Berlin, in keinem Plan
    json.dump({"updated": "2026-11-16T16:20:00Z", "accounts": {}, "posts": FOUR + [extra], "problems": []}, open(os.path.join(root, "stats/latest.json"), "w"))
    E.run(gh, root, REAL, NOW16 + dt.timedelta(hours=4))
    i = gh.issues[num - 1]
    assert i["state"] == "open" and "post|tiktok|999000111" in i["body"] and "https://x/tiktok/t15irl" in i["body"]
    assert any("999000111" in c[1] for c in gh.comments)                                              # Kommentar = Benachrichtigung


def test_foreign_and_unmarked_issues_are_ignored():
    forged = {"number": 9, "state": "open", "user": {"login": "stranger"}, "body": "<!-- einreichen-day: 2026-11-16 -->\n- [x] a <!-- k:slot|Pusnik G|X|2026-11-16|15:00 -->"}
    plain = {"number": 8, "state": "open", "user": {"login": BOT}, "body": "- [x] a <!-- k:slot|Pusnik G|X|2026-11-16|15:00 -->"}
    assert E.issue_ticks([forged, plain], REAL) == set()


def test_closed_issue_counts_as_all_ticked():
    body = E.render_body("2026-11-16", [{"key": "slot|Pusnik G|X|2026-11-16|15:00", "zeit": "15:00", "text": "t"}], set())
    assert E.issue_ticks([{"number": 1, "state": "closed", "user": {"login": BOT}, "body": body}], REAL) == {"slot|Pusnik G|X|2026-11-16|15:00"}


def test_write_file_only_adds(tmp_path):
    root = repo(tmp_path, [], {"slots": ["a|b|2026-11-16|09:00"], "eingereicht": ["keep"]})
    assert E.write_file(root, {"slot|c|d|2026-11-16|09:30", "post|tiktok|123456"}) is True
    f = json.load(open(os.path.join(root, "plan/eingereicht.json")))
    assert f["slots"] == ["a|b|2026-11-16|09:00", "c|d|2026-11-16|09:30"] and f["posts"] == ["tiktok|123456"] and f["eingereicht"] == ["keep"]
    assert E.write_file(root, {"slot|c|d|2026-11-16|09:30"}) is False


# ---------- Daten ----------
def test_postplan_is_consistent_with_repo():
    plan = json.load(open(os.path.join(ROOT, "plan/postplan.json")))["slots"]
    names = {k["name"] for k in REAL["kampagnen"]}; konten = {"Pusnik G", "Pusnik IRL"}
    seen = set()
    for s in plan:
        assert s["kampagne"] in names and s["konto"] in konten, s
        assert re.fullmatch(r"\d\d:\d\d", s["zeit"]) and s["zeit"] <= REAL["postzeit_ende"], f"nie nach 19:30: {s}"
        assert s["zeit"] != "18:00", "nie zur Short-Zeit"
        k = (s["konto"], s["datum"], s["zeit"]); assert k not in seen, f"zwei Clips im selben Slot: {k}"; seen.add(k)
        job, cid = s["clip"].split("/")
        res = json.load(open(os.path.join(ROOT, "clips", job, "result.json")))
        assert cid in [c["id"] for c in res["clips"]], f"{s['clip']} nicht gerendert"
    for konto in konten:                                                                                   # höchstens 2 pro Konto und Tag
        for d in {s["datum"] for s in plan}: assert sum(1 for s in plan if s["konto"] == konto and s["datum"] == d) <= 2, (konto, d)


# ---------- Postplan gegen Live: Slot nicht rausgegangen ----------
def live_keys(root, now=NOW, blind=()):
    st = W.jl(os.path.join(root, "stats/latest.json")); return sorted(p.key for p in W.check_slots_live(root, REAL, now, st, set(blind)))


FULL = FOUR + [post("youtube", "y19irl", "2026-11-16T18:00:25Z", "TJR", "Pusnik IRL")]                  # alle YouTube/TikTok-Posts der vier Slots


def test_slots_live_all_present(tmp_path):
    assert live_keys(repo(tmp_path, FULL, {})) == []


def test_slot_missing_on_platform_is_reported(tmp_path):
    root = repo(tmp_path, [p for p in FULL if p["id"] != "t19irl"], {})
    assert live_keys(root) == ["live:2026-11-16:19:00:Pusnik IRL:tiktok"]


def test_slot_not_judged_early_or_with_old_numbers(tmp_path):
    early = dt.datetime(2026, 11, 16, 15, 30, tzinfo=dt.timezone.utc)                           # 16:30 Berlin: 15:00-Slots noch keine 2 h alt
    assert live_keys(repo(tmp_path, [], {}, updated="2026-11-16T15:20:00Z"), now=early) == []
    assert live_keys(repo(tmp_path / "b", [], {}, updated="2026-11-16T12:27:00Z"), now=NOW) == []   # Zahlen vor der Planzeit gemessen


def test_slot_blind_platform_and_instagram_skipped(tmp_path):
    root = repo(tmp_path, [], {}, slots=[{"datum": "2026-11-16", "zeit": "15:00", "konto": "Pusnik IRL", "kampagne": "TJR", "clip": "tjr5/A_key", "plattformen": ["tiktok", "instagram", "youtube"]}])
    assert live_keys(root) == ["live:2026-11-16:15:00:Pusnik IRL:tiktok", "live:2026-11-16:15:00:Pusnik IRL:youtube"]
    assert live_keys(root, blind=[("Pusnik IRL", "tiktok")]) == ["live:2026-11-16:15:00:Pusnik IRL:youtube"]
