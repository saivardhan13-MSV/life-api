-- Fails (returns rows) if any day has physically impossible values.
select *
from {{ ref('fct_daily_life') }}
where sleep_minutes not between 0 and 1440
   or steps < 0
   or resting_heart_rate not between 25 and 140
   or screen_minutes not between 0 and 1440
