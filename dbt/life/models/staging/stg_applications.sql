-- The tracker is exported as a full snapshot each day; the newest snapshot is the truth.
with latest as (
    select max(dt) as dt from {{ source('clean', 'applications') }}
)

select
    a.id                                   as application_id,
    a.company,
    a.role,
    a.status,
    a.source,
    a.location,
    cast(a.applied_on as date)             as applied_date,
    from_iso8601_timestamp(a.created_at)   as created_at,
    from_iso8601_timestamp(a.updated_at)   as updated_at
from {{ source('clean', 'applications') }} a
join latest l on a.dt = l.dt
