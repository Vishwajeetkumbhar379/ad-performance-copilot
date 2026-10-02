"""Weekly paid-media report: account overview, platform split, flags and a budget plan."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .analysis import aggregate, diagnose, load

MODEL = os.environ.get("ADCOPILOT_MODEL", "claude-sonnet-4-5")


def eur(v):
    return "n/a" if v is None else f"EUR {v:,.2f}"


def build(rows, target_cpa: float, target_roas: float, summary: str | None = None) -> str:
    tot = aggregate(rows, ())[()]
    dx = diagnose(rows, target_cpa, target_roas)
    days = sorted({r["date"] for r in rows})
    L = [
        "# Paid media weekly review",
        f"_{days[0]} to {days[-1]} · target CPA {eur(target_cpa)} · target ROAS {target_roas:.1f}x_",
        "",
        "| Spend | Revenue | ROAS | Conversions | CPA | CTR | CPM |",
        "|---:|---:|---:|---:|---:|---:|---:|",
        f"| {eur(tot.spend)} | {eur(tot.revenue)} | {tot.roas:.2f}x | {tot.conversions:,.0f} | {eur(tot.cpa)} | {tot.ctr:.2%} | {eur(tot.cpm)} |",
        "",
    ]
    if summary:
        L += ["## Summary", "", summary, ""]
    L += ["## By platform", "", "| Platform | Spend | ROAS | CPA | CTR | CVR | CPM |", "|---|---:|---:|---:|---:|---:|---:|"]
    for (p,), s in sorted(aggregate(rows, ("platform",)).items(), key=lambda kv: -kv[1].spend):
        L.append(f"| {p.title()} | {eur(s.spend)} | {s.roas:.2f}x | {eur(s.cpa)} | {s.ctr:.2%} | {s.cvr:.2%} | {eur(s.cpm)} |")
    L += ["", "## By campaign", "", "| Campaign | Platform | Spend | ROAS | CPA | Frequency |", "|---|---|---:|---:|---:|---:|"]
    for (p, c), s in sorted(aggregate(rows, ("platform", "campaign")).items(), key=lambda kv: -kv[1].roas):
        L.append(f"| {c} | {p} | {eur(s.spend)} | {s.roas:.2f}x | {eur(s.cpa)} | {s.frequency:.1f} |")
    L += ["", "## What needs attention", ""]
    for f in sorted(dx.flags, key=lambda f: f.level != "act"):
        L.append(f"- **{'Act' if f.level == 'act' else 'Watch'} · {f.where}.** {f.issue}. → {f.action}.")
    if dx.plan:
        L += ["", "## Budget shift for next week", "", "| Campaign | Change | Reason |", "|---|---:|---|"]
        for p in sorted(dx.plan, key=lambda p: p["change_eur"]):
            L.append(f"| {p['campaign']} ({p['platform']}) | {p['change_eur']:+,.2f} EUR | {p['why']} |")
        L += ["", "<sub>Moves at most 20% of a weak campaign's spend, weighted toward the most efficient campaigns. Same total budget.</sub>"]
    return "\n".join(L) + "\n"


def ai_summary(report_md: str, client=None) -> str:
    if client is None:
        import anthropic

        client = anthropic.Anthropic()
    msg = client.messages.create(
        model=MODEL, max_tokens=350,
        messages=[{"role": "user", "content": "You are a performance marketing lead. Write a 4-5 sentence summary of this weekly "
                   "review for the client: biggest win, biggest problem, what changes next week. Use only numbers in the report. "
                   "No bullet points.\n\n" + report_md}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="adcopilot", description="Weekly paid-media review with flags and a budget plan.")
    ap.add_argument("csv", type=Path)
    ap.add_argument("--target-cpa", type=float, required=True)
    ap.add_argument("--target-roas", type=float, default=2.0)
    ap.add_argument("--out", type=Path, default=Path("reports/weekly_review.md"))
    ap.add_argument("--ai", action="store_true", help="Add a Claude-written client summary")
    a = ap.parse_args(argv)
    rows = load(a.csv)
    md = build(rows, a.target_cpa, a.target_roas)
    if a.ai:
        if os.environ.get("ANTHROPIC_API_KEY"):
            md = build(rows, a.target_cpa, a.target_roas, ai_summary(md))
        else:
            print("Set ANTHROPIC_API_KEY for --ai", file=sys.stderr)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
