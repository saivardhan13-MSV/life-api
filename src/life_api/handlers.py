"""AWS Lambda entry points.

* ``api_handler``    - API Gateway HTTP API -> FastAPI (via Mangum)
* ``ingest_handler`` - EventBridge Scheduler, daily. Event options::

      {}                          ingest yesterday (local time)
      {"date": "2026-11-01"}      ingest one day
      {"backfill_days": 14}       ingest the last N days
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import Any, ClassVar

import boto3
from mangum import Mangum

from life_api.api.app import create_app
from life_api.config import get_settings
from life_api.ingest.google_health import GoogleHealthClient
from life_api.ingest.job import export_applications_snapshot, ingest_health_day
from life_api.ingest.tokens import SsmTokenStore, load_client_config
from life_api.storage.dynamo import LifeRepository
from life_api.storage.lake import Lake


class JsonFormatter(logging.Formatter):
    """One JSON object per log line, so CloudWatch Logs Insights can query fields."""

    _std: ClassVar[set[str]] = set(vars(logging.LogRecord("", 0, "", 0, "", None, None)))

    def format(self, record: logging.LogRecord) -> str:
        payload = {"level": record.levelname, "logger": record.name, "msg": record.getMessage()}
        payload |= {k: v for k, v in vars(record).items() if k not in self._std}
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def _configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in root.handlers:
        h.setFormatter(JsonFormatter())


_configure_logging()
log = logging.getLogger(__name__)

api_handler = Mangum(create_app(), lifespan="off")


def _days_from_event(event: dict[str, Any], yesterday: date) -> list[date]:
    if event.get("date"):
        return [date.fromisoformat(event["date"])]
    n = int(event.get("backfill_days", 1))
    if not 1 <= n <= 90:
        raise ValueError("backfill_days must be between 1 and 90")
    return [yesterday - timedelta(days=i) for i in range(n - 1, -1, -1)]


def ingest_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    settings = get_settings()
    ssm = boto3.client("ssm", region_name=settings.aws_region)
    client = GoogleHealthClient(
        load_client_config(ssm, settings.google_client_param),
        SsmTokenStore(ssm, settings.google_token_param),
    )
    lake = Lake.from_settings(settings)
    repo = LifeRepository.from_settings(settings)

    days = _days_from_event(event or {}, settings.yesterday())
    results = [ingest_health_day(d, client, lake, repo).model_dump(mode="json") for d in days]
    app_count = export_applications_snapshot(settings.today(), lake, repo)
    log.info("ingest complete", extra={"days": len(results), "applications": app_count})
    return {"days": results, "applications_exported": app_count}
