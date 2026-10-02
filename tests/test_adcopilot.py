from types import SimpleNamespace

from adcopilot.analysis import aggregate, diagnose, reallocate
from adcopilot.report import ai_summary, build
from adcopilot.sample import generate

ROWS = [dict(r, **{k: float(r[k]) for k in ("spend", "impressions", "reach", "clicks", "conversions", "revenue")}) for r in generate()]


def test_metrics_math():
    s = aggregate([{"spend": 100.0, "impressions": 10000.0, "reach": 5000.0, "clicks": 200.0, "conversions": 10.0, "revenue": 400.0}], ())[()]
    assert (s.ctr, s.cpc, s.cpm, s.cvr, s.cpa, s.roas, s.frequency) == (0.02, 0.5, 10.0, 0.05, 10.0, 4.0, 2.0)


def test_finds_the_built_in_stories():
    dx = diagnose(ROWS, target_cpa=40, target_roas=1.5)
    text = " ".join(f"{f.where} {f.issue}" for f in dx.flags)
    assert "Creative fatigue" in text and "UGC video" in text
    assert any("generic serum" in f.where and f.level == "act" for f in dx.flags)
    assert any("Retargeting" in f.where and f.level == "watch" for f in dx.flags)


def test_reallocation_keeps_total_budget():
    camps = aggregate(ROWS, ("platform", "campaign"))
    plan = reallocate(camps, 40)
    assert plan and abs(sum(p["change_eur"] for p in plan)) < 0.05


def test_report_and_ai_summary():
    fake = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: SimpleNamespace(content=[SimpleNamespace(type="text", text="Good week.")])))
    md = build(ROWS, 40, 1.5, ai_summary("x", client=fake))
    assert "Good week." in md and "Budget shift" in md
