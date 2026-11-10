from __future__ import annotations

import json
from datetime import date

import pytest

from life_api.handlers import _days_from_event
from life_api.ingest.job import export_applications_snapshot, ingest_health_day
from life_api.ingest.screen_time import parse_csv
from tests.fixtures import RHR_POINTS, SLEEP_POINTS, STEPS_ROLLUP

DAY = date(2026, 11, 8)


class FakeSource:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def list_data_points(self, data_type, *, filter=None, page_size=None, max_pages=None):
        self.calls.append((data_type, filter))
        return {"sleep": SLEEP_POINTS, "daily-resting-heart-rate": RHR_POINTS}[data_type]

    def daily_rollup(self, data_type, start, end):
        self.calls.append((data_type, start, end))
        return STEPS_ROLLUP


def test_ingest_writes_lake_and_dynamo(repo, lake, s3):
    source = FakeSource()
    health = ingest_health_day(DAY, source, lake, repo)

    assert health.sleep_minutes == 412 and health.steps == 9312 and health.resting_heart_rate == 58
    assert 'civil_end_time < "2026-11-09"' in source.calls[0][1]

    keys = sorted(o["Key"] for o in s3.list_objects_v2(Bucket="test-lake")["Contents"])
    assert "clean/daily_health/dt=2026-11-08/data.jsonl" in keys
    assert "raw/source=google_health/dataset=sleep/dt=2026-11-08/data.json" in keys

    row = json.loads(
        s3.get_object(Bucket="test-lake", Key="clean/daily_health/dt=2026-11-08/data.jsonl")[
            "Body"
        ].read()
    )
    assert row["day"] == "2026-11-08" and "_ingested_at" in row

    [stored] = repo.get_days(DAY, DAY)
    assert stored.sleep_minutes == 412


def test_ingest_is_idempotent(repo, lake, s3):
    ingest_health_day(DAY, FakeSource(), lake, repo)
    ingest_health_day(DAY, FakeSource(), lake, repo)
    assert s3.list_objects_v2(Bucket="test-lake")["KeyCount"] == 4
    assert len(repo.get_days(DAY, DAY)) == 1


def test_export_applications_snapshot(repo, lake, s3, client, auth):
    client.post("/v1/applications", json={"company": "Acme", "role": "DE"}, headers=auth)
    assert export_applications_snapshot(DAY, lake, repo) == 1


def test_days_from_event():
    y = date(2026, 11, 9)
    assert _days_from_event({}, y) == [y]
    assert _days_from_event({"date": "2026-01-02"}, y) == [date(2026, 1, 2)]
    assert _days_from_event({"backfill_days": 3}, y) == [date(2026, 11, 7), date(2026, 11, 8), y]
    with pytest.raises(ValueError):
        _days_from_event({"backfill_days": 500}, y)


def test_parse_screen_time_csv_sums_sessions():
    csv_text = (
        "date,package,app_name,minutes\n"
        "2026-11-08,com.instagram.android,Instagram,20\n"
        "2026-11-08,com.instagram.android,Instagram,15.5\n"
        "2026-11-09,com.google.android.youtube,YouTube,60\n"
    )
    uploads = parse_csv(csv_text)
    assert [u.day for u in uploads] == [date(2026, 11, 8), date(2026, 11, 9)]
    assert uploads[0].apps[0].minutes == 35.5


def test_parse_screen_time_csv_requires_columns():
    with pytest.raises(ValueError, match="missing"):
        parse_csv("day,app\n")
