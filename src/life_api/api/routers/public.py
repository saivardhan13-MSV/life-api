from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Query, Response

from life_api.api.deps import RepoDep, SettingsDep
from life_api.domain import PublicSummary, PublicTimeseries
from life_api.services.summary import build_public_summary, build_public_timeseries

router = APIRouter(tags=["public"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/public/summary")
def public_summary(response: Response, repo: RepoDep, settings: SettingsDep) -> PublicSummary:
    """Aggregates only. This is what the public dashboard and recruiters see."""
    today = settings.today()
    summary = build_public_summary(
        repo.list_applications(), repo.get_days(today - timedelta(days=90), today), today
    )
    response.headers["Cache-Control"] = "public, max-age=300"
    return summary


@router.get("/public/timeseries")
def public_timeseries(
    response: Response,
    repo: RepoDep,
    settings: SettingsDep,
    days: int = Query(default=30, ge=7, le=90),
) -> PublicTimeseries:
    """Daily series for the dashboard charts. Application *counts* only, never companies."""
    end = settings.today()
    start = end - timedelta(days=days - 1)
    series = build_public_timeseries(
        repo.list_applications(), repo.get_days(start, end), start, end
    )
    response.headers["Cache-Control"] = "public, max-age=300"
    return series
