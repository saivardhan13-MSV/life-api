-- One row per calendar day: how you slept, moved, scrolled and job-hunted.
with bounds as (
    select min(d) as first_day, current_date as last_day
    from (
        select min(activity_date) as d from {{ ref('stg_daily_health') }}
        union all
        select min(activity_date) from {{ ref('stg_screen_time') }}
        union all
        select min(applied_date) from {{ ref('stg_applications') }}
    )
),

calendar as (
    select d as activity_date
    from bounds
    cross join unnest(sequence(first_day, last_day, interval '1' day)) as t(d)
),

screen as (
    select
        activity_date,
        sum(minutes)                                    as screen_minutes,
        sum(case when is_doomscroll then minutes end)   as doomscroll_minutes
    from {{ ref('stg_screen_time') }}
    group by activity_date
),

apps as (
    select applied_date as activity_date, count(*) as applications_sent
    from {{ ref('stg_applications') }}
    group by applied_date
)

select
    c.activity_date,
    day_of_week(c.activity_date)                    as iso_weekday,
    h.sleep_minutes,
    round(h.sleep_minutes / 60.0, 2)                as sleep_hours,
    h.deep_sleep_minutes,
    h.rem_sleep_minutes,
    h.steps,
    h.resting_heart_rate,
    s.screen_minutes,
    s.doomscroll_minutes,
    coalesce(a.applications_sent, 0)                as applications_sent,
    -- tonight's sleep, for "does scrolling today hurt sleep tonight?" analysis
    lead(h.sleep_minutes) over (order by c.activity_date) as next_night_sleep_minutes
from calendar c
left join {{ ref('stg_daily_health') }} h on c.activity_date = h.activity_date
left join screen s on c.activity_date = s.activity_date
left join apps a on c.activity_date = a.activity_date
