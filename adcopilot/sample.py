"""Generate a realistic, fictional ad-account export (Meta, Google, LinkedIn) for demos and tests.

Built-in stories to find: one Meta creative fatigues after week two, one Google campaign
wastes spend, and the LinkedIn lead-gen campaign is efficient but under-funded.
"""
from __future__ import annotations

import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

CAMPAIGNS = [
    # platform, campaign, creative, daily_spend, cpm, base_ctr, cvr, aov, fatigue
    ("meta", "Prospecting · DACH", "UGC video · morning routine", 180, 9.5, 0.014, 0.024, 54, True),
    ("meta", "Prospecting · DACH", "Static · before/after", 120, 9.5, 0.010, 0.016, 54, False),
    ("meta", "Retargeting · 30d visitors", "Carousel · bestsellers", 90, 12.0, 0.018, 0.040, 58, False),
    ("google", "Search · brand", "RSA · brand terms", 70, 40.0, 0.080, 0.080, 56, False),
    ("google", "Search · generic serum", "RSA · generic", 160, 60.0, 0.032, 0.012, 52, False),
    ("google", "Performance Max", "Asset group · all", 140, 12.0, 0.012, 0.025, 55, False),
    ("linkedin", "Lead gen · B2B salon owners", "Document ad · wholesale guide", 60, 38.0, 0.009, 0.120, 140, False),
]


def generate(days: int = 28, start: date = date(2026, 9, 1), seed: int = 7) -> list[dict]:
    rnd = random.Random(seed)
    rows = []
    for d in range(days):
        day = start + timedelta(days=d)
        for plat, camp, creative, spend, base_cpm, ctr, cvr, aov, fatigue in CAMPAIGNS:
            s = spend * rnd.uniform(0.85, 1.15)
            cpm = base_cpm * rnd.uniform(0.9, 1.1)
            impressions = int(s / cpm * 1000)
            reach = int(impressions / (1.2 + (0.12 * d if fatigue else 0.02 * d)))
            c = ctr * (math.exp(-0.06 * max(0, d - 12)) if fatigue else 1) * rnd.uniform(0.9, 1.1)
            clicks = int(impressions * c)
            conv = sum(1 for _ in range(clicks) if rnd.random() < cvr)
            rev = round(sum(aov * rnd.uniform(0.8, 1.3) for _ in range(conv)), 2)
            rows.append({
                "date": day.isoformat(), "platform": plat, "campaign": camp, "creative": creative,
                "spend": round(s, 2), "impressions": impressions, "reach": reach, "clicks": clicks,
                "conversions": conv, "revenue": rev,
            })
    return rows


def write(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "data" / "ads_export.csv"
    write(out, generate())
    print(f"Wrote {out}")
