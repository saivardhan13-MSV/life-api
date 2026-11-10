-- Latest ingest wins when a day is re-run (backfills, parser fixes).
with ranked as (
    select
        *,
        row_number() over (partition by day order by _ingested_at desc) as rn
    from {{ source('clean', 'daily_health') }}
)

select
    cast(day as date)                                   as activity_date,
    sleep_minutes,
    deep_sleep_minutes,
    light_sleep_minutes,
    rem_sleep_minutes,
    awake_minutes,
    from_iso8601_timestamp(sleep_start)                 as sleep_start_at,
    from_iso8601_timestamp(sleep_end)                   as sleep_end_at,
    steps,
    resting_heart_rate,
    from_iso8601_timestamp(_ingested_at)                as ingested_at
from ranked
where rn = 1
