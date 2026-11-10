from datetime import UTC, date, datetime, timedelta

from life_api.domain import Application, ApplicationStatus, DaySummary
from life_api.services.summary import build_public_summary, scroll_vs_sleep

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


def test_public_summary_counts():
    apps = [_app(0), _app(0), _app(2), _app(5, ApplicationStatus.INTERVIEWING), _app(40)]
    days = [
        DaySummary(day=TODAY - timedelta(days=i), sleep_minutes=420, steps=8000) for i in range(7)
    ]
    s = build_public_summary(apps, days, TODAY)
    assert s.applications_total == 5
    assert s.applications_today == 2
    assert s.applications_this_week == 3  # Mon 9th .. Thu 12th
    assert s.applications_last_30_days == 4
    assert s.interviews_total == 1
    assert s.avg_sleep_hours_7d == 7.0
    assert s.avg_steps_7d == 8000
    assert s.avg_screen_hours_7d is None


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
