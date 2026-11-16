"""Lose JSON-Schemas (nur Pflichtfelder + Typen) für alles, was Agenten von Hand schreiben und Actions lesen.
Bewusst NICHT geprüft: plan/livewatch.json und plan/jason*.json (gehören der Livewatch-Session, würden deren Pushes rot machen)."""
import glob, json, os, re
import pytest
from jsonschema import Draft202012Validator
from conftest import ROOT

S = json.load(open(os.path.join(os.path.dirname(__file__), "schemas", "schemas.json")))
rel = lambda p: os.path.relpath(p, ROOT)
J = lambda p: json.load(open(p))


def check(schema, path):
    errs = sorted(Draft202012Validator(S[schema]).iter_errors(J(path)), key=lambda e: list(e.path))
    assert not errs, f"{rel(path)}: " + "; ".join(f"{'/'.join(map(str, e.path)) or '.'}: {e.message[:120]}" for e in errs[:4])


def files(pat): return sorted(glob.glob(os.path.join(ROOT, pat)))


@pytest.mark.parametrize("p", files("jobs/*.json"), ids=rel)
def test_render_jobs(p):
    check("job", p); j = J(p)
    assert j["name"] == os.path.basename(p)[:-5], "name != Dateiname: die Ergebnisdatei shorts/<name>.json passt sonst nicht"
    assert len(j["script"]) == len(j["shots"]), "eine Shot-Liste pro Skriptzeile"
    assert j["date"] in j["name"]
    for i in j.get("tiktok_lines", []): assert i < len(j["script"])


@pytest.mark.parametrize("p", [f for f in files("shorts/*.json") if "/qa/" not in f], ids=rel)
def test_short_results(p):
    check("short_result", p); r = J(p)
    if r["ok"]: assert r.get("urls", {}).get("video", "").startswith("https://raw.githubusercontent.com/"), "ok ohne Video-URL"


@pytest.mark.parametrize("p", files("clipjobs/*.json"), ids=rel)
def test_clipjobs(p):
    check("clipjob", p); assert J(p)["name"] == os.path.basename(p)[:-5]


@pytest.mark.parametrize("p", files("clips/*/result.json"), ids=rel)
def test_clip_results(p):
    check("clip_result", p)
    for c in J(p)["clips"]:
        if c["ok"]: assert c.get("url", "").endswith(".mp4"), f"{c['id']}: ok ohne url"


PLAN = {"plan/countdown_plan.json": "countdown_plan", "plan/kampagnen.json": "kampagnen", "plan/stats.json": "stats_plan",
        "plan/trendscout.json": "trendscout", "plan/reflab.json": "reflab", "plan/camtest.json": "camtest", "plan/gta6_launch.json": "gta6_launch",
        "stats/latest.json": "stats_latest", "trends/latest.json": "feed_latest", "campaigns/latest.json": "feed_latest"}


@pytest.mark.parametrize("rp", sorted(PLAN))
def test_plan_and_output_files(rp):
    check(PLAN[rp], os.path.join(ROOT, rp))


@pytest.mark.parametrize("rp,sch", [("plan/waechter.json", "waechter"), ("plan/eingereicht.json", "eingereicht"), ("plan/postplan.json", "postplan")])
def test_waechter_files(rp, sch):
    check(sch, os.path.join(ROOT, rp))


def test_countdown_plan_has_job_for_each_near_date():
    """Jedes Datum im Plan hat bis zum 26.11. ein Render-Auftrag (sonst fällt der Tages-Short aus)."""
    have = {J(p)["date"] for p in files("jobs/*.json")}
    plan = [e["date"] for e in J(os.path.join(ROOT, "plan/countdown_plan.json"))["entries"] if "2026-11-17" <= e["date"] <= "2026-11-26"]
    assert not [d for d in plan if d not in have], "Plan-Tage ohne jobs/*.json"


def test_no_credit_tools_in_workflows():
    """Tripwire: kein Workflow bekommt Schlüssel von Credit-/Bezahldiensten (vidIQ, Higgsfield, OpenAI, Anthropic) – ausser ai_assets."""
    for p in files(".github/workflows/*.yml"):
        t = open(p).read()
        assert not re.search(r"secrets\.(vidiq|higgsfield|openai|anthropic)", t, re.I) or p.endswith("ai_assets.yml"), rel(p)
