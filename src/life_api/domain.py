"""Domain models shared by the API, ingestion jobs and storage layer."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ApplicationStatus(StrEnum):
    APPLIED = "applied"
    SCREENING = "screening"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    REJECTED = "rejected"
    GHOSTED = "ghosted"
    WITHDRAWN = "withdrawn"


class ApplicationIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    company: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=200)
    applied_on: date | None = Field(default=None, description="Defaults to today (local time).")
    status: ApplicationStatus = ApplicationStatus.APPLIED
    source: str = Field(default="jobright", max_length=50)
    location: str | None = Field(default=None, max_length=200)
    url: HttpUrl | None = None
    notes: str | None = Field(default=None, max_length=2000)


class ApplicationUpdate(BaseModel):
    status: ApplicationStatus | None = None
    notes: str | None = Field(default=None, max_length=2000)


class Application(ApplicationIn):
    id: str
    applied_on: date
    created_at: datetime
    updated_at: datetime


class DailyHealth(BaseModel):
    """One day of wearable data. Sleep is attributed to the day you woke up."""

    day: date
    sleep_minutes: int | None = None
    deep_sleep_minutes: int | None = None
    light_sleep_minutes: int | None = None
    rem_sleep_minutes: int | None = None
    awake_minutes: int | None = None
    sleep_start: datetime | None = None
    sleep_end: datetime | None = None
    steps: int | None = None
    resting_heart_rate: int | None = None


class AppUsage(BaseModel):
    package: str = Field(min_length=1, max_length=200, examples=["com.instagram.android"])
    app_name: str | None = Field(default=None, max_length=200)
    minutes: float = Field(ge=0, le=24 * 60)


class ScreenTimeIn(BaseModel):
    day: date
    apps: list[AppUsage] = Field(min_length=1, max_length=500)


class DaySummary(BaseModel):
    """Everything known about one day, merged from all sources."""

    day: date
    sleep_minutes: int | None = None
    deep_sleep_minutes: int | None = None
    light_sleep_minutes: int | None = None
    rem_sleep_minutes: int | None = None
    awake_minutes: int | None = None
    steps: int | None = None
    resting_heart_rate: int | None = None
    screen_minutes: float | None = None
    doomscroll_minutes: float | None = None


class JobHunt(BaseModel):
    """Public job-search signal: a daily habit, never counts, companies or outcomes."""

    applied_today: bool
    streak_days: int = Field(description="Consecutive days with at least one application.")


class PublicSummary(BaseModel):
    """Aggregates only: safe to show to anyone. No application counts, no company names."""

    generated_at: datetime
    job_hunt: JobHunt
    last_night_sleep_hours: float | None
    avg_sleep_hours_7d: float | None
    avg_steps_7d: int | None
    avg_screen_hours_7d: float | None
    avg_doomscroll_hours_7d: float | None
    days_tracked: int


class ScrollSleepInsight(BaseModel):
    days_compared: int
    doomscroll_threshold_minutes: float | None
    avg_sleep_hours_high_scroll: float | None
    avg_sleep_hours_low_scroll: float | None
    difference_minutes: float | None
    message: str


class PublicDay(BaseModel):
    """One day on the public dashboard. Counts and health metrics only."""

    day: date
    sleep_minutes: int | None = None
    deep_sleep_minutes: int | None = None
    light_sleep_minutes: int | None = None
    rem_sleep_minutes: int | None = None
    awake_minutes: int | None = None
    steps: int | None = None
    resting_heart_rate: int | None = None
    screen_minutes: float | None = None
    doomscroll_minutes: float | None = None
    applied: bool = False


class PublicTimeseries(BaseModel):
    generated_at: datetime
    job_hunt: JobHunt
    days: list[PublicDay]
