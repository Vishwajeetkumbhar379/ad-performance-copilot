"""Paid-media maths and diagnostics across Meta, Google and LinkedIn exports."""
from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

NUM = ("spend", "impressions", "reach", "clicks", "conversions", "revenue")


def load(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in NUM:
            r[k] = float(r.get(k) or 0)
    return rows


@dataclass
class Stats:
    key: tuple
    spend: float = 0
    impressions: float = 0
    reach: float = 0
    clicks: float = 0
    conversions: float = 0
    revenue: float = 0

    def add(self, r: dict) -> None:
        for k in NUM:
            setattr(self, k, getattr(self, k) + r[k])

    ctr = property(lambda s: s.clicks / s.impressions if s.impressions else 0)
    cpc = property(lambda s: s.spend / s.clicks if s.clicks else 0)
    cpm = property(lambda s: s.spend / s.impressions * 1000 if s.impressions else 0)
    cvr = property(lambda s: s.conversions / s.clicks if s.clicks else 0)
    cpa = property(lambda s: s.spend / s.conversions if s.conversions else None)
    roas = property(lambda s: s.revenue / s.spend if s.spend else 0)
    frequency = property(lambda s: s.impressions / s.reach if s.reach else 0)


def aggregate(rows: list[dict], by: tuple[str, ...]) -> dict[tuple, Stats]:
    out: dict[tuple, Stats] = {}
    for r in rows:
        k = tuple(r[b] for b in by)
        out.setdefault(k, Stats(k)).add(r)
    return out


@dataclass
class Flag:
    level: str  # act | watch
    where: str
    issue: str
    action: str


@dataclass
class Diagnosis:
    flags: list[Flag] = field(default_factory=list)
    plan: list[dict] = field(default_factory=list)


def _window(rows, days_from_end: int, length: int):
    dates = sorted({r["date"] for r in rows})
    sel = set(dates[max(0, len(dates) - days_from_end - length): len(dates) - days_from_end])
    return [r for r in rows if r["date"] in sel]


def diagnose(rows: list[dict], target_cpa: float, target_roas: float = 2.0) -> Diagnosis:
    dx = Diagnosis()
    # 1. Creative fatigue: CTR down a lot while frequency climbs
    for (camp, cr), _ in aggregate(rows, ("campaign", "creative")).items():
        mine = [r for r in rows if r["campaign"] == camp and r["creative"] == cr]
        early = aggregate(sorted(mine, key=lambda r: r["date"])[:7], ("creative",))[(cr,)]
        late = aggregate(_window(mine, 0, 7), ("creative",))[(cr,)]
        if early.ctr and late.ctr < early.ctr * 0.75 and late.frequency > early.frequency * 1.3:
            dx.flags.append(Flag("act", f"{camp} · {cr}", f"Creative fatigue: CTR {early.ctr:.2%} → {late.ctr:.2%}, frequency {early.frequency:.1f} → {late.frequency:.1f}",
                                 "Rotate in 2-3 new creatives with the same hook; cap frequency or widen the audience"))
    # 2. Wasted spend and efficiency by campaign
    camps = aggregate(rows, ("platform", "campaign"))
    for (plat, camp), s in camps.items():
        if s.cpa is None and s.spend > 2 * target_cpa:
            dx.flags.append(Flag("act", camp, f"EUR {s.spend:,.0f} spent with no conversions", "Pause, check tracking and landing page"))
        elif s.cpa and s.cpa > target_cpa * 1.5:
            dx.flags.append(Flag("act", camp, f"CPA EUR {s.cpa:,.2f} vs target EUR {target_cpa:,.2f} · ROAS {s.roas:.2f}",
                                 "Cut budget; tighten keywords or audiences and test a new landing page"))
        elif s.cpa and s.cpa < target_cpa * 0.7 and s.roas >= target_roas:
            dx.flags.append(Flag("watch", camp, f"Strong: CPA EUR {s.cpa:,.2f}, ROAS {s.roas:.2f}", "Scale budget 15-20% and watch CPA for 3-4 days"))
    # 3. Recent CPA spike (last 3 days vs the 7 days before)
    for (plat, camp), _ in camps.items():
        mine = [r for r in rows if r["campaign"] == camp]
        recent = aggregate(_window(mine, 0, 3), ("campaign",)).get((camp,))
        before = aggregate(_window(mine, 3, 7), ("campaign",)).get((camp,))
        if recent and before and recent.cpa and before.cpa and recent.cpa > before.cpa * 1.4:
            dx.flags.append(Flag("watch", camp, f"CPA up {recent.cpa / before.cpa - 1:.0%} in the last 3 days", "Check auction changes, creative fatigue and tracking"))
    dx.plan = reallocate(camps, target_cpa)
    return dx


def reallocate(camps: dict[tuple, Stats], target_cpa: float, max_move: float = 0.2) -> list[dict]:
    """Move up to 20% of budget from expensive campaigns to efficient ones, weighted by efficiency."""
    donors = {k: s for k, s in camps.items() if s.cpa is None or s.cpa > target_cpa * 1.3}
    takers = {k: s for k, s in camps.items() if s.cpa and s.cpa < target_cpa * 0.8}
    pool = sum(s.spend * max_move for s in donors.values())
    if not donors or not takers or not pool:
        return []
    weight = {k: target_cpa / s.cpa for k, s in takers.items()}
    wsum = sum(weight.values())
    plan = [{"campaign": k[1], "platform": k[0], "change_eur": -round(s.spend * max_move, 2), "why": "CPA above target" if s.cpa else "no conversions"}
            for k, s in donors.items()]
    plan += [{"campaign": k[1], "platform": k[0], "change_eur": round(pool * weight[k] / wsum, 2), "why": f"CPA EUR {s.cpa:,.2f}"}
             for k, s in takers.items()]
    return plan
