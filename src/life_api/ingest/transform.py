"""Turn Google Health API payloads into a flat ``DailyHealth`` row.

Parsers are defensive: the API returns numbers as strings, and for some data
types (resting heart rate) the docs do not show the response shape, so we
search for the value instead of hard-coding one path. Raw payloads are always
kept in the lake, so a parser bug can be fixed and the day replayed.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from life_api.domain import DailyHealth

STAGE_FIELDS = {
    "DEEP": "deep_sleep_minutes",
    "LIGHT": "light_sleep_minutes",
    "REM": "rem_sleep_minutes",
    "AWAKE": "awake_minutes",
}
RHR_VALUE_KEYS = ("beatsPerMinute", "restingHeartRate", "bpm", "value")


def _int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return round(float(value))
    except (TypeError, ValueError):
        return None


def _parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def civil_date(obj: Any) -> date | None:
    """``{"year": 2026, "month": 3, "day": 4}`` -> ``date(2026, 3, 4)``."""
    if isinstance(obj, dict) and {"year", "month", "day"} <= obj.keys():
        try:
            return date(int(obj["year"]), int(obj["month"]), int(obj["day"]))
        except (TypeError, ValueError):
            return None
    return None


def _find_date(obj: Any) -> date | None:
    """Depth-first search for the first civil date in a payload."""
    found = civil_date(obj)
    if found:
        return found
    if isinstance(obj, dict):
        for v in obj.values():
            if (found := _find_date(v)) is not None:
                return found
    elif isinstance(obj, list):
        for v in obj:
            if (found := _find_date(v)) is not None:
                return found
    return None


def _find_number(obj: Any, keys: tuple[str, ...]) -> int | None:
    if isinstance(obj, dict):
        for k in keys:
            if k in obj and (n := _int(obj[k])) is not None:
                return n
        for v in obj.values():
            if (n := _find_number(v, keys)) is not None:
                return n
    elif isinstance(obj, list):
        for v in obj:
            if (n := _find_number(v, keys)) is not None:
                return n
    return None


def parse_sleep(points: list[dict[str, Any]]) -> dict[str, Any]:
    """Pick the main sleep session (or the longest) and flatten its summary."""
    sessions = [p["sleep"] for p in points if isinstance(p.get("sleep"), dict)]
    if not sessions:
        return {}
    # The live API uses ``mainSleep``; the docs show ``main``. Accept both.
    main = [
        s
        for s in sessions
        if (s.get("metadata") or {}).get("mainSleep") or (s.get("metadata") or {}).get("main")
    ]
    chosen = max(
        main or sessions, key=lambda s: _int(s.get("summary", {}).get("minutesAsleep")) or 0
    )
    summary = chosen.get("summary", {})
    out: dict[str, Any] = {
        "sleep_minutes": _int(summary.get("minutesAsleep")),
        "sleep_start": _parse_ts(chosen.get("interval", {}).get("startTime")),
        "sleep_end": _parse_ts(chosen.get("interval", {}).get("endTime")),
    }
    for stage in summary.get("stagesSummary", []) or []:
        field = STAGE_FIELDS.get(str(stage.get("type", "")).upper())
        if field:
            out[field] = _int(stage.get("minutes"))
    if out.get("awake_minutes") is None:
        out["awake_minutes"] = _int(summary.get("minutesAwake"))
    return out


def parse_steps_rollup(rollups: list[dict[str, Any]], day: date) -> int | None:
    total: int | None = None
    for r in rollups:
        start = civil_date((r.get("civilStartTime") or {}).get("date"))
        if start != day:
            continue
        count = _int((r.get("steps") or {}).get("countSum"))
        if count is not None:
            total = (total or 0) + count
    return total


def parse_resting_hr(points: list[dict[str, Any]], day: date) -> int | None:
    for p in points:
        if _find_date(p) == day:
            return _find_number(p, RHR_VALUE_KEYS)
    return None


def build_daily_health(
    day: date,
    sleep_points: list[dict[str, Any]],
    steps_rollups: list[dict[str, Any]],
    rhr_points: list[dict[str, Any]],
) -> DailyHealth:
    return DailyHealth(
        day=day,
        **parse_sleep(sleep_points),
        steps=parse_steps_rollup(steps_rollups, day),
        resting_heart_rate=parse_resting_hr(rhr_points, day),
    )
