from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query, status

from life_api.api.deps import LakeDep, RepoDep, SettingsDep
from life_api.domain import DaySummary, ScreenTimeIn, ScrollSleepInsight
from life_api.ingest import screen_time
from life_api.services.summary import scroll_vs_sleep

router = APIRouter(prefix="/v1", tags=["days"])
MAX_RANGE_DAYS = 366


@router.get("/days")
def list_days(
    repo: RepoDep,
    settings: SettingsDep,
    start: date | None = None,
    end: date | None = None,
) -> list[DaySummary]:
    end = end or settings.today()
    start = start or end - timedelta(days=29)
    if start > end:
        raise HTTPException(422, "start must be before end")
    if (end - start).days > MAX_RANGE_DAYS:
        raise HTTPException(422, "range is limited to 366 days")
    return repo.get_days(start, end)


@router.get("/days/{day}")
def get_day(day: date, repo: RepoDep) -> DaySummary:
    found = repo.get_days(day, day)
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No data for that day")
    return found[0]


@router.post("/screen-time", status_code=status.HTTP_201_CREATED)
def upload_screen_time(body: ScreenTimeIn, repo: RepoDep, lake: LakeDep) -> DaySummary:
    rows, totals = screen_time.summarize(body)
    lake.write_records("screen_time", body.day, rows)
    repo.upsert_day(body.day, totals)
    return repo.get_days(body.day, body.day)[0]


@router.get("/insights/scroll-vs-sleep")
def insight_scroll_vs_sleep(
    repo: RepoDep, settings: SettingsDep, days: int = Query(default=60, ge=7, le=365)
) -> ScrollSleepInsight:
    end = settings.today()
    return scroll_vs_sleep(repo.get_days(end - timedelta(days=days), end))
