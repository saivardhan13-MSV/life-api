from datetime import date

from life_api.ingest.transform import (
    build_daily_health,
    parse_resting_hr,
    parse_sleep,
    parse_steps_rollup,
)
from tests.fixtures import RHR_POINTS, SLEEP_POINTS, STEPS_ROLLUP

DAY = date(2026, 11, 8)


def test_parse_sleep_picks_main_session_and_stages():
    out = parse_sleep(SLEEP_POINTS)
    assert out["sleep_minutes"] == 412
    assert out["deep_sleep_minutes"] == 71
    assert out["rem_sleep_minutes"] == 103
    assert out["light_sleep_minutes"] == 238
    assert out["awake_minutes"] == 38
    assert out["sleep_end"].isoformat() == "2026-11-08T11:40:00+00:00"


def test_parse_sleep_without_main_flag_uses_longest():
    points = [
        {"sleep": {"summary": {"minutesAsleep": "30"}}},
        {"sleep": {"summary": {"minutesAsleep": "400"}}},
    ]
    assert parse_sleep(points)["sleep_minutes"] == 400


def test_parse_sleep_empty():
    assert parse_sleep([]) == {}


def test_parse_steps_only_counts_requested_day():
    assert parse_steps_rollup(STEPS_ROLLUP, DAY) == 9312
    assert parse_steps_rollup(STEPS_ROLLUP, date(2026, 1, 1)) is None


def test_parse_resting_hr_matches_date():
    assert parse_resting_hr(RHR_POINTS, DAY) == 58
    assert parse_resting_hr(RHR_POINTS, date(2026, 11, 9)) == 61
    assert parse_resting_hr(RHR_POINTS, date(2026, 1, 1)) is None


def test_build_daily_health_tolerates_garbage():
    health = build_daily_health(DAY, [{"sleep": {"summary": {"minutesAsleep": "n/a"}}}], [], [{}])
    assert health.sleep_minutes is None
    assert health.steps is None
    assert health.resting_heart_rate is None


def test_parse_sleep_prefers_main_sleep_over_longer_nap():
    points = [
        {"sleep": {"metadata": {"mainSleep": False}, "summary": {"minutesAsleep": "300"}}},
        {"sleep": {"metadata": {"mainSleep": True}, "summary": {"minutesAsleep": "200"}}},
    ]
    assert parse_sleep(points)["sleep_minutes"] == 200
