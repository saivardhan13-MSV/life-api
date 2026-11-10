"""Pure functions that turn stored data into summaries and insights."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from statistics import mean, median

from life_api.domain import (
    Application,
    ApplicationStatus,
    DaySummary,
    PublicDay,
    PublicSummary,
    PublicTimeseries,
    ScrollSleepInsight,
)

INTERVIEW_STATUSES = {ApplicationStatus.INTERVIEWING, ApplicationStatus.OFFER}


def _avg(values: list[float]) -> float | None:
    return mean(values) if values else None


def _hours(minutes: float | None) -> float | None:
    return round(minutes / 60, 1) if minutes is not None else None


def build_public_summary(
    apps: list[Application], days: list[DaySummary], today: date
) -> PublicSummary:
    week_start = today - timedelta(days=today.weekday())  # Monday
    last7 = [d for d in days if today - timedelta(days=7) < d.day <= today]
    by_day = {d.day: d for d in days}
    last_night = by_day.get(today) or by_day.get(today - timedelta(days=1))

    avg_steps = _avg([d.steps for d in last7 if d.steps is not None])
    return PublicSummary(
        generated_at=datetime.now(UTC),
        applications_total=len(apps),
        applications_today=sum(a.applied_on == today for a in apps),
        applications_this_week=sum(week_start <= a.applied_on <= today for a in apps),
        applications_last_30_days=sum(
            today - timedelta(days=30) < a.applied_on <= today for a in apps
        ),
        interviews_total=sum(a.status in INTERVIEW_STATUSES for a in apps),
        last_night_sleep_hours=_hours(last_night.sleep_minutes) if last_night else None,
        avg_sleep_hours_7d=_hours(_avg([d.sleep_minutes for d in last7 if d.sleep_minutes])),
        avg_steps_7d=round(avg_steps) if avg_steps is not None else None,
        avg_screen_hours_7d=_hours(
            _avg([d.screen_minutes for d in last7 if d.screen_minutes is not None])
        ),
        avg_doomscroll_hours_7d=_hours(
            _avg([d.doomscroll_minutes for d in last7 if d.doomscroll_minutes is not None])
        ),
        days_tracked=len(days),
    )


def scroll_vs_sleep(days: list[DaySummary]) -> ScrollSleepInsight:
    """Compare sleep after high-scroll days with sleep after low-scroll days.

    Scrolling on day N is paired with the sleep recorded on day N+1 (the night
    after). Days are split at the median doomscroll time.
    """
    by_day = {d.day: d for d in days}
    pairs: list[tuple[float, float]] = []
    for d in days:
        nxt = by_day.get(d.day + timedelta(days=1))
        if d.doomscroll_minutes is not None and nxt and nxt.sleep_minutes:
            pairs.append((d.doomscroll_minutes, float(nxt.sleep_minutes)))

    if len(pairs) < 4:
        return ScrollSleepInsight(
            days_compared=len(pairs),
            doomscroll_threshold_minutes=None,
            avg_sleep_hours_high_scroll=None,
            avg_sleep_hours_low_scroll=None,
            difference_minutes=None,
            message="Not enough paired days yet (need at least 4).",
        )

    # Compare the heaviest half of days with the lightest half (middle day dropped
    # when odd), which stays well-defined even when many days tie at the median.
    pairs.sort(key=lambda p: p[0])
    half = len(pairs) // 2
    threshold = median(p[0] for p in pairs)
    low = [s for _, s in pairs[:half]]
    high = [s for _, s in pairs[-half:]]
    high_avg, low_avg = _avg(high), _avg(low)
    diff = round(low_avg - high_avg, 1) if high_avg is not None and low_avg is not None else None

    if diff is None:
        message = "Scrolling was too uniform to compare."
    elif diff > 0:
        message = f"You sleep {diff:.0f} min less after your heaviest-scrolling days."
    else:
        message = f"No sleep penalty found after heavy-scroll days (diff {diff:.0f} min)."

    return ScrollSleepInsight(
        days_compared=len(pairs),
        doomscroll_threshold_minutes=round(threshold, 1),
        avg_sleep_hours_high_scroll=_hours(high_avg),
        avg_sleep_hours_low_scroll=_hours(low_avg),
        difference_minutes=diff,
        message=message,
    )


def build_public_timeseries(
    apps: list[Application], days: list[DaySummary], start: date, end: date
) -> PublicTimeseries:
    """Every calendar day in ``[start, end]`` (gaps included), plus a status funnel."""
    by_day = {d.day: d for d in days}
    sent: dict[date, int] = {}
    for a in apps:
        sent[a.applied_on] = sent.get(a.applied_on, 0) + 1

    rows = []
    d = start
    while d <= end:
        known = by_day.get(d)
        fields = known.model_dump(exclude={"day"}) if known else {}
        rows.append(PublicDay(day=d, applications_sent=sent.get(d, 0), **fields))
        d += timedelta(days=1)

    status_counts = {s.value: 0 for s in ApplicationStatus}
    for a in apps:
        status_counts[a.status.value] += 1
    return PublicTimeseries(generated_at=datetime.now(UTC), days=rows, status_counts=status_counts)
