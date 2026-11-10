-- A re-upload of a day replaces it, so keep only rows from the latest upload per day.
with latest_upload as (
    select day, max(_ingested_at) as _ingested_at
    from {{ source('clean', 'screen_time') }}
    group by day
)

select
    cast(s.day as date)                       as activity_date,
    s.package,
    coalesce(c.app_name, s.app_name, s.package) as app_name,
    coalesce(c.category, 'other')             as category,
    coalesce(c.is_doomscroll, s.is_doomscroll) as is_doomscroll,
    s.minutes
from {{ source('clean', 'screen_time') }} s
join latest_upload l
  on s.day = l.day and s._ingested_at = l._ingested_at
left join {{ ref('app_categories') }} c
  on s.package = c.package
