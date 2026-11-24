with memberships as (
    select * from {{ ref('fct_memberships') }}
),
days as (
    select * from {{ ref('time_spine_daily') }}
)

select
    concat(m.membership_id, '-', d.date_day) as member_day_id,
    m.membership_id,
    m.member_id,
    m.location_id,
    m.plan_id,
    m.plan_name,
    d.date_day
from memberships m
join days d
  on d.date_day between m.start_date and m.effective_end_date