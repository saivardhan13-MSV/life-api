from datetime import UTC, date, datetime, timedelta

from life_api.domain import Application, ApplicationStatus, DaySummary
from life_api.services.summary import build_public_summary, job_hunt, scroll_vs_sleep

TODAY = date(2026, 11, 12)  # a Thursday


def _app(days_ago: int, status=ApplicationStatus.APPLIED) -> Application:
    now = datetime.now(UTC)
    return Application(
        id=str(days_ago),
        company="X",
        role="SDE",
        applied_on=TODAY - timedelta(days=days_ago),
        status=status,
        created_at=now,
        updated_at=now,
    )


def test_public_summary_has_habit_not_counts():
    apps = [_app(0), _app(0), _app(1), _app(2), _app(5, ApplicationStatus.REJECTED)]
    days = [
        DaySummary(day=TODAY - timedelta(days=i), sleep_minutes=420, steps=8000) for i in range(7)
    ]
    s = build_public_summary(apps, days, TODAY)
    assert s.job_hunt.applied_today is True
    assert s.job_hunt.streak_days == 3  # today, -1, -2; gap at -3
    assert s.avg_sleep_hours_7d == 7.0
    assert s.avg_steps_7d == 8000
    dumped = s.model_dump_json()
    for leaked in ("applications_total", "interviews", "rejected", "status"):
        assert leaked not in dumped


def test_streak_survives_until_you_log_today():
    hunt = job_hunt([_app(1), _app(2)], TODAY)
    assert hunt.applied_today is False
    assert hunt.streak_days == 2


def test_streak_zero_when_lapsed():
    assert job_hunt([_app(3)], TODAY).streak_days == 0
    assert job_hunt([], TODAY).streak_days == 0


def test_scroll_vs_sleep_detects_penalty():
    days = []
    for i in range(10):
        heavy = i % 2 == 0
        days.append(
            DaySummary(
                day=TODAY - timedelta(days=10 - i),
                doomscroll_minutes=180 if heavy else 30,
                # the *previous* day's scrolling decides tonight's sleep
                sleep_minutes=360 if i > 0 and (i - 1) % 2 == 0 else 450,
            )
        )
    insight = scroll_vs_sleep(days)
    assert insight.days_compared == 9
    assert insight.difference_minutes == 90
    assert "90 min less" in insight.message


def test_scroll_vs_sleep_needs_data():
    assert scroll_vs_sleep([]).message.startswith("Not enough")
