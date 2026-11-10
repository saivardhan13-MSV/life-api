"""Screen time: parse uploads from the phone and classify doomscrolling."""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import date
from typing import Any

from life_api.domain import AppUsage, ScreenTimeIn

# Infinite-feed apps. LinkedIn is deliberately excluded: during a job search it's work.
DOOMSCROLL_PACKAGES = frozenset(
    {
        "com.instagram.android",
        "com.instagram.barcelona",  # Threads
        "com.zhiliaoapp.musically",  # TikTok
        "com.ss.android.ugc.trill",  # TikTok (some regions)
        "com.google.android.youtube",
        "com.reddit.frontpage",
        "com.twitter.android",
        "com.facebook.katana",
        "com.snapchat.android",
        "com.pinterest",
    }
)


def is_doomscroll(package: str) -> bool:
    return package.strip().lower() in DOOMSCROLL_PACKAGES


def parse_csv(text: str) -> list[ScreenTimeIn]:
    """CSV with header ``date,package,app_name,minutes`` (app_name optional).

    Rows for the same day and package are summed, so exports with several
    sessions per app work too.
    """
    reader = csv.DictReader(io.StringIO(text))
    missing = {"date", "package", "minutes"} - set(reader.fieldnames or [])
    if missing:
        raise ValueError(f"CSV is missing columns: {sorted(missing)}")

    totals: dict[date, dict[str, list[Any]]] = defaultdict(dict)
    for row in reader:
        day = date.fromisoformat(row["date"].strip())
        pkg = row["package"].strip()
        entry = totals[day].setdefault(pkg, [row.get("app_name") or None, 0.0])
        entry[1] += float(row["minutes"])

    return [
        ScreenTimeIn(
            day=day,
            apps=[
                AppUsage(package=p, app_name=n, minutes=round(m, 2)) for p, (n, m) in apps.items()
            ],
        )
        for day, apps in sorted(totals.items())
    ]


def summarize(upload: ScreenTimeIn) -> tuple[list[dict[str, Any]], dict[str, float]]:
    """Return lake rows and the day totals stored on the DynamoDB day item."""
    rows = [
        {
            "day": upload.day.isoformat(),
            "package": a.package,
            "app_name": a.app_name,
            "minutes": a.minutes,
            "is_doomscroll": is_doomscroll(a.package),
        }
        for a in upload.apps
    ]
    totals = {
        "screen_minutes": round(sum(a.minutes for a in upload.apps), 1),
        "doomscroll_minutes": round(
            sum(a.minutes for a in upload.apps if is_doomscroll(a.package)), 1
        ),
    }
    return rows, totals
