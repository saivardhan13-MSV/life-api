from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Response

from life_api.api.deps import RepoDep, SettingsDep
from life_api.domain import PublicSummary
from life_api.services.summary import build_public_summary

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
