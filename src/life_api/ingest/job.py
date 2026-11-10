"""Daily ingestion job: Google Health -> S3 lake (raw + clean) -> DynamoDB."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Protocol

from life_api.domain import DailyHealth
from life_api.ingest.transform import build_daily_health
from life_api.storage.dynamo import LifeRepository
from life_api.storage.lake import Lake

log = logging.getLogger(__name__)
SOURCE = "google_health"


class HealthSource(Protocol):
    def list_data_points(
        self,
        data_type: str,
        *,
        filter: str | None = None,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict]: ...
    def daily_rollup(self, data_type: str, start: date, end: date) -> list[dict]: ...


def ingest_health_day(
    day: date, source: HealthSource, lake: Lake, repo: LifeRepository
) -> DailyHealth:
    nxt = day + timedelta(days=1)
    # Sleep belongs to the day you woke up, so filter on the session's end date.
    sleep = source.list_data_points(
        "sleep",
        filter=(
            f'sleep.interval.civil_end_time >= "{day.isoformat()}" '
            f'AND sleep.interval.civil_end_time < "{nxt.isoformat()}"'
        ),
        page_size=25,
    )
    steps = source.daily_rollup("steps", day, nxt)
    # The docs don't show the filter field for this daily type, so take the most
    # recent points (newest first, one page only) and match the date while parsing.
    # Covers backfills up to 30 days without re-reading the whole history daily.
    rhr = source.list_data_points("daily-resting-heart-rate", page_size=31, max_pages=1)

    lake.write_raw(SOURCE, "sleep", day, sleep)
    lake.write_raw(SOURCE, "steps_daily", day, steps)
    lake.write_raw(SOURCE, "resting_heart_rate", day, rhr)

    health = build_daily_health(day, sleep, steps, rhr)
    lake.write_records("daily_health", day, [health.model_dump(mode="json")])
    repo.upsert_day(day, health.model_dump(mode="json", exclude={"day"}))
    log.info("ingested %s: %s", day, health.model_dump(mode="json", exclude_none=True))
    return health


def export_applications_snapshot(day: date, lake: Lake, repo: LifeRepository) -> int:
    """Full daily snapshot of the tracker so dbt can model it (latest dt wins)."""
    apps = repo.list_applications()
    lake.write_records("applications", day, [a.model_dump(mode="json") for a in apps])
    return len(apps)
