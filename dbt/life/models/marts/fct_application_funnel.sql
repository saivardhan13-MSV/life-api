-- Weekly job-search funnel: how many applications move past "applied".
select
    date_trunc('week', applied_date)                                          as week_start,
    count(*)                                                                  as applications,
    count_if(status in ('screening', 'interviewing', 'offer'))                as responses,
    count_if(status in ('interviewing', 'offer'))                             as interviews,
    count_if(status = 'offer')                                                as offers,
    count_if(status = 'rejected')                                             as rejections,
    round(100.0 * count_if(status in ('screening', 'interviewing', 'offer')) / count(*), 1)
                                                                              as response_rate_pct
from {{ ref('stg_applications') }}
group by 1
